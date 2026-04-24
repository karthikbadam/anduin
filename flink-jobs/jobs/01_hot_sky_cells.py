"""01_hot_sky_cells — tumbling per-minute count of distinct satellites per
HEALPix cell, written to a JSON Kafka topic for query-api to cache in Redis.

Source: anduin.satellite.position.v1 (Avro-Confluent)
Sink:   anduin.sky.hot_cells.v1   (JSON)
  payload: {"cell": long, "window_end_ms": long, "n_sats": long}

Watermark: envelope.occurred_at − 10 s. Windows are 1-minute tumbling.
"""
from pyflink.table import EnvironmentSettings, TableEnvironment


SOURCE_DDL = """
CREATE TABLE satellite_position (
    `envelope` ROW<
        `event_id` STRING,
        `event_version` INT,
        `occurred_at` TIMESTAMP_LTZ(3),
        `ingested_at` TIMESTAMP_LTZ(3),
        `source` STRING,
        `trace_id` STRING
    >,
    `norad_id` STRING,
    `name` STRING,
    `position` ROW<`lat_deg` DOUBLE, `lon_deg` DOUBLE, `alt_km` DOUBLE>,
    `speed_km_s` DOUBLE,
    `healpix_cell` BIGINT,
    `tle_epoch` TIMESTAMP_LTZ(3),
    `sampled_at` TIMESTAMP_LTZ(3),
    `tle_source` STRING,
    `occurred_at` AS `envelope`.`occurred_at`,
    WATERMARK FOR `occurred_at` AS `occurred_at` - INTERVAL '10' SECOND
) WITH (
    'connector'                           = 'kafka',
    'topic'                               = 'anduin.satellite.position.v1',
    'properties.bootstrap.servers'        = 'kafka:29092',
    'properties.group.id'                 = 'anduin.flink.hot-sky-cells',
    'scan.startup.mode'                   = 'latest-offset',
    'format'                              = 'avro-confluent',
    'avro-confluent.url'                  = 'http://schema-registry:8081'
)
"""

SINK_DDL = """
CREATE TABLE hot_cells (
    `cell`          BIGINT,
    `window_end_ms` BIGINT,
    `n_sats`        BIGINT
) WITH (
    'connector'                    = 'kafka',
    'topic'                        = 'anduin.sky.hot_cells.v1',
    'properties.bootstrap.servers' = 'kafka:29092',
    'format'                       = 'json'
)
"""

QUERY = """
INSERT INTO hot_cells
SELECT
    `healpix_cell`                              AS `cell`,
    CAST(UNIX_TIMESTAMP(CAST(window_end AS TIMESTAMP)) AS BIGINT) * 1000
                                                AS `window_end_ms`,
    COUNT(DISTINCT `norad_id`)                  AS `n_sats`
FROM TABLE(
    TUMBLE(TABLE `satellite_position`, DESCRIPTOR(`occurred_at`), INTERVAL '1' MINUTE)
)
GROUP BY `healpix_cell`, `window_end`
"""


def main() -> None:
    settings = EnvironmentSettings.in_streaming_mode()
    t_env = TableEnvironment.create(settings)
    t_env.get_config().set("parallelism.default", "2")
    t_env.execute_sql(SOURCE_DDL)
    t_env.execute_sql(SINK_DDL)
    t_env.execute_sql(QUERY)


if __name__ == "__main__":
    main()
