from kafka import KafkaProducer
import json
import random
from kafka import KafkaProducer
import json
import random
import time

producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

while True:
    data = {
        "container_id": "CNT-1001",
        "temperature": round(random.uniform(20, 35), 2),
        "humidity": round(random.uniform(40, 80), 2),
        "vibration": round(random.uniform(0, 5), 2),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    producer.send("sensor-data", data)
    print("Sent:", data)

    time.sleep(2)