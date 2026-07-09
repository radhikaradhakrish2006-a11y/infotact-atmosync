from kafka import KafkaConsumer
import snowflake.connector
import json

# Connect to Snowflake
conn = snowflake.connector.connect(
    user="RADHIKA",
    password="Radhika56@2006",
    account="TZBNHXF-QN62223",
    warehouse="COMPUTE_WH",
    database="ATMOSYNC_DB",
    schema="PUBLIC"
)

cur = conn.cursor()


consumer = KafkaConsumer(
    "sensor-data",
    bootstrap_servers="localhost:9092",
    value_deserializer=lambda x: json.loads(x.decode("utf-8"))
)

print("Waiting for messages...")

for msg in consumer:
    data = msg.value

    cur.execute("""
        INSERT INTO SENSOR_DATA
        (CONTAINER_ID, TEMPERATURE_C, HUMIDITY_PCT, VIBRATION_LEVEL, TIMESTAMP)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        data["container_id"],
        data["temperature"],
        data["humidity"],
        data["vibration"],
        data["timestamp"]
    ))

    conn.commit()
    print("Inserted:", data)