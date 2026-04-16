from kafka import KafkaProducer
import json, time, random

producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

cities = ["Bangalore", "Hyderabad", "Delhi", "Mumbai", "Chennai"]

while True:
    ride = {
        "ride_id": random.randint(10000, 99999),
        "city": random.choice(cities),
        "timestamp": time.time(),
        "distance_km": round(random.uniform(1, 20), 2),
        "base_fare": 50
    }
    producer.send("uber_rides", ride)
    time.sleep(1)
