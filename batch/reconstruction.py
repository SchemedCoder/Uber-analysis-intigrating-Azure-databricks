import os
import sys

# 1. Add parent directory to sys.path to allow local imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# 2. Import local modules first (so they are loaded and cached)
from streaming.stream_processor import get_spark_session
from streaming.surge_engine import get_spark_surge_expression

# 3. Clean sys.path COMPLETELY of any paths containing spaces
# This bypasses the Windows PySpark JVM launch bug when directory paths contain spaces.
saved_sys_path = list(sys.path)
sys.path = [p for p in sys.path if " " not in p]

# 4. Import PySpark/SparkSession
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, current_timestamp, lit
from pyspark.sql.types import StructType, StringType, DoubleType, IntegerType, TimestampType

# 5. Restore sys.path
sys.path = saved_sys_path

def run_backfill(batch_input_dir="data/raw_batch", silver_path="data/delta/silver_rides", gold_path="data/delta/gold_surge_rates"):
    """
    Simulates a production historical data reconstruction/backfill pipeline.
    It reads historical JSON logs, cleans them, and upserts (MERGE) them 
    into the Silver Delta Table, then updates the Gold aggregations.
    """
    spark = get_spark_session()
    spark.sparkContext.setLogLevel("WARN")
    
    print(f"[*] Starting historical backfill from {batch_input_dir}...")
    
    # 1. Read raw historical batch files
    if not os.path.exists(batch_input_dir) or not os.listdir(batch_input_dir):
        print(f"[!] No backfill source files found in {batch_input_dir}. Skipping.")
        return
        
    payload_schema = StructType() \
        .add("ride_id", IntegerType()) \
        .add("city", StringType()) \
        .add("timestamp", DoubleType()) \
        .add("distance_km", DoubleType()) \
        .add("base_fare", DoubleType())

    raw_batch_df = spark.read.json(batch_input_dir)
    
    # 2. Add audit columns & cast schema
    cleaned_batch_df = raw_batch_df \
        .filter("ride_id IS NOT NULL AND distance_km > 0 AND base_fare > 0") \
        .withColumn("timestamp", col("timestamp").cast(TimestampType())) \
        .withColumn("ingested_at", current_timestamp()) \
        .withColumn("source_origin", lit("historical_backfill")) \
        .dropDuplicates(["ride_id", "timestamp"])

    # 3. Delta Merge (Upsert) to Silver Table
    from delta.tables import DeltaTable
    
    # Check if target silver delta table exists
    if os.path.exists(silver_path) and DeltaTable.isDeltaTable(spark, silver_path):
        print(f"[*] Silver Delta table exists at {silver_path}. Performing MERGE (upsert)...")
        silver_table = DeltaTable.forPath(spark, silver_path)
        
        silver_table.alias("target") \
            .merge(
                source=cleaned_batch_df.alias("source"),
                condition="target.ride_id = source.ride_id AND target.timestamp = source.timestamp"
            ) \
            .whenMatchedUpdateAll() \
            .whenNotMatchedInsertAll() \
            .execute()
        print("[*] Delta MERGE completed successfully.")
    else:
        print(f"[*] Target Silver Delta table does not exist. Initializing write at {silver_path}...")
        cleaned_batch_df.write \
            .format("delta") \
            .mode("overwrite") \
            .partitionBy("city") \
            .save(silver_path)
        print("[*] Silver Delta table initialized.")

    # 4. Rebuild Gold Aggregations from the Silver table
    print("[*] Rebuilding Gold Aggregations table from cleaned Silver data...")
    silver_df = spark.read.format("delta").load(silver_path)
    
    # Group by 5-minute windows and city
    from pyspark.sql.functions import window, count
    gold_rebuilt_df = silver_df \
        .groupBy(
            window(col("timestamp"), "5 minutes").alias("time_window"),
            col("city")
        ) \
        .agg(count("*").alias("ride_count")) \
        .select(
            col("time_window.start").alias("window_start"),
            col("time_window.end").alias("window_end"),
            col("city"),
            col("ride_count")
        ) \
        .withColumn("surge_multiplier", get_spark_surge_expression("city", "ride_count")) \
        .withColumn("calculated_at", current_timestamp())

    # Write (Overwrite) backfilled aggregates to Gold Delta Table
    gold_rebuilt_df.write \
        .format("delta") \
        .mode("overwrite") \
        .save(gold_path)
        
    print(f"[*] Gold Aggregations rebuilt and written to {gold_path}.")

if __name__ == "__main__":
    # Create input dir if not exists
    os.makedirs("data/raw_batch", exist_ok=True)
    
    # Run the backfill pipeline
    run_backfill()
