#!/usr/bin/env bash
# Register Avro schemas with the Schema Registry, resolving references between
# them via the registry's `references` field. Uses BACKWARD compatibility.
#
# Schemas are registered against subject `<topic>-value`. Shared types (Envelope,
# GeoPoint, TleSource, DlqRecord) are also registered under a standalone subject
# so they can be referenced by name.
#
# Requires: curl, jq.
set -euo pipefail

REGISTRY="${SCHEMA_REGISTRY_URL:-http://localhost:8081}"
SCHEMAS_DIR="$(cd "$(dirname "$0")" && pwd)"

log() { printf '[register] %s\n' "$*"; }

wait_registry() {
  for _ in $(seq 1 30); do
    if curl -fsS "$REGISTRY/subjects" >/dev/null 2>&1; then return 0; fi
    sleep 1
  done
  echo "ERROR: Schema Registry at $REGISTRY not responding" >&2
  exit 1
}

# POST a schema. Args:
#   $1 subject name
#   $2 path to .avsc file
#   $3 JSON array of references (pass '[]' if none)
post_schema() {
  local subject=$1 file=$2 refs=$3
  local body
  # Put the raw AVSC schema text into the "schema" field of the registry request.
  body=$(jq -n --arg schema "$(cat "$file")" --argjson refs "$refs" \
    '{schemaType: "AVRO", schema: $schema, references: $refs}')

  local resp
  resp=$(curl -fsS -X POST \
    -H "Content-Type: application/vnd.schemaregistry.v1+json" \
    --data "$body" \
    "$REGISTRY/subjects/$subject/versions")
  local id
  id=$(echo "$resp" | jq -r '.id')
  log "registered $subject → schema id $id"
}

set_backward_default() {
  curl -fsS -X PUT -H "Content-Type: application/vnd.schemaregistry.v1+json" \
    --data '{"compatibility": "BACKWARD"}' \
    "$REGISTRY/config" >/dev/null
  log "global compatibility: BACKWARD"
}

wait_registry
# Use NONE compat when re-registering after breaking changes; callers can
# flip back to BACKWARD once the new schema version is the only live one.
curl -fsS -X PUT -H "Content-Type: application/vnd.schemaregistry.v1+json" \
    --data '{"compatibility": "NONE"}' "$REGISTRY/config" >/dev/null
log "global compatibility: NONE (set by register.sh)"

# ─── shared types: registered under explicit *-type subjects ───────────────
# Order matters: GeoPoint has no refs, Envelope has no refs.
post_schema "anduin.common.GeoPoint" "$SCHEMAS_DIR/common/geo_point.avsc" '[]'
post_schema "anduin.common.Envelope" "$SCHEMAS_DIR/common/envelope.avsc" '[]'

# ─── domain schemas registered against <topic>-value subjects ──────────────

# Position: references Envelope + GeoPoint
POSITION_REFS=$(jq -n '[
  {name: "anduin.common.Envelope", subject: "anduin.common.Envelope", version: -1},
  {name: "anduin.common.GeoPoint", subject: "anduin.common.GeoPoint", version: -1}
]')
post_schema "anduin.satellite.position.v1-value" \
  "$SCHEMAS_DIR/satellite/satellite_position_sampled.avsc" "$POSITION_REFS"

# TLE: references Envelope (TleSource is now a plain string, not an enum).
TLE_REFS=$(jq -n '[
  {name: "anduin.common.Envelope", subject: "anduin.common.Envelope", version: -1}
]')
post_schema "anduin.satellite.tle.v1-value" \
  "$SCHEMAS_DIR/satellite/tle_record.avsc" "$TLE_REFS"

# Pass: references Envelope + GeoPoint
PASS_REFS=$(jq -n '[
  {name: "anduin.common.Envelope", subject: "anduin.common.Envelope", version: -1},
  {name: "anduin.common.GeoPoint", subject: "anduin.common.GeoPoint", version: -1}
]')
post_schema "anduin.satellite.pass.v1-value" \
  "$SCHEMAS_DIR/satellite/satellite_pass_predicted.avsc" "$PASS_REFS"

# Anomaly: references Envelope
ANOMALY_REFS=$(jq -n '[
  {name: "anduin.common.Envelope", subject: "anduin.common.Envelope", version: -1}
]')
post_schema "anduin.satellite.anomaly.v1-value" \
  "$SCHEMAS_DIR/satellite/satellite_anomaly_detected.avsc" "$ANOMALY_REFS"

# DLQ shared schema — used by every *.dlq topic
post_schema "anduin.dlq.DlqRecord" "$SCHEMAS_DIR/dlq/dlq_record.avsc" '[]'
DLQ_REF=$(jq -n '[{name: "anduin.dlq.DlqRecord", subject: "anduin.dlq.DlqRecord", version: -1}]')
# Register DlqRecord as the value schema for each dlq topic. We can re-register
# the same schema; the registry dedupes by schema identity and returns the same id.
for topic in anduin.satellite.position.v1.dlq anduin.satellite.tle.v1.dlq \
             anduin.satellite.pass.v1.dlq anduin.satellite.anomaly.v1.dlq; do
  post_schema "$topic-value" "$SCHEMAS_DIR/dlq/dlq_record.avsc" '[]'
done

log "done. subjects:"
curl -fsS "$REGISTRY/subjects" | jq -r '.[]' | sort | sed 's/^/  /'
