import os
import sys

# Add parent directory to sys.path to allow local imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import local modules first
from streaming.surge_engine import get_spark_surge_expression

# Clean sys.path COMPLETELY of any elements containing spaces.
# This bypasses the Windows PySpark JVM launch bug when directory paths contain spaces.
saved_sys_path = list(sys.path)
sys.path = [p for p in sys.path if " " not in p]

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, window, count, current_timestamp, input_file_name
from pyspark.sql.types import StructType, StringType, DoubleType, IntegerType, TimestampType

# Restore sys.path
sys.path = saved_sys_path

def get_spark_session():
    """
    Creates a local Spark Session pre-configured for Delta Lake and Windows compatibility.
    To avoid Windows space-in-path issues with spark-submit, Delta JARs are downloaded
    directly from Maven Central and loaded as local Spark Jars.
    """
    import urllib.request
    import pyspark
    version = pyspark.__version__
    
    # Map PySpark versions to compatible Delta Lake jar versions
    if version.startswith("3.5"):
        delta_ver = "3.1.0"
    elif version.startswith("3.4"):
        delta_ver = "2.4.0"
    else:
        delta_ver = "3.1.0"  # Default fallback
        
    print(f"[*] Detected PySpark version: {version}. Using Delta Lake version: {delta_ver}")
    
    # Local Jars directory path
    jars_dir = "jars"
    os.makedirs(jars_dir, exist_ok=True)
    
    jars = {
        f"delta-spark_2.12-{delta_ver}.jar": f"https://repo1.maven.org/maven2/io/delta/delta-spark_2.12/{delta_ver}/delta-spark_2.12-{delta_ver}.jar",
        f"delta-storage-{delta_ver}.jar": f"https://repo1.maven.org/maven2/io/delta/delta-storage/{delta_ver}/delta-storage-{delta_ver}.jar"
    }
    
    local_jar_paths = []
    for jar_name, url in jars.items():
        dest_path = os.path.join(jars_dir, jar_name)
        local_jar_paths.append(dest_path)
        if not os.path.exists(dest_path):
            print(f"[*] Downloading Delta JAR {jar_name} from Maven Central...")
            try:
                urllib.request.urlretrieve(url, dest_path)
                print(f"[+] Downloaded {jar_name}")
            except Exception as e:
                print(f"[!] Error downloading {jar_name}: {e}")
                
    jar_config = ",".join(local_jar_paths)
    
    # Configure directories for local running to prevent locks and permission issues on Windows
    warehouse_dir = "data/spark-warehouse"
    derby_dir = "data/derby"
    
    # Clean sys.path of any elements containing spaces permanently to bypass Windows PySpark JVM launch bug
    sys.path = [p for p in sys.path if " " not in p]
    
    # Clean environment variables containing spaces/quotes to prevent Windows spark-class2.cmd parser failure
    for k in list(os.environ.keys()):
        if k.startswith("ANTIGRAVITY_"):
            del os.environ[k]
            
    # Attempt to load Azure Credentials from .env if they exist
    from dotenv import load_dotenv
    load_dotenv()
    
    tenant_id = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")
    storage_account = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
    
    spark_builder = SparkSession.builder \
        .appName("UberMedallionStreaming") \
        .config("spark.jars", jar_config) \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .config("spark.sql.warehouse.dir", warehouse_dir) \
        .config("spark.driver.extraJavaOptions", f"-Dderby.system.home={derby_dir}") \
        .config("spark.sql.shuffle.partitions", "4")
        
    # Configure Azure ADLS Gen2 connections if credentials are provided
    if all([tenant_id, client_id, client_secret, storage_account]):
        print("[*] Azure credentials found. Configuring ABFSS (ADLS Gen2) connection...")
        spark_builder = spark_builder \
            .config(f"fs.azure.account.auth.type.{storage_account}.dfs.core.windows.net", "OAuth") \
            .config(f"fs.azure.account.oauth.provider.type.{storage_account}.dfs.core.windows.net", "org.apache.hadoop.fs.azurebfs.oauth2.ClientCredsTokenProvider") \
            .config(f"fs.azure.account.oauth2.client.id.{storage_account}.dfs.core.windows.net", client_id) \
            .config(f"fs.azure.account.oauth2.client.secret.{storage_account}.dfs.core.windows.net", client_secret) \
            .config(f"fs.azure.account.oauth2.client.endpoint.{storage_account}.dfs.core.windows.net", f"https://login.microsoftonline.com/{tenant_id}/oauth2/token")
    
    spark = spark_builder.getOrCreate()
        
    return spark


def run_pipeline(mode="file", target_limit=None):
    """
    Runs the Medallion streaming pipeline:
    1. Bronze Ingestion (Raw landing files / Kafka -> Bronze Delta Table)
    2. Silver Processing (Bronze Delta -> Clean, Deduplicate, Cast -> Silver Delta Table)
    3. Gold Aggregation (Silver Delta -> Stateful Window aggregates -> Gold Delta Table)
    """
    spark = get_spark_session()
    spark.sparkContext.setLogLevel("WARN")
    
    print(f"[*] Starting streaming processor in '{mode}' mode...")
    
    # Directories
    bronze_path = "data/delta/bronze_rides"
    silver_path = "data/delta/silver_rides"
    gold_path = "data/delta/gold_surge_rates"
    
    checkpoint_bronze = "data/delta/checkpoints/bronze"
    checkpoint_silver = "data/delta/checkpoints/silver"
    checkpoint_gold = "data/delta/checkpoints/gold"
    
    # Ensure directory structures and initialize Delta tables if they don't exist
    # This prevents DELTA_SCHEMA_NOT_SET errors when reading streams from empty folders.
    os.makedirs("data/raw_landing", exist_ok=True)
    
    from pyspark.sql.types import LongType
    
    # 1. Initialize Bronze Delta Table if not exists
    bronze_schema = StructType() \
        .add("json_payload", StringType()) \
        .add("ingested_at", TimestampType()) \
        .add("source_origin", StringType())
        
    if not os.path.exists(bronze_path) or not os.listdir(bronze_path):
        print("[*] Initializing empty Bronze Delta Table...")
        spark.createDataFrame(spark.sparkContext.emptyRDD(), bronze_schema) \
            .write.format("delta").mode("overwrite").save(bronze_path)
            
    # 2. Initialize Silver Delta Table if not exists
    silver_init_schema = StructType() \
        .add("ride_id", IntegerType()) \
        .add("city", StringType()) \
        .add("timestamp", TimestampType()) \
        .add("distance_km", DoubleType()) \
        .add("base_fare", DoubleType()) \
        .add("ingested_at", TimestampType()) \
        .add("source_origin", StringType())
        
    if not os.path.exists(silver_path) or not os.listdir(silver_path):
        print("[*] Initializing empty Silver Delta Table...")
        spark.createDataFrame(spark.sparkContext.emptyRDD(), silver_init_schema) \
            .write.format("delta").mode("overwrite").partitionBy("city").save(silver_path)
            
    # 3. Initialize Gold Delta Table if not exists
    gold_schema = StructType() \
        .add("window_start", TimestampType()) \
        .add("window_end", TimestampType()) \
        .add("city", StringType()) \
        .add("ride_count", LongType()) \
        .add("surge_multiplier", DoubleType()) \
        .add("calculated_at", TimestampType())
        
    if not os.path.exists(gold_path) or not os.listdir(gold_path):
        print("[*] Initializing empty Gold Delta Table...")
        spark.createDataFrame(spark.sparkContext.emptyRDD(), gold_schema) \
            .write.format("delta").mode("overwrite").save(gold_path)
    
    # ----------------------------------------------------
    # BRONZE LAYER: Ingest raw JSON payloads
    # ----------------------------------------------------
    if mode == "file":
        # Simulates Databricks Auto Loader (cloudFiles) by reading directory stream
        input_schema = StructType().add("value", StringType()) # dummy reading as raw text lines
        raw_stream = spark.readStream \
            .format("text") \
            .load("data/raw_landing")
        
        bronze_df = raw_stream.select(
            col("value").alias("json_payload"),
            current_timestamp().alias("ingested_at"),
            input_file_name().alias("source_origin")
        )
    else:
        # Kafka mode
        raw_stream = spark.readStream \
            .format("kafka") \
            .option("kafka.bootstrap.servers", "localhost:9092") \
            .option("subscribe", "uber_rides") \
            .load()
            
        bronze_df = raw_stream.select(
            col("value").cast("string").alias("json_payload"),
            current_timestamp().alias("ingested_at"),
            col("topic").alias("source_origin")
        )

    # Write raw stream to Bronze Delta Table
    query_bronze = bronze_df.writeStream \
        .format("delta") \
        .outputMode("append") \
        .option("checkpointLocation", checkpoint_bronze) \
        .start(bronze_path)
        
    print("[*] Bronze ingestion streaming query started.")

    # ----------------------------------------------------
    # SILVER LAYER: Parse, Clean, Validate & Deduplicate
    # ----------------------------------------------------
    # Schema for the JSON payload
    payload_schema = StructType() \
        .add("ride_id", IntegerType()) \
        .add("city", StringType()) \
        .add("timestamp", DoubleType()) \
        .add("distance_km", DoubleType()) \
        .add("base_fare", DoubleType())

    # Read from Bronze Delta Table as a stream
    bronze_delta_stream = spark.readStream \
        .format("delta") \
        .load(bronze_path)

    # Parse and clean
    parsed_stream = bronze_delta_stream.select(
        from_json(col("json_payload"), payload_schema).alias("data"),
        col("ingested_at")
    ).select("data.*", "ingested_at")

    # Clean data (remove corrupt events, cast timestamps, add watermarks, and deduplicate)
    clean_stream = parsed_stream \
        .filter("ride_id IS NOT NULL AND distance_km > 0 AND base_fare > 0") \
        .withColumn("timestamp", col("timestamp").cast(TimestampType())) \
        .withWatermark("timestamp", "10 minutes") \
        .dropDuplicates(["ride_id", "timestamp"])

    # Write cleaned stream to Silver Delta Table, partitioned by city
    query_silver = clean_stream.writeStream \
        .format("delta") \
        .outputMode("append") \
        .partitionBy("city") \
        .option("checkpointLocation", checkpoint_silver) \
        .start(silver_path)

    print("[*] Silver processing streaming query started.")

    # ----------------------------------------------------
    # GOLD LAYER: Stateful aggregation & Business Logic
    # ----------------------------------------------------
    # Read from Silver Delta Table as a stream
    silver_delta_stream = spark.readStream \
        .format("delta") \
        .load(silver_path)

    # Calculate 5-minute window demand (stateful aggregation)
    windowed_demand = silver_delta_stream \
        .withWatermark("timestamp", "10 minutes") \
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
        )

    # Calculate surge multiplier using optimized Spark SQL expression
    gold_df = windowed_demand.withColumn(
        "surge_multiplier", 
        get_spark_surge_expression("city", "ride_count")
    ).withColumn("calculated_at", current_timestamp())

    # Write Gold stream to Gold Delta Table in append mode
    # Note: Append mode is supported for windowed aggregation when watermarking is defined
    query_gold = gold_df.writeStream \
        .format("delta") \
        .outputMode("append") \
        .option("checkpointLocation", checkpoint_gold) \
        .start(gold_path)

    print("[*] Gold aggregation streaming query started.")

    # Block until termination
    if target_limit:
        # If running as part of orchestrator, let it run for a specific duration
        print(f"[*] Pipeline will run for {target_limit} seconds to process files...")
        try:
            query_gold.awaitTermination(target_limit)
        except Exception:
            pass
        finally:
            query_bronze.stop()
            query_silver.stop()
            query_gold.stop()
            print("[*] Streaming queries stopped.")
    else:
        # Block indefinitely
        spark.streams.awaitAnyTermination()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Uber Medallion Stream Processor")
    parser.add_argument("--mode", choices=["file", "kafka"], default="file", help="Ingestion source mode")
    parser.add_argument("--duration", type=int, default=None, help="Run duration in seconds before exiting")
    args = parser.parse_args()
    
    run_pipeline(mode=args.mode, target_limit=args.duration)
