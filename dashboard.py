from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import snowflake.connector
import logging

# ─── Logging ───
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── FastAPI App ───
app = FastAPI()

# ─── CORS (Allow all origins for development) ───
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Snowflake Connection ───
def get_snowflake_conn():
    try:
        conn = snowflake.connector.connect(
            user="RADHIKA",
            password="Radhika56@2006",
            account="TZBNHXF-QN62223",
            warehouse="COMPUTE_WH",
            database="ATMOSYNC_DB",
            schema="PUBLIC"
        )
        logger.info("✅ Snowflake connected")
        return conn
    except Exception as e:
        logger.error(f"❌ Snowflake connection failed: {e}")
        raise
#debugging the end point
@app.get("/api/tables")
def list_tables():
    """List all tables in the schema (debug)."""
    conn = get_snowflake_conn()
    cur = conn.cursor()
    cur.execute("SHOW TABLES")
    tables = cur.fetchall()
    conn.close()
    return {"tables": [t[1] for t in tables]}

@app.get("/api/debug")
def debug_data():
    """Check row counts in sensor_transformation table."""
    try:
        conn = get_snowflake_conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM SENSOR_TRANSFORMATION")
        total = cur.fetchone()[0]
        cur.execute("""
            SELECT COUNT(*) 
            FROM SENSOR_TRANSFORMATION 
            WHERE TIMESTAMP >= DATEADD(hour, -24, CURRENT_TIMESTAMP())
        """)
        last_24h = cur.fetchone()[0]
        conn.close()
        return {
            "total_rows": total,
            "rows_last_24h": last_24h,
            "status": "✅ Data available" if total > 0 else "❌ No data"
        }
    except Exception as e:
        return {"error": str(e), "status": "❌ Query failed"}

# ──────────────────────────────────────────────
# MONITORING API
# ──────────────────────────────────────────────

@app.get("/api/dashboard")
def get_dashboard_data():
    """
    Real-time monitoring dashboard data.
    Returns summary stats, trends, and recent alerts.
    """
    try:
        conn = get_snowflake_conn()
        cur = conn.cursor()

        # 1. Summary Stats (last 24h)
        cur.execute("""
            SELECT
                COUNT(DISTINCT CONTAINER_ID) as total_sensors,
                COALESCE(AVG(TEMPERATURE_C), 0) as avg_temp,
                COALESCE(AVG(HUMIDITY_PCT), 0) as avg_humidity,
                COUNT(
                    CASE
                        WHEN TEMPERATURE_C > 30
                          OR HUMIDITY_PCT > 70
                          OR VIBRATION_LEVEL > 4
                    THEN 1
                    END
                ) as active_alerts
            FROM SENSOR_TRANSFORMATION
            WHERE TIMESTAMP >= DATEADD(hour, -24, CURRENT_TIMESTAMP())
        """)
        stats = cur.fetchone()

        # 2. Temperature Trend (last 7 days)
        cur.execute("""
            SELECT DATE(TIMESTAMP) as day, COALESCE(AVG(TEMPERATURE_C), 0) as temp
            FROM SENSOR_TRANSFORMATION
            WHERE TIMESTAMP >= DATEADD(day, -7, CURRENT_TIMESTAMP())
            GROUP BY day ORDER BY day ASC
        """)
        temp_trend = cur.fetchall()

        # 3. Humidity Trend (last 7 days)
        cur.execute("""
            SELECT DATE(TIMESTAMP) as day, COALESCE(AVG(HUMIDITY_PCT), 0) as hum
            FROM SENSOR_TRANSFORMATION
            WHERE TIMESTAMP >= DATEADD(day, -7, CURRENT_TIMESTAMP())
            GROUP BY day ORDER BY day ASC
        """)
        hum_trend = cur.fetchall()

        # 4. Recent Alerts (top 5 high temp)
        cur.execute("""
            SELECT TIMESTAMP, CONTAINER_ID, TEMPERATURE_C
            FROM SENSOR_TRANSFORMATION
            WHERE TEMPERATURE_C > 30
            ORDER BY TIMESTAMP DESC LIMIT 5
        """)
        alerts = cur.fetchall()

        conn.close()

        # Format trends
        days = [str(d[0]) for d in temp_trend] if temp_trend else ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        temps = [float(d[1]) for d in temp_trend] if temp_trend else [0,0,0,0,0,0,0]
        hums = [float(d[1]) for d in hum_trend] if hum_trend else [0,0,0,0,0,0,0]

        return {
            "stats": {
                "total_sensors": stats[0] if stats else 0,
                "avg_temp": round(stats[1], 1) if stats else 0,
                "avg_humidity": round(stats[2], 1) if stats else 0,
                "active_alerts": stats[3] if stats else 0,
            },
            "trends": {
                "days": days,
                "temperatures": temps,
                "humidities": hums,
            },
            "alerts": [
                {"time": str(a[0]), "sensor": a[1], "temp": float(a[2])}
                for a in alerts
            ]
        }

    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        return {
            "error": str(e),
            "stats": {"total_sensors":0,"avg_temp":0,"avg_humidity":0,"active_alerts":0},
            "trends": {"days":[],"temperatures":[],"humidities":[]},
            "alerts": []
        }

# ──────────────────────────────────────────────
# ANALYTICS API (UPDATED: THRESHOLD 30)
# ──────────────────────────────────────────────

@app.get("/api/analytics")
def get_analytics_data():
    """
    Spoilage & Arbitrage Analytics.
    UPDATED THRESHOLDS (Power BI compatible):
    - Spoilage Score = (Temp * 0.5) + (Humidity * 0.3) + (Vibration * 0.2)
    - Risk Level: 3 (High) if Score >= 30
                  2 (Medium) if Score >= 20
                  1 (Low) if Score < 20
    - High Risk Containers = CALCULATE(DISTINCTCOUNT(CONTAINER_ID), Risk Level = 3)
    - Arbitrage Opportunity = "Reroute Shipment" if Risk Level = 3 else "Normal"
    - Reroute Recommended = CALCULATE(COUNTROWS(SENSOR_TRANSFORMATION), Arbitrage Opportunity = "Reroute Shipment")
    """
    try:
        conn = get_snowflake_conn()
        cur = conn.cursor()

        # Get per-container averages (last 7 days)
        cur.execute("""
            SELECT 
                CONTAINER_ID,
                COALESCE(AVG(TEMPERATURE_C), 0) as avg_temp,
                COALESCE(AVG(HUMIDITY_PCT), 0) as avg_hum,
                COALESCE(AVG(VIBRATION_LEVEL), 0) as avg_vib
            FROM SENSOR_TRANSFORMATION
            WHERE TIMESTAMP >= DATEADD(day, -7, CURRENT_TIMESTAMP())
            GROUP BY CONTAINER_ID
        """)
        containers_raw = cur.fetchall()

        # Total alerts (last 24h)
        cur.execute("""
            SELECT COUNT(*) 
            FROM SENSOR_TRANSFORMATION
            WHERE TIMESTAMP >= DATEADD(hour, -24, CURRENT_TIMESTAMP())
              AND (TEMPERATURE_C > 30 OR HUMIDITY_PCT > 70 OR VIBRATION_LEVEL > 4)
        """)
        result = cur.fetchone()
        total_alerts = result[0] if result else 0

        conn.close()

        # If no data, return zeros
        if not containers_raw:
            return {
                "summary": {
                    "avg_spoilage_score": 0,
                    "high_risk_containers": 0,
                    "reroute_recommended": 0,
                    "total_alerts": 0
                },
                "risk_distribution": {"high": 0, "medium": 0, "low": 0},
                "top_containers": [],
                "all_containers": []
            }


        container_list = []
        high = 0
        medium = 0
        low = 0

        for c in containers_raw:
            cid, avg_temp, avg_hum, avg_vib = c

            # ─── DAX: Spoilage Score ───
            score = round((avg_temp * 0.5) + (avg_hum * 0.3) + (avg_vib * 0.2), 2)

            # ─── UPDATED: Risk Level (Threshold 30) ───
            if score >= 30:
                risk_level = 3
                risk_label = 'High'
                high += 1
            elif score >= 20:
                risk_level = 2
                risk_label = 'Medium'
                medium += 1
            else:
                risk_level = 1
                risk_label = 'Low'
                low += 1

            # ─── DAX: Arbitrage Opportunity ───
            if risk_level == 3:
                arbitrage_opportunity = "Reroute Shipment"
            else:
                arbitrage_opportunity = "Normal"

            container_list.append({
                "id": cid,
                "score": score,
                "risk_level": risk_level,
                "risk": risk_label,
                "arbitrage_opportunity": arbitrage_opportunity
            })

        # Sort by score descending
        container_list.sort(key=lambda x: x["score"], reverse=True)

        # ─── Summary Stats ───
        avg_score = round(
            sum(c["score"] for c in container_list) / len(container_list),
            2
        ) if container_list else 0

        # DAX: CALCULATE(DISTINCTCOUNT(CONTAINER_ID), Risk Level = 3)
        high_risk_count = sum(1 for c in container_list if c["risk_level"] == 3)

        # DAX: CALCULATE(COUNTROWS(SENSOR_TRANSFORMATION), Arbitrage Opportunity = "Reroute Shipment")
        # In container-level aggregation, this maps to count of containers needing reroute.
        reroute_count = sum(1 for c in container_list if c["arbitrage_opportunity"] == "Reroute Shipment")

        return {
            "summary": {
                "avg_spoilage_score": avg_score,
                "high_risk_containers": high_risk_count,
                "reroute_recommended": reroute_count,
                "total_alerts": total_alerts
            },
            "risk_distribution": {
                "high": high,
                "medium": medium,
                "low": low
            },
            "top_containers": container_list[:8],
            "all_containers": container_list
        }

    except Exception as e:
        logger.error(f"Analytics error: {e}")
        return {
            "error": str(e),
            "summary": {
                "avg_spoilage_score": 0,
                "high_risk_containers": 0,
                "reroute_recommended": 0,
                "total_alerts": 0
            },
            "risk_distribution": {"high": 0, "medium": 0, "low": 0},
            "top_containers": [],
            "all_containers": []
        }

# ──────────────────────────────────────────────
# ROOT
# ──────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "message": "AtmoSync API is running.",
        "endpoints": {
            "/api/dashboard": "Real-time monitoring data",
            "/api/analytics": "Spoilage & Arbitrage analytics (Power BI logic with Threshold 30)",
            "/api/debug": "Debug - check row counts",
            "/api/tables": "Debug - list all tables"
        }
    }