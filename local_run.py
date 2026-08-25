import os
import sys

# 1. Clean sys.path temporarily of any elements containing spaces
# This forces PySpark to cache a clean space-free classpath during import.
saved_sys_path = list(sys.path)
sys.path = [p for p in sys.path if " " not in p]

# 2. Import PySpark and SparkSession now
import pyspark
from pyspark.sql import SparkSession

# 3. Restore sys.path to include workspace path for local imports
sys.path = saved_sys_path
workspace_dir = os.getcwd()
if workspace_dir not in sys.path:
    sys.path.insert(0, workspace_dir)

# 4. Import ALL local modules
import local_generator
from streaming import stream_processor
from batch import reconstruction
from ml import demand_model

# 5. Clean sys.path COMPLETELY of any elements containing spaces and keep it clean
# This ensures that when SparkSession.builder.getOrCreate() is called, JVM starts without spaces.
sys.path = [p for p in sys.path if " " not in p]

import shutil
import time
import threading
import json



def clear_data():
    """
    Cleans up all data directories to ensure a clean end-to-end run.
    """
    paths_to_clean = ["data/delta", "data/raw_landing", "data/raw_batch", "data/spark-warehouse", "data/derby", "ml/demand_model.pkl"]
    print("[*] Cleaning up previous data files...")
    for path in paths_to_clean:
        if os.path.exists(path):
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                print(f"    - Cleaned: {path}")
            except Exception as e:
                print(f"    - [Warning] Could not clean {path}: {e}")

def create_historical_batch_data():
    """
    Creates mock historical batch files for the backfill pipeline.
    """
    os.makedirs("data/raw_batch", exist_ok=True)
    batch_file = "data/raw_batch/historical_rides.json"
    
    print("[*] Generating historical batch data for backfill demo...")
    
    # Create 50 historical rides
    import random
    cities = ["Bangalore", "Hyderabad", "Delhi", "Mumbai", "Chennai"]
    rides = []
    base_time = time.time() - 3600  # 1 hour ago
    
    for i in range(50):
        rides.append({
            "ride_id": random.randint(100000, 999999),
            "city": random.choice(cities),
            "timestamp": base_time + (i * 30),  # spaced out by 30s
            "distance_km": round(random.uniform(2.0, 15.0), 2),
            "base_fare": round(random.uniform(50.0, 120.0), 2)
        })
        
    with open(batch_file, "w") as f:
        for r in rides:
            f.write(json.dumps(r) + "\n")
            
    print(f"[+] Written 50 historical events to {batch_file}")

def main():
    print("====================================================================")
    print("       UBER REAL-TIME DEMAND & SURGE PRICING PLATFORM DEMO")
    print("====================================================================")
    
    # 1. Clean up and setup directories
    clear_data()
    create_historical_batch_data()
    
    # 2. Start the File Generator in the background
    # It will write JSON files to 'data/raw_landing' every 1.5 seconds.
    generator_thread = threading.Thread(
        target=local_generator.start_file_generator,
        kwargs={"target_dir": "data/raw_landing", "delay": 1.5, "max_files": 12},
        daemon=True
    )
    generator_thread.start()
    
    # Let the generator write a couple of files first
    print("[*] Waiting for generator to create initial files...")
    time.sleep(4)
    
    # 3. Run Spark Medallion Stream Processor
    # We run it for 20 seconds, which is enough to process the 12 generated files
    print("\n----------------------------------------------------")
    print("   STAGE 1: Running Medallion Streaming Pipeline")
    print("----------------------------------------------------")
    
    # This will run Spark streaming, write to Bronze, Silver, and Gold delta tables
    stream_processor.run_pipeline(mode="file", target_limit=25)
    
    print("\n----------------------------------------------------")
    print("   STAGE 2: Running Historical Batch Backfill")
    print("----------------------------------------------------")
    # 4. Run reconstruction / backfill pipeline
    # This will merge historical batch records into the Silver table and rebuild Gold
    reconstruction.run_backfill()
    
    print("\n----------------------------------------------------")
    print("   STAGE 3: Training Demand/Surge Prediction Model")
    print("----------------------------------------------------")
    # 5. Run the ML pipeline
    # This will load the Gold Delta table, train a Linear Regression model and save it
    demand_model.train_demand_prediction_model()
    
    print("\n----------------------------------------------------")
    print("   STAGE 4: Querying Delta Tables (Gold Reporting)")
    print("----------------------------------------------------")
    # 6. Read and print the final Gold Delta table to display aggregated surge pricing
    spark = stream_processor.get_spark_session()
    
    gold_path = "data/delta/gold_surge_rates"
    silver_path = "data/delta/silver_rides"
    
    if os.path.exists(gold_path):
        print("\n[+] Displaying Gold Delta Table content (Surge Multiplier Aggregates):")
        gold_df = spark.read.format("delta").load(gold_path)
        gold_df.orderBy("city", "window_start").show(truncate=False)
        
        print("[+] Verifying Data Lineage (Silver Table Count vs Gold Aggregated Rides):")
        silver_df = spark.read.format("delta").load(silver_path)
        total_silver = silver_df.count()
        total_gold_rides = gold_df.agg({"ride_count": "sum"}).collect()[0][0]
        print(f"    - Total rides processed in Silver table: {total_silver}")
        print(f"    - Total rides aggregated in Gold table: {total_gold_rides}")
    else:
        print("[!] Delta Gold table was not created. Check Spark streaming logs.")
        
    print("\n====================================================================")
    print("                     DEMO RUN COMPLETED SUCCESSFULLY")
    print("====================================================================")
    print("[*] To run SQL queries on Delta tables, open the Spark Shell or use spark.read.")

if __name__ == "__main__":
    main()
