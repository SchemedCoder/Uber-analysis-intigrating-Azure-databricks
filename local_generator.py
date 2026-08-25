import os
import json
import time
import random
from datetime import datetime

cities = ["Bangalore", "Hyderabad", "Delhi", "Mumbai", "Chennai"]

def generate_ride_event():
    return {
        "ride_id": random.randint(100000, 999999),
        "city": random.choice(cities),
        "timestamp": time.time(),
        "distance_km": round(random.uniform(1.0, 25.0), 2),
        "base_fare": round(random.uniform(40.0, 150.0), 2)
    }

def generate_corrupted_event():
    # Occasionally inject bad data (missing ride_id or negative distance) to test clean-up pipeline
    event = generate_ride_event()
    if random.random() < 0.05:
        event["ride_id"] = None
    elif random.random() < 0.05:
        event["distance_km"] = -5.0
    return event

def start_file_generator(target_dir="data/raw_landing", delay=2.0, max_files=None):
    """
    Simulates real-time file landing by writing JSON files containing 
    micro-batches of ride events to a target directory.
    """
    os.makedirs(target_dir, exist_ok=True)
    print(f"[*] Starting local file generator writing to {target_dir}...")
    files_created = 0
    try:
        while True:
            if max_files and files_created >= max_files:
                print(f"[*] Reached limit of {max_files} files. Stopping generator.")
                break
            
            # Generate a micro-batch of 3 to 8 rides
            batch_size = random.randint(3, 8)
            batch = [generate_corrupted_event() for _ in range(batch_size)]
            
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            file_path = os.path.join(target_dir, f"rides_{timestamp_str}.json")
            
            # Write batch as JSON Lines (one JSON per line)
            with open(file_path, "w") as f:
                for record in batch:
                    f.write(json.dumps(record) + "\n")
            
            files_created += 1
            time.sleep(delay)
    except KeyboardInterrupt:
        print("[*] Local file generator stopped.")

def start_kafka_generator(bootstrap_servers="localhost:9092", topic="uber_rides", delay=1.0):
    """
    Writes ride events directly to a Kafka topic.
    """
    try:
        from kafka import KafkaProducer
        producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        print(f"[*] Starting Kafka generator sending to topic '{topic}' at {bootstrap_servers}...")
        while True:
            event = generate_corrupted_event()
            producer.send(topic, event)
            time.sleep(delay)
    except ImportError:
        print("[!] kafka-python is not installed. Please install it using requirements.txt")
    except Exception as e:
        print(f"[!] Error starting Kafka generator: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Uber Mock Ride Event Generator")
    parser.add_argument("--mode", choices=["file", "kafka"], default="file", help="Generation mode")
    parser.add_argument("--dir", default="data/raw_landing", help="Directory for file mode")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between writes in seconds")
    parser.add_argument("--limit", type=int, default=None, help="Stop after this many iterations")
    
    args = parser.parse_args()
    if args.mode == "file":
        start_file_generator(target_dir=args.dir, delay=args.delay, max_files=args.limit)
    else:
        start_kafka_generator(delay=args.delay)
