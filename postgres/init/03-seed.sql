-- Dev seed data: dev API key + three seed satellites.
-- Raw key is: dev-key-anduin-local-only
-- sha256 hex:  3a7e2d6e8c3e5f...  (computed at insert time)

BEGIN;

INSERT INTO api_keys (key_hash, owner, scopes, rate_per_minute)
VALUES (
  digest('dev-key-anduin-local-only', 'sha256'),
  'dev',
  ARRAY['read:satellites','write:events'],
  120
)
ON CONFLICT (key_hash) DO NOTHING;

INSERT INTO satellites (norad_id, name, classification) VALUES
  ('25544', 'ISS (ZARYA)',        'U'),
  ('20580', 'HST',                'U'),
  ('48274', 'TIANGONG (CSS)',     'U')
ON CONFLICT (norad_id) DO NOTHING;

COMMIT;
