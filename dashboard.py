from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import snowflake.connector
from datetime import datetime, timedelta
import random

app = FastAPI()

# CORS - HTML-ல இருந்து API call பண்ண allow பண்ணும்
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
        password="Radhika56@2006",  # <-- உங்கள் Password போடுங்க
        account="TZBNHXF-QN62223",
        warehouse="COMPUTE_WH",
        database="ATMOSYNC_DB",
        schema="PUBLIC"
    )

@app.get("/api/dashboard")
def get_dashboard_data():
    conn = get_snowflake_conn()
    cur = conn.cursor()

    # 1. Summary Stats
    cur.execute("""
        SELECT 
            COUNT(DISTINCT CONTAINER_ID) as total_sensors,
            AVG(TEMPERATURE_C) as avg_temp,
            AVG(HUMIDITY_PCT) as avg_humidity,
            COUNT(CASE WHEN TEMPERATURE_C > 30 THEN 1 END) as active_alerts
        FROM SENSOR_DATA
        WHERE TIMESTAMP >= DATEADD(hour, -24, CURRENT_TIMESTAMP())
    """)
    stats = cur.fetchone()
    
    # 2. Last 7 days trend (Temperature)
    cur.execute("""
        SELECT DATE(TIMESTAMP) as day, AVG(TEMPERATURE_C) as temp
        FROM SENSOR_DATA
        WHERE TIMESTAMP >= DATEADD(day, -7, CURRENT_TIMESTAMP())
        GROUP BY day ORDER BY day ASC
    """)
    temp_trend = cur.fetchall()
    
    # 3. Last 7 days trend (Humidity)
    cur.execute("""
        SELECT DATE(TIMESTAMP) as day, AVG(HUMIDITY_PCT) as hum
        FROM SENSOR_DATA
        WHERE TIMESTAMP >= DATEADD(day, -7, CURRENT_TIMESTAMP())
        GROUP BY day ORDER BY day ASC
    """)
    hum_trend = cur.fetchall()
    
    # 4. Recent Alerts (last 5 high temps)
    cur.execute("""
        SELECT TIMESTAMP, CONTAINER_ID, TEMPERATURE_C
        FROM SENSOR_DATA
        WHERE TEMPERATURE_C > 30
        ORDER BY TIMESTAMP DESC LIMIT 5
    """)
    alerts = cur.fetchall()
    
    # 5. Top 5 sensors avg temp
    cur.execute("""
        SELECT CONTAINER_ID, AVG(TEMPERATURE_C) as avg_temp
        FROM SENSOR_DATA
        WHERE TIMESTAMP >= DATEADD(hour, -24, CURRENT_TIMESTAMP())
        GROUP BY CONTAINER_ID
        ORDER BY avg_temp DESC LIMIT 5
    """)
    top_sensors = cur.fetchall()
    
    conn.close()

    # Format Response
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
        ],
        "top_sensors": [
            {"id": s[0], "temp": float(s[1])} for s in top_sensors
        ]
    }

# To run: uvicorn dashboard_api:app --reload --host 0.0.0.0 --port 8000