from kafka import KafkaConsumer

consumer = KafkaConsumer(
    'uber_rides',
    bootstrap_servers='localhost:9092',
    group_id='monitor-group'
)

for partition in consumer.assignment():
    committed = consumer.committed(partition)
    latest = consumer.end_offsets([partition])[partition]
    lag = latest - committed

    if lag > 100:
        print("ALERT: High Kafka Lag!")
