import json
import random
import time
from datetime import datetime, timezone

CONTAINER_IDS = ["CNT-1001", "CNT-1002", "CNT-1003", "CNT-1004"]

BASELINE_TEMP_RANGE = (2.0, 8.0)
BASELINE_HUMIDITY_RANGE = (40.0, 70.0)
VIBRATION_RANGE = (0.0, 2.5)

DRIFTING_CONTAINERS = {"CNT-1001"}


def generate_reading(container_id, tick):
    temp_low, temp_high = BASELINE_TEMP_RANGE
    hum_low, hum_high = BASELINE_HUMIDITY_RANGE

    if container_id in DRIFTING_CONTAINERS:
        drift_amount = min(tick * 0.15, 10.0)
        temperature = round(random.uniform(temp_low, temp_high) + drift_amount, 2)
        humidity = round(random.uniform(hum_low, hum_high) + drift_amount * 0.5, 2)
    else:
        temperature = round(random.uniform(temp_low, temp_high), 2)
        humidity = round(random.uniform(hum_low, hum_high), 2)

    vibration = round(random.uniform(*VIBRATION_RANGE), 2)

    return {
        "container_id": container_id,
        "temperature_c": temperature,
        "humidity_pct": humidity,
        "vibration_level": vibration,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def run_simulator(interval_seconds=2.0, total_ticks=10):
    tick = 0
    print("AtmoSync IoT Simulator started...\n")
    while True:
        for container_id in CONTAINER_IDS:
            reading = generate_reading(container_id, tick)
            print(json.dumps(reading))
        tick += 1
        if total_ticks is not None and tick >= total_ticks:
            break
        time.sleep(interval_seconds)


run_simulator(interval_seconds=2.0, total_ticks=10)