# Anduin

Real-time satellite tracking platform. Event-driven, schema-first, observable by default.


## Stage 1 quickstart

```bash
cp .env.example .env
make up                 # brings up kafka / schema-registry / redis / postgres + app services
make register-schemas   # POSTs Avro schemas with references resolved
open http://localhost:5173
```

`TLE_SOURCE=fixture` (the default) reads `tle-producer/fixtures/active.txt` if present, otherwise falls back to `fixtures/seed.txt` (ISS, Hubble, Tiangong). Run `make refresh-tle-fixture` once to fetch the full Celestrak snapshot. 

## Services

| Service | Port | Purpose |
|---|---|---|
| kafka | 9092 (host), 29092 (internal) | event backbone (KRaft, single node) |
| schema-registry | 8081 | Avro schema store (BACKWARD compat) |
| redis | 6379 | hot state (ZSETs, lists) |
| postgres | 5432 | cold store (partitioned) |
| ingest-api | 8000 | `POST /events/*` |
| query-api | 8001 | `GET /satellites/*` + `/ws/stream` (Stage 2) |
| frontend | 5173 (dev) / 80 (prod) | Vite + React + MapLibre + Deck.gl |

## Stages

- **Stage 1 ✅**: ingest + propagate + live map
- **Stage 2**: WebSocket streaming + hot cells + pass prediction
- **Stage 3**: anomaly detection + full observability

Each stage ends with a reviewable demo and 1–3 algorithm functions stubbed `# TODO(me)` with precise I/O contracts and equations.

## Current state

Stage 1 pipeline runs end-to-end at ~11k satellites. To resume:

```bash
make up                     # backbone + all services
make register-schemas       # only needed if volumes got wiped
open http://localhost:5180  # live map
```

Dev API key `dev-key-anduin-local-only` (sha256-hashed in Postgres; rate limit bumped in-DB from 120 → 30000 rpm to support full-catalog ingest). `TLE_SOURCE=fixture` by default; `tle-producer/fixtures/active.txt` (gitignored) is the full catalog from `make refresh-tle-fixture`.

TODO(me) stubs still unfilled: `tle-producer/app/propagate.py::propagate_position` and `tle-producer/app/healpix.py::lonlat_to_healpix`. Set `STUB_PROPAGATE=false` once implemented.
