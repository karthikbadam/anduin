"""Hot-sky-cells support.

- `HotCellsConsumer` tails Flink output topic `anduin.sky.hot_cells.v1` and
  populates Redis ZSETs `sky:hot:{window_end_ms}`, tracking the latest key
  in `sky:hot:latest`.
- `cells_to_features()` converts (cell_id, n_sats) pairs to GeoJSON polygons
  using HEALPix boundaries at nside=64. Polygons that cross the antimeridian
  are dropped (~1% of cells) to avoid visual artifacts.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid

import numpy as np
import healpy as hp
import redis.asyncio as redis_asyncio
from aiokafka import AIOKafkaConsumer

log = logging.getLogger("query-api.hot-cells")

TOPIC = "anduin.sky.hot_cells.v1"
NSIDE = 64
LATEST_KEY = "sky:hot:latest"
WINDOW_TTL_S = 600


class HotCellsConsumer:
    def __init__(self, bootstrap: str, redis: redis_asyncio.Redis):
        self.bootstrap = bootstrap
        self.redis = redis
        self._consumer: AIOKafkaConsumer | None = None
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        group = f"anduin.query-api-hotcells.{uuid.uuid4().hex[:8]}"
        self._consumer = AIOKafkaConsumer(
            TOPIC,
            bootstrap_servers=self.bootstrap,
            group_id=group,
            auto_offset_reset="latest",
            enable_auto_commit=False,
            value_deserializer=lambda b: json.loads(b.decode("utf-8")),
        )
        await self._consumer.start()
        self._task = asyncio.create_task(self._pump(), name="hot-cells-pump")
        log.info("hot-cells consumer started")

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
                d = msg.value
                window_end_ms = int(d["window_end_ms"])
                cell = int(d["cell"])
                n_sats = int(d["n_sats"])
                key = f"sky:hot:{window_end_ms}"
                pipe = self.redis.pipeline()
                pipe.zadd(key, {str(cell): n_sats})
                pipe.expire(key, WINDOW_TTL_S)
                pipe.set(LATEST_KEY, str(window_end_ms), ex=WINDOW_TTL_S)
                await pipe.execute()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("hot-cells pump crashed")


def cells_to_features(cells: list[tuple[int, int]], nside: int = NSIDE) -> list[dict]:
    """Convert (cell_id, n_sats) list to GeoJSON Polygon features.

    Boundaries come from healpy.boundaries which returns 3D unit vectors for
    each cell's 4 corners in NESTED ordering. We flatten, transform to
    geodetic lon/lat via hp.vec2ang, then reshape back and build polygons.
    Cells spanning the antimeridian are dropped — the PolygonLayer's
    `wrapLongitude` handles most cases but a few degenerate ones still
    produce visual artifacts at nside=64.
    """
    if not cells:
        return []
    pix = np.array([c[0] for c in cells], dtype=np.int64)
    # (npix, 3, 4) → (npix, 4, 3)
    vecs = np.transpose(hp.boundaries(nside, pix, step=1, nest=True), (0, 2, 1))
    flat = vecs.reshape(-1, 3)
    theta, phi = hp.vec2ang(flat)
    lon = np.degrees(phi)
    lat = 90.0 - np.degrees(theta)
    lon = np.where(lon > 180.0, lon - 360.0, lon)
    lon = lon.reshape(-1, 4)
    lat = lat.reshape(-1, 4)

    features: list[dict] = []
    for i, (cell_id, n_sats) in enumerate(cells):
        cell_lon = lon[i]
        cell_lat = lat[i]
        if float(cell_lon.max() - cell_lon.min()) > 180:
            continue  # antimeridian-crossing; skip
        ring = [[float(cell_lon[k]), float(cell_lat[k])] for k in range(4)]
        ring.append(ring[0])
        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {"cell": int(cell_id), "n_sats": int(n_sats)},
        })
    return features
