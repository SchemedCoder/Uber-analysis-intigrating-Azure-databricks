from pyspark.sql import SparkSession
from pyspark.sql.functions import window, count, col
from streaming.surge_engine import calculate_surge
from pyspark.sql.functions import udf
from pyspark.sql.types import FloatType

spark = SparkSession.builder.appName("RebuildPipeline").getOrCreate()

df = spark.read.json("data/raw.json")

df = df.withColumn("timestamp", col("timestamp").cast("timestamp"))

demand = df.groupBy(window("timestamp", "5 minutes"), "city") \
    .agg(count("*").alias("ride_count"))

surge_udf = udf(lambda c, r: calculate_surge(c, r), FloatType())

final_df = demand.withColumn("surge_multiplier", surge_udf("city", "ride_count"))

final_df.write.mode("overwrite").parquet("data/gold/")
