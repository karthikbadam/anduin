"""Kafka producer wrapper with Confluent wire-format Avro serialization.

- Single `confluent_kafka.Producer` instance (idempotent, compressed).
- `stats_cb` JSON is parsed into Prometheus gauges for producer in-flight,
  RTT, batch size, and internal queue depth (see metrics module).
"""
from __future__ import annotations

import json
import logging
from typing import Any

from confluent_kafka import Producer

from .avro_codec import AvroCodec
from .metrics import producer_metrics

log = logging.getLogger(__name__)


class KafkaProducerWrapper:
    def __init__(self, bootstrap: str, codec: AvroCodec):
        self.codec = codec
        self.producer = Producer(
            {
                "bootstrap.servers": bootstrap,
                "acks": "all",
                "enable.idempotence": True,
                "linger.ms": 10,
                "compression.type": "zstd",
                "statistics.interval.ms": 5000,
                "stats_cb": self._on_stats,
            }
        )

    def _on_stats(self, stats_json: str) -> None:
        try:
            stats: dict[str, Any] = json.loads(stats_json)
            producer_metrics.set_from_stats(stats)
        except Exception as e:  # noqa: BLE001
            log.warning("producer stats parse error: %s", e)

    def publish(self, topic: str, subject: str, key: str, value: dict) -> None:
        """Serialize `value` to Confluent wire format and produce to `topic`.
        Caller must catch BufferError if the producer queue is full.
        """
        payload = self.codec.encode(subject, value)
        self.producer.produce(topic=topic, key=key.encode("utf-8"), value=payload)
        # Serve delivery callbacks without blocking the event loop.
        self.producer.poll(0)

    def flush(self, timeout: float = 5.0) -> int:
        return self.producer.flush(timeout)
