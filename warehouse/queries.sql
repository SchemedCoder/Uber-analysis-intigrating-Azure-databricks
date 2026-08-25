-- ====================================================================
-- Databricks SQL / Delta Lake Query & Performance Tuning Examples
-- ====================================================================

USE CATALOG uber_catalog;
USE SCHEMA analytics;

-- 1. Analytics Query: Top Cities by Ride Count and Average Surge Pricing
-- Analyzes gold level aggregated data
SELECT 
    city,
    COUNT(*) as total_windows,
    SUM(ride_count) as total_rides,
    ROUND(AVG(surge_multiplier), 2) as avg_surge,
    MAX(surge_multiplier) as max_surge
FROM gold_surge_rates
GROUP BY city
ORDER BY total_rides DESC;

-- 2. Advanced Window Function: Identify peak surge window per city
WITH ranked_surge AS (
    SELECT 
        window_start,
        window_end,
        city,
        ride_count,
        surge_multiplier,
        DENSE_RANK() OVER (PARTITION BY city ORDER BY surge_multiplier DESC, ride_count DESC) as rank
    FROM gold_surge_rates
)
SELECT 
    window_start,
    window_end,
    city,
    ride_count,
    surge_multiplier
FROM ranked_surge
WHERE rank = 1;

-- 3. Delta Lake Time Travel (Audit & Debugging)
-- Query the Silver table at a specific historical point or transaction version
-- This is critical for data audits and debugging pipeline issues

-- Option A: View data as of a specific version
SELECT * FROM silver_rides VERSION AS OF 1 LIMIT 10;

-- Option B: View data as of a specific timestamp
SELECT * FROM silver_rides TIMESTAMP AS OF '2026-08-15 12:00:00' LIMIT 10;

-- Option C: Check table history/audit trail of operations (MERGE, WRITE, etc.)
DESCRIBE HISTORY silver_rides;

-- 4. Delta Lake Performance Optimization & Compaction
-- Compacts small files into larger 1GB files and co-locates data on disk
-- Z-Ordering by 'timestamp' optimizes queries filtering on time

-- Compact small files
OPTIMIZE silver_rides;

-- Compact and optimize layouts for fast queries on timestamp
OPTIMIZE silver_rides ZORDER BY (timestamp);

-- Clean up older files no longer in active transaction logs (older than 7 days by default)
-- WARNING: Running VACUUM prevents time traveling back past the retention threshold
VACUUM silver_rides RETAIN 168 HOURS;
