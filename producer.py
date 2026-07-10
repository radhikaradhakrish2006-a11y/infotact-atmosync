from kafka import KafkaProducer
import json
import random
import time

# Kafka Producer
producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# 12 Container IDs
container_ids = [
    "CNT-1001",
    "CNT-1002",
    "CNT-1003",
    "CNT-1004",
    "CNT-1005",
    "CNT-1006",
    "CNT-1007",
    "CNT-1008",
    "CNT-1009",
    "CNT-1010",
    "CNT-1011",
    "CNT-1012"
]

print("Sending sensor data to Kafka...")

while True:
    data = {
        "container_id": random.choice(container_ids),
        "temperature": round(random.uniform(20, 35), 2),
        "humidity": round(random.uniform(40, 80), 2),
        "vibration": round(random.uniform(0, 5), 2),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    producer.send("sensor-data", data)
    producer.flush()

    print("Sent:", data)

    time.sleep(2)