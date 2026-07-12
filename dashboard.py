from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import snowflake.connector
from datetime import datetime, timedelta

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Snowflake Connection
def get_snowflake_conn():
    return snowflake.connector.connect(
        user="RADHIKA",
        password="Radhika56@2006",
        account="TZBNHXF-QN62223",
        warehouse="COMPUTE_WH",
        database="ATMOSYNC_DB",
        schema="PUBLIC"
    )

# ─── MONITORING API ───
@app.get("/api/dashboard")
def get_dashboard_data():
    conn = get_snowflake_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            COUNT(DISTINCT CONTAINER_ID) as total_sensors,
            AVG(TEMPERATURE_C) as avg_temp,
            AVG(HUMIDITY_PCT) as avg_humidity,
            COUNT(
                CASE
                    WHEN TEMPERATURE_C > 30
                      OR HUMIDITY_PCT > 70
                      OR VIBRATION_LEVEL > 4
                    THEN 1
                END
            ) as active_alerts
        FROM SENSOR_DATA
        WHERE TIMESTAMP >= DATEADD(hour, -24, CURRENT_TIMESTAMP())
    """)
    stats = cur.fetchone()

    cur.execute("""
        SELECT DATE(TIMESTAMP) as day, AVG(TEMPERATURE_C) as temp
        FROM SENSOR_DATA
        WHERE TIMESTAMP >= DATEADD(day, -7, CURRENT_TIMESTAMP())
        GROUP BY day ORDER BY day ASC
    """)
    temp_trend = cur.fetchall()

    cur.execute("""
        SELECT DATE(TIMESTAMP) as day, AVG(HUMIDITY_PCT) as hum
        FROM SENSOR_DATA
        WHERE TIMESTAMP >= DATEADD(day, -7, CURRENT_TIMESTAMP())
        GROUP BY day ORDER BY day ASC
    """)
    hum_trend = cur.fetchall()

    cur.execute("""
        SELECT TIMESTAMP, CONTAINER_ID, TEMPERATURE_C
        FROM SENSOR_DATA
        WHERE TEMPERATURE_C > 30
        ORDER BY TIMESTAMP DESC LIMIT 5
    """)
    alerts = cur.fetchall()

    conn.close()

    days = [str(d[0]) for d in temp_trend] if temp_trend else ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    temps = [float(d[1]) for d in temp_trend] if temp_trend else [20, 22, 25, 24, 26, 28, 27]
    hums = [float(d[1]) for d in hum_trend] if hum_trend else [50, 55, 52, 60, 58, 62, 65]

    return {
        "stats": {
            "total_sensors": stats[0] if stats else 0,
            "avg_temp": round(stats[1], 1) if stats and stats[1] else 0,
            "avg_humidity": round(stats[2], 1) if stats and stats[2] else 0,
            "active_alerts": stats[3] if stats else 0,
        },
        "trends": {
            "days": days,
            "temperatures": temps,
            "humidities": hums,
        },
        "alerts": [
            {"time": str(a[0]), "sensor": a[1], "temp": float(a[2])} for a in alerts
        ]
    }

# ─── ANALYTICS API ───
@app.get("/api/analytics")
def get_analytics_data():
    conn = get_snowflake_conn()
    cur = conn.cursor()

    # Get last 7 days data per container
    cur.execute("""
        SELECT 
            CONTAINER_ID,
            AVG(TEMPERATURE_C) as avg_temp,
            AVG(HUMIDITY_PCT) as avg_hum,
            AVG(VIBRATION_LEVEL) as avg_vib
        FROM SENSOR_DATA
        WHERE TIMESTAMP >= DATEADD(day, -7, CURRENT_TIMESTAMP())
        GROUP BY CONTAINER_ID
    """)
    containers = cur.fetchall()

    # Total Alerts in last 24h
    cur.execute("""
        SELECT COUNT(*) 
        FROM SENSOR_DATA
        WHERE TIMESTAMP >= DATEADD(hour, -24, CURRENT_TIMESTAMP())
          AND (TEMPERATURE_C > 30 OR HUMIDITY_PCT > 70 OR VIBRATION_LEVEL > 4)
    """)
    result = cur.fetchone()
    total_alerts_count = result[0] if result else 0

    conn.close()

    # If no data in Snowflake, return Mock Data
    if not containers:
        return {
            "summary": {
                "avg_spoilage_score": 37.62,
                "high_risk_containers": 23,
                "reroute_recommended": 23,
                "total_alerts": 140
            },
            "risk_distribution": {"high": 23, "medium": 61, "low": 35},
            "top_containers": [
                {"id": "CNT-1001", "score": 48.6, "risk": "High"},
                {"id": "CNT-1002", "score": 42.3, "risk": "High"},
                {"id": "CNT-1003", "score": 39.8, "risk": "Medium"},
                {"id": "CNT-1004", "score": 36.4, "risk": "Medium"},
                {"id": "CNT-1005", "score": 35.6, "risk": "Medium"},
                {"id": "CNT-1006", "score": 33.2, "risk": "Medium"},
                {"id": "CNT-1007", "score": 31.7, "risk": "Low"},
                {"id": "CNT-1008", "score": 29.5, "risk": "Low"}
            ],
            "all_containers": [
                {"id": "CNT-1001", "score": 48.6, "risk": "High"},
                {"id": "CNT-1002", "score": 42.3, "risk": "High"},
                {"id": "CNT-1003", "score": 39.8, "risk": "Medium"},
                {"id": "CNT-1004", "score": 36.4, "risk": "Medium"},
                {"id": "CNT-1005", "score": 35.6, "risk": "Medium"},
                {"id": "CNT-1006", "score": 33.2, "risk": "Medium"},
                {"id": "CNT-1007", "score": 31.7, "risk": "Low"},
                {"id": "CNT-1008", "score": 29.5, "risk": "Low"},
                {"id": "CNT-1009", "score": 28.1, "risk": "Low"},
                {"id": "CNT-1010", "score": 26.3, "risk": "Low"},
                {"id": "CNT-1011", "score": 24.7, "risk": "Low"},
                {"id": "CNT-1012", "score": 22.9, "risk": "Low"}
            ]
        }

    # Calculate Spoilage Score & Risk
    container_list = []
    high_risk = 0
    medium_risk = 0
    low_risk = 0

    for c in containers:
        cid, avg_temp, avg_hum, avg_vib = c

        temp_score = min(100, max(0, (avg_temp - 2) / 28 * 100))
        hum_score = min(100, max(0, (avg_hum - 40) / 40 * 100))
        vib_score = min(100, max(0, avg_vib / 5 * 100))
        score = round((temp_score * 0.6) + (hum_score * 0.3) + (vib_score * 0.1), 2)

        if score > 60:
            risk = 'High'
            high_risk += 1
        elif score > 40:
            risk = 'Medium'
            medium_risk += 1
        else:
            risk = 'Low'
            low_risk += 1

        container_list.append({"id": cid, "score": score, "risk": risk})

    container_list.sort(key=lambda x: x["score"], reverse=True)

    avg_spoilage = round(sum(c["score"] for c in container_list) / len(container_list), 2) if container_list else 0

    return {
        "summary": {
            "avg_spoilage_score": avg_spoilage,
            "high_risk_containers": high_risk,
            "reroute_recommended": high_risk,
            "total_alerts": total_alerts_count
        },
        "risk_distribution": {
            "high": high_risk,
            "medium": medium_risk,
            "low": low_risk
        },
        "top_containers": container_list[:8],
        "all_containers": container_list
    }