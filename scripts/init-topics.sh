#!/usr/bin/env bash
# Create Kafka topics idempotently. Runs once at compose bring-up as the
# `topic-init` one-shot service.
set -euo pipefail

BOOTSTRAP="${KAFKA_BOOTSTRAP:-kafka:29092}"

# Wait for Kafka to accept connections (in case healthcheck races)
for _ in $(seq 1 30); do
  if kafka-broker-api-versions --bootstrap-server "$BOOTSTRAP" >/dev/null 2>&1; then
    break
  fi
  echo "[topic-init] waiting for kafka..."
  sleep 2
done

create_delete_topic() {
  local topic=$1 parts=$2 retention_ms=$3
  kafka-topics --bootstrap-server "$BOOTSTRAP" --create --if-not-exists \
    --topic "$topic" --partitions "$parts" --replication-factor 1 \
    --config "cleanup.policy=delete" \
    --config "retention.ms=$retention_ms"
}

# Domain topics (retention per plan §A)
create_delete_topic anduin.satellite.position.v1 12 86400000       # 24h
create_delete_topic anduin.satellite.pass.v1      6 604800000      # 7d
create_delete_topic anduin.satellite.anomaly.v1   3 2592000000     # 30d
create_delete_topic anduin.sky.hot_cells.v1       3 3600000        # 1h (Flink output)

# DLQ topics — 30d retention
create_delete_topic anduin.satellite.position.v1.dlq 1 2592000000
create_delete_topic anduin.satellite.tle.v1.dlq      1 2592000000
create_delete_topic anduin.satellite.pass.v1.dlq     1 2592000000
create_delete_topic anduin.satellite.anomaly.v1.dlq  1 2592000000

# TLE topic is log-compacted (keyed by norad_id)
kafka-topics --bootstrap-server "$BOOTSTRAP" --create --if-not-exists \
  --topic anduin.satellite.tle.v1 --partitions 1 --replication-factor 1 \
  --config "cleanup.policy=compact" \
  --config "retention.ms=2592000000" \
  --config "min.cleanable.dirty.ratio=0.1" \
  --config "segment.ms=3600000"

echo "[topic-init] done. Topics:"
kafka-topics --bootstrap-server "$BOOTSTRAP" --list | grep '^anduin\.' | sort
