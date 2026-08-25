import os
import sys
import pickle
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score

# 1. Add parent directory to sys.path to allow local imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# 2. Clean sys.path COMPLETELY of any paths containing spaces temporarily
saved_sys_path = list(sys.path)
sys.path = [p for p in sys.path if " " not in p]

# 3. Import stream_processor (which imports PySpark)
from streaming.stream_processor import get_spark_session

# 4. Restore sys.path
sys.path = saved_sys_path

def train_demand_prediction_model(gold_path="data/delta/gold_surge_rates", model_output_path="ml/demand_model.pkl"):
    """
    Simulates a machine learning pipeline inside Databricks.
    Reads features directly from the Delta Gold Table, performs feature engineering,
    trains a demand/surge prediction model, and saves it (simulating MLflow tracking).
    """
    spark = get_spark_session()
    spark.sparkContext.setLogLevel("WARN")
    
    print(f"[*] Loading training data from Delta Gold Table at {gold_path}...")
    
    # 1. Read features from Gold Delta table
    if not os.path.exists(gold_path):
        print(f"[!] Delta Gold table not found at {gold_path}. Cannot train model.")
        return
        
    df_spark = spark.read.format("delta").load(gold_path)
    
    # Check if we have enough data
    count = df_spark.count()
    print(f"[*] Found {count} records in Delta Gold table.")
    if count < 5:
        print("[!] Insufficient data for training. Run stream/batch pipelines first to populate tables.")
        return
        
    # 2. Convert to Pandas for local Scikit-Learn training (common for small/medium tabular datasets)
    df = df_spark.toPandas()
    
    # 3. Feature Engineering
    print("[*] Performing feature engineering...")
    # Extract temporal features
    df["window_start"] = pd.to_datetime(df["window_start"])
    df["hour"] = df["window_start"].dt.hour
    df["day_of_week"] = df["window_start"].dt.dayofweek
    
    # Categorical encoding for cities
    df["city_code"] = df["city"].astype("category").cat.codes
    
    # Features and Target
    # Predicting surge multiplier based on ride demand (ride_count), hour, and city
    X = df[["ride_count", "hour", "day_of_week", "city_code"]]
    y = df["surge_multiplier"]
    
    print("[*] Training dataset features sample:")
    print(X.head())
    
    # 4. Train/Test Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # 5. Model Training
    print("[*] Fitting Linear Regression model...")
    model = LinearRegression()
    model.fit(X_train, y_train)
    
    # 6. Evaluation
    predictions = model.predict(X_test)
    mse = mean_squared_error(y_test, predictions)
    r2 = r2_score(y_test, predictions)
    print(f"[+] Model Evaluation Results:")
    print(f"    - Mean Squared Error (MSE): {mse:.4f}")
    print(f"    - R-squared (R2 Score): {r2:.4f}")
    print(f"    - Coefficients: {model.coef_}")
    print(f"    - Intercept: {model.intercept_}")
    
    # 7. Save Model (Simulating MLflow registry artifact)
    os.makedirs(os.path.dirname(model_output_path), exist_ok=True)
    with open(model_output_path, "wb") as f:
        pickle.dump(model, f)
    print(f"[+] Model artifact registered and saved locally at {model_output_path}")

if __name__ == "__main__":
    train_demand_prediction_model()
