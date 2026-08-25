-- Databricks Unity Catalog & Delta Lake Schema Definition
-- In production, these tables are managed Delta Tables in Unity Catalog

CREATE CATALOG IF NOT EXISTS uber_catalog;
USE CATALOG uber_catalog;

CREATE SCHEMA IF NOT EXISTS analytics;
USE SCHEMA analytics;

-- 1. Bronze Table (Raw ingestion replica, schema-on-read payload)
CREATE TABLE IF NOT EXISTS bronze_rides (
    json_payload STRING,
    ingested_at TIMESTAMP,
    source_origin STRING
)
USING DELTA
TBLPROPERTIES (
    'delta.appendOnly' = 'true',
    'delta.minReaderVersion' = '1',
    'delta.minWriterVersion' = '2'
);

-- 2. Silver Table (Cleaned, parsed, conformed data - conformed star schema representation)
CREATE TABLE IF NOT EXISTS silver_rides (
    ride_id INT,
    city STRING,
    timestamp TIMESTAMP,
    distance_km DOUBLE,
    base_fare DOUBLE,
    ingested_at TIMESTAMP,
    source_origin STRING
)
USING DELTA
PARTITIONED BY (city)
TBLPROPERTIES (
    'delta.autoOptimize.optimizeWrite' = 'true',
    'delta.autoOptimize.autoCompact' = 'true'
);

-- 3. Gold Table (Aggregated surge pricing metrics for BI reporting)
CREATE TABLE IF NOT EXISTS gold_surge_rates (
    window_start TIMESTAMP,
    window_end TIMESTAMP,
    city STRING,
    ride_count LONG,
    surge_multiplier DOUBLE,
    calculated_at TIMESTAMP
)
USING DELTA;
