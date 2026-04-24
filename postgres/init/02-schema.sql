-- Core anduin schema. Partitioning for satellite_positions is monthly on
-- sampled_at; partitions are created manually here for the current and next
-- two months, with a weekly cron (documented in README) creating new ones.

BEGIN;

-- ─────────────────────────── satellites ────────────────────────────
CREATE TABLE IF NOT EXISTS satellites (
  norad_id        TEXT PRIMARY KEY,
  name            TEXT,
  classification  TEXT,
  last_tle_epoch  TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─────────────────────── satellite_positions ───────────────────────
-- Partitioned monthly on sampled_at. The parent table is unlogged-adjacent
-- in sizing impact; ensure the PK covers partitioning column.
CREATE TABLE IF NOT EXISTS satellite_positions (
  norad_id       TEXT NOT NULL,
  sampled_at     TIMESTAMPTZ NOT NULL,
  lat_deg        DOUBLE PRECISION NOT NULL,
  lon_deg        DOUBLE PRECISION NOT NULL,
  alt_km         DOUBLE PRECISION NOT NULL,
  speed_km_s     DOUBLE PRECISION NOT NULL,
  healpix_cell   BIGINT NOT NULL,
  tle_epoch      TIMESTAMPTZ,
  tle_source     TEXT,
  PRIMARY KEY (norad_id, sampled_at)
) PARTITION BY RANGE (sampled_at);

CREATE INDEX IF NOT EXISTS satellite_positions_by_cell
  ON satellite_positions (healpix_cell, sampled_at DESC);

-- Default partition (catch-all; future hard-dated partitions override it).
CREATE TABLE IF NOT EXISTS satellite_positions_default
  PARTITION OF satellite_positions DEFAULT;

-- Helper function to create a month partition idempotently.
CREATE OR REPLACE FUNCTION ensure_positions_partition(p_month DATE)
RETURNS VOID AS $$
DECLARE
  part_name TEXT := 'satellite_positions_' || to_char(p_month, 'YYYY_MM');
  range_from DATE := date_trunc('month', p_month)::DATE;
  range_to   DATE := (date_trunc('month', p_month) + INTERVAL '1 month')::DATE;
BEGIN
  EXECUTE format(
    'CREATE TABLE IF NOT EXISTS %I PARTITION OF satellite_positions
       FOR VALUES FROM (%L) TO (%L)',
    part_name, range_from, range_to
  );
END $$ LANGUAGE plpgsql;

-- Pre-create current + next 2 months so the pipeline has somewhere to land.
SELECT ensure_positions_partition(now()::date);
SELECT ensure_positions_partition((now() + INTERVAL '1 month')::date);
SELECT ensure_positions_partition((now() + INTERVAL '2 months')::date);

-- ────────────────────────────── passes ─────────────────────────────
CREATE TABLE IF NOT EXISTS passes (
  id             BIGSERIAL PRIMARY KEY,
  norad_id       TEXT NOT NULL,
  observer_id    TEXT NOT NULL,
  observer_lat   DOUBLE PRECISION NOT NULL,
  observer_lon   DOUBLE PRECISION NOT NULL,
  rise_at        TIMESTAMPTZ NOT NULL,
  culmination_at TIMESTAMPTZ,
  set_at         TIMESTAMPTZ,
  max_elev_deg   DOUBLE PRECISION,
  az_rise_deg    DOUBLE PRECISION,
  az_set_deg     DOUBLE PRECISION,
  visible        BOOLEAN,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS passes_observer_rise  ON passes (observer_id, rise_at);
CREATE INDEX IF NOT EXISTS passes_norad_rise     ON passes (norad_id, rise_at);

-- ──────────────────────────── anomalies ────────────────────────────
CREATE TABLE IF NOT EXISTS anomalies (
  id            BIGSERIAL PRIMARY KEY,
  norad_id      TEXT NOT NULL,
  anomaly_type  TEXT NOT NULL,            -- conjunction | orbit_decay | tle_stale | reentry | maneuver
  severity      TEXT NOT NULL,            -- info | warn | critical
  detected_at   TIMESTAMPTZ NOT NULL,
  evidence      JSONB NOT NULL DEFAULT '{}',
  trace_id      TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS anomalies_by_detected_at ON anomalies (detected_at DESC);
CREATE INDEX IF NOT EXISTS anomalies_by_type        ON anomalies (anomaly_type, detected_at DESC);

-- ──────────────────────────── api_keys ─────────────────────────────
CREATE TABLE IF NOT EXISTS api_keys (
  key_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  key_hash         BYTEA NOT NULL UNIQUE,   -- sha256 of the raw key
  owner            TEXT NOT NULL,
  scopes           TEXT[] NOT NULL DEFAULT '{}',
  rate_per_minute  INT NOT NULL DEFAULT 120,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  disabled_at      TIMESTAMPTZ
);

-- ────────────────── rate_limit_events (optional audit) ─────────────
CREATE TABLE IF NOT EXISTS rate_limit_events (
  id           BIGSERIAL PRIMARY KEY,
  key_id       UUID NOT NULL,
  endpoint     TEXT NOT NULL,
  status       INT NOT NULL,
  occurred_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─────────────────────────── dlq_events ────────────────────────────
CREATE TABLE IF NOT EXISTS dlq_events (
  id              BIGSERIAL PRIMARY KEY,
  original_topic  TEXT NOT NULL,
  failure_reason  TEXT NOT NULL,
  failure_stage   TEXT NOT NULL,
  failed_at       TIMESTAMPTZ NOT NULL,
  original_key    BYTEA,
  original_value  BYTEA,
  headers         JSONB NOT NULL DEFAULT '{}',
  trace_id        TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS dlq_events_by_topic_time
  ON dlq_events (original_topic, failed_at DESC);

COMMIT;
