import pandas as pd
from sklearn.linear_model import LinearRegression

df = pd.read_csv("data/demand.csv")

df["city_code"] = df["city"].astype("category").cat.codes

X = df[["ride_count", "hour", "city_code"]]
y = df["future_demand"]

model = LinearRegression()
model.fit(X, y)

print("Model trained")
