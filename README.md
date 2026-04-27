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

