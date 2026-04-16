from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, window, count
from pyspark.sql.types import StructType, StringType, FloatType, IntegerType
from pyspark.sql.functions import udf
from pyspark.sql.types import FloatType
from surge_engine import calculate_surge

spark = SparkSession.builder.appName("UberStreaming").getOrCreate()

schema = StructType() \
    .add("ride_id", IntegerType()) \
    .add("city", StringType()) \
    .add("timestamp", FloatType()) \
    .add("distance_km", FloatType()) \
    .add("base_fare", FloatType())

df = spark.readStream.format("kafka") \
    .option("kafka.bootstrap.servers", "localhost:9092") \
    .option("subscribe", "uber_rides") \
    .load()

json_df = df.selectExpr("CAST(value AS STRING)")

rides = json_df.select(from_json(col("value"), schema).alias("data")).select("data.*")

rides = rides.withColumn("timestamp", col("timestamp").cast("timestamp"))

demand = rides.withWatermark("timestamp", "10 minutes") \
    .groupBy(window("timestamp", "5 minutes"), "city") \
    .agg(count("*").alias("ride_count"))

surge_udf = udf(lambda c, r: calculate_surge(c, r), FloatType())

result = demand.withColumn("surge_multiplier", surge_udf("city", "ride_count"))

query = result.writeStream.format("console").start()

query.awaitTermination()
