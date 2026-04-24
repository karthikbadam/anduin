"""Producer-stats → Prometheus gauges.

`confluent_kafka` emits a rich JSON stats payload every `statistics.interval.ms`.
We surface a handful of useful fields:
  - msg_cnt: in-flight message count
  - msg_size: bytes enqueued
  - int_latency (avg): enqueue → in-flight, in µs
  - rtt (avg): broker RTT per broker, averaged
  - batchsize (avg): per-partition batch size
"""
from __future__ import annotations

from typing import Any

from prometheus_client import Gauge


class _ProducerMetrics:
    def __init__(self) -> None:
        self.in_flight = Gauge(
            "kafka_producer_in_flight_messages", "Producer in-flight messages"
        )
        self.queue_bytes = Gauge(
            "kafka_producer_queue_bytes", "Bytes queued in producer"
        )
        self.int_latency_avg_us = Gauge(
            "kafka_producer_int_latency_avg_us",
            "Average internal producer enqueue latency (µs)",
        )
        self.rtt_avg_us = Gauge(
            "kafka_producer_broker_rtt_avg_us",
            "Average broker RTT (µs), averaged across brokers",
        )
        self.batch_avg_bytes = Gauge(
            "kafka_producer_batch_size_avg_bytes",
            "Average produce batch size (bytes), averaged across topics",
        )

    def set_from_stats(self, stats: dict[str, Any]) -> None:
        self.in_flight.set(stats.get("msg_cnt", 0))
        self.queue_bytes.set(stats.get("msg_size", 0))

        int_latency = stats.get("int_latency", {})
        if isinstance(int_latency, dict):
            self.int_latency_avg_us.set(int_latency.get("avg", 0))

        # brokers -> { "<id>": { rtt: {avg: ...} } }
        brokers = stats.get("brokers", {})
        rtts = [
            b.get("rtt", {}).get("avg", 0) for b in brokers.values()
            if isinstance(b, dict)
        ]
        if rtts:
            self.rtt_avg_us.set(sum(rtts) / len(rtts))

        # topics -> partitions -> batchsize.avg
        topics = stats.get("topics", {})
        batch_avgs: list[float] = []
        for t in topics.values():
            for p in t.get("partitions", {}).values():
                bs = p.get("batchsize", {})
                if isinstance(bs, dict) and bs.get("avg"):
                    batch_avgs.append(bs["avg"])
        if batch_avgs:
            self.batch_avg_bytes.set(sum(batch_avgs) / len(batch_avgs))


producer_metrics = _ProducerMetrics()
