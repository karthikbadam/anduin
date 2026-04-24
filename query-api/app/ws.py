"""WebSocket fan-out hub.

A single background aiokafka consumer reads the live topics and a simple
asyncio PubSub broadcasts decoded frames to every connected client, filtered
by each client's subscribe request. One replica handles ~1k concurrent WS
connections comfortably.

Client protocol (JSON over the WS):
  → {"subscribe": ["satellite.position","passes","alerts"], "filter": {"norad_ids": ["25544"]}}
  ← {"topic":"satellite.position","ts":...,"data":{...}}
  ← {"topic":"ping","ts":...}   (server heartbeat every 20s)
  → {"pong": <ts>}              (client reply; optional — server only uses timeouts)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from aiokafka import AIOKafkaConsumer
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from .codec import SchemaCache

log = logging.getLogger("query-api.ws")

# Friendly subscribe-names → Kafka topic mapping.
TOPIC_MAP = {
    "satellite.position": "anduin.satellite.position.v1",
    "passes":             "anduin.satellite.pass.v1",
    "alerts":             "anduin.satellite.anomaly.v1",
}
KAFKA_TO_FRIENDLY = {v: k for k, v in TOPIC_MAP.items()}

# Heartbeat cadence + stale-client close threshold.
PING_EVERY_S = 20
MAX_IDLE_S = 60


def _json_default(o: Any) -> Any:
    if isinstance(o, datetime):
        return o.astimezone(timezone.utc).isoformat()
    if isinstance(o, uuid.UUID):
        return str(o)
    if isinstance(o, Decimal):
        return float(o)
    if isinstance(o, bytes):
        return o.hex()
    raise TypeError(f"{type(o).__name__} not JSON serializable")


def _to_json(obj: Any) -> str:
    return json.dumps(obj, default=_json_default, separators=(",", ":"))


class WsClient:
    """Per-connection state. Queue provides backpressure — if a client can't
    keep up, older frames are dropped rather than blocking the hub loop."""

    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.topics: set[str] = set()
        self.norad_filter: set[str] | None = None
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=1024)
        self.dropped = 0

    def matches(self, topic: str, data: dict) -> bool:
        if topic not in self.topics:
            return False
        if self.norad_filter is not None:
            nid = data.get("norad_id") if isinstance(data, dict) else None
            if nid not in self.norad_filter:
                return False
        return True

    def offer(self, frame: dict) -> None:
        try:
            self.queue.put_nowait(frame)
        except asyncio.QueueFull:
            self.dropped += 1  # frame dropped; backpressure signal


class WsHub:
    """Single consumer, fan-out to N WS clients via asyncio.Queue per client."""

    def __init__(self, kafka_bootstrap: str, schema_registry: str):
        self.bootstrap = kafka_bootstrap
        self.cache = SchemaCache(schema_registry)
        self.clients: set[WsClient] = set()
        self._consumer: AIOKafkaConsumer | None = None
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        # Ephemeral group id so we don't commit offsets; start from latest.
        group_id = f"anduin.query-api-ws.{uuid.uuid4().hex[:8]}"
        self._consumer = AIOKafkaConsumer(
            *TOPIC_MAP.values(),
            bootstrap_servers=self.bootstrap,
            group_id=group_id,
            auto_offset_reset="latest",
            enable_auto_commit=False,
            value_deserializer=None,
        )
        await self._consumer.start()
        self._task = asyncio.create_task(self._pump(), name="ws-hub-pump")
        log.info("ws-hub started: topics=%s", list(TOPIC_MAP.values()))

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        if self._consumer:
            await self._consumer.stop()

    async def _pump(self) -> None:
        assert self._consumer is not None
        try:
            async for msg in self._consumer:
                try:
                    _sid, decoded = await self.cache.decode(msg.value)
                except Exception as e:  # noqa: BLE001
                    log.warning("decode error on %s offset=%d: %s", msg.topic, msg.offset, e)
                    continue
                friendly = KAFKA_TO_FRIENDLY.get(msg.topic, msg.topic)
                frame = {"topic": friendly, "ts": int(time.time() * 1000), "data": decoded}
                for c in list(self.clients):
                    if c.matches(friendly, decoded):
                        c.offer(frame)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("ws-hub pump crashed")

    def register(self, client: WsClient) -> None:
        self.clients.add(client)

    def unregister(self, client: WsClient) -> None:
        self.clients.discard(client)


# ───────────────────────────── WebSocket route ─────────────────────────────

router = APIRouter()


async def _require_api_key_ws(ws: WebSocket, api_key_q: str | None) -> bool:
    # Allow key via header (if the client supports it), query param, or Sec-WebSocket-Protocol.
    raw = (
        ws.headers.get("x-api-key")
        or api_key_q
        or ws.headers.get("sec-websocket-protocol")
    )
    if not raw:
        await ws.close(code=4401, reason="missing api key")
        return False
    key = await ws.app.state.auth.lookup(raw)
    if key is None:
        await ws.close(code=4401, reason="invalid api key")
        return False
    return True


@router.websocket("/ws/stream")
async def ws_stream(ws: WebSocket, api_key: str | None = Query(default=None)) -> None:
    if not await _require_api_key_ws(ws, api_key):
        return

    # If the client sent a Sec-WebSocket-Protocol header (our workaround for
    # browser X-API-Key), echo it back so the handshake completes.
    subprotocol = ws.headers.get("sec-websocket-protocol")
    await ws.accept(subprotocol=subprotocol)

    hub: WsHub = ws.app.state.ws_hub
    client = WsClient(ws)
    hub.register(client)
    last_rx_ts = time.time()

    # All writes go through the sender task via the queue so we never have
    # two tasks concurrently calling ws.send_text (Starlette is not safe for that).
    def enqueue(frame: dict) -> None:
        try:
            client.queue.put_nowait(frame)
        except asyncio.QueueFull:
            client.dropped += 1

    async def sender() -> None:
        try:
            while True:
                frame = await client.queue.get()
                await ws.send_text(_to_json(frame))
        except WebSocketDisconnect:
            return
        except Exception as e:  # noqa: BLE001
            log.info("ws sender stopped: %s", e)

    async def receiver() -> None:
        nonlocal last_rx_ts
        try:
            while True:
                raw = await ws.receive_text()
                last_rx_ts = time.time()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if "subscribe" in msg:
                    client.topics = set(msg.get("subscribe", [])) & set(TOPIC_MAP.keys())
                    f = msg.get("filter") or {}
                    nids = f.get("norad_ids")
                    client.norad_filter = set(nids) if nids else None
                    enqueue({"topic": "subscribed", "ts": int(time.time() * 1000),
                             "data": {"topics": sorted(client.topics)}})
        except WebSocketDisconnect:
            return
        except Exception as e:  # noqa: BLE001
            log.info("ws receiver stopped: %s", e)

    async def pinger() -> None:
        try:
            while True:
                await asyncio.sleep(PING_EVERY_S)
                if time.time() - last_rx_ts > MAX_IDLE_S:
                    enqueue({"topic": "ping", "ts": int(time.time() * 1000),
                             "data": {"reason": "closing-stale-client"}})
                    await asyncio.sleep(0.1)
                    await ws.close(code=1011, reason="client idle")
                    return
                enqueue({"topic": "ping", "ts": int(time.time() * 1000)})
        except (WebSocketDisconnect, RuntimeError):
            return
        except Exception as e:  # noqa: BLE001
            log.info("ws pinger stopped: %s", e)

    tasks = [asyncio.create_task(coro, name=name) for coro, name in (
        (sender(), "ws-sender"),
        (receiver(), "ws-receiver"),
        (pinger(), "ws-pinger"),
    )]
    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in done:
            if t.exception():
                log.info("ws task %s raised: %s", t.get_name(), t.exception())
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        log.exception("ws handler error")
    finally:
        hub.unregister(client)
        for t in tasks:
            t.cancel()
        for t in tasks:
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
