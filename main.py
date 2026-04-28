import pandas as pd
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

app = FastAPI(title="Smart Health API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def getDBPool():
    from serverFol.Database import getPool
    return getPool()


def insert_into_db(data: dict):
    conn   = getDBPool().get_connection()
    cursor = conn.cursor()
    try:
        user_id = data.get("user_id", "1")
        cursor.execute(
            """
            INSERT INTO raw_sensor_data
                (user_id, heart_rate, hrv, steps,
                 skin_temperature, skin_conductance, recorded_at, anomaly_flag)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                user_id,
                data["heart_rate"],
                data["hrv"],
                data["steps"],
                data["skinTemp"],
                data["skinCond"],
                data["timestamp"],
                data.get("flag", False),
            ),
        )
        cursor.execute(
            """
            INSERT INTO raw_location_data
                (user_id, latitude, longitude, recorded_at, anomaly_flag)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                user_id,
                data["location"]["latitude"],
                data["location"]["longitude"],
                data["timestamp"],
                data.get("flag", False),
            ),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


# ─── WebSocket ────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("WebSocket client connected")
    try:
        while True:
            data = await websocket.receive_json()
            try:
                insert_into_db(data)
                print(f"Inserted data @ {data.get('timestamp')}")
            except Exception as e:
                print(f"DB insert error: {e}")
    except WebSocketDisconnect:
        print("WebSocket client disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")


# ─── health ───────────────────────────────────────────────────────────────────

@app.get("/health")
def health_check():
    return {"status": "ok"}


# ─── summaries ────────────────────────────────────────────────────────────────

@app.get("/summary/daily")
def daily_summary():
    conn = getDBPool().get_connection()
    try:
        query = """
            SELECT
                DATE(recorded_at)     AS day,
                AVG(heart_rate)       AS avg_heart_rate,
                AVG(hrv)              AS avg_hrv,
                MAX(steps)            AS total_steps,
                AVG(skin_temperature) AS avg_skin_temp,
                AVG(skin_conductance) AS avg_skin_conductance,
                SUM(anomaly_flag)     AS anomaly_count
            FROM raw_sensor_data
            GROUP BY day
            ORDER BY day
        """
        df = pd.read_sql(query, conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

    df["day"] = df["day"].astype(str)
    return df.to_dict(orient="records")


@app.get("/summary/hourly")
def hourly_summary():
    conn = getDBPool().get_connection()
    try:
        query = """
            SELECT
                DATE_FORMAT(recorded_at, '%Y-%m-%d %H:00:00') AS hour,
                AVG(heart_rate)       AS avg_heart_rate,
                AVG(hrv)              AS avg_hrv,
                MAX(steps)            AS total_steps,
                AVG(skin_temperature) AS avg_skin_temp,
                AVG(skin_conductance) AS avg_skin_conductance,
                SUM(anomaly_flag)     AS anomaly_count
            FROM raw_sensor_data
            GROUP BY hour
            ORDER BY hour
        """
        df = pd.read_sql(query, conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

    return df.to_dict(orient="records")


# ─── anomalies ────────────────────────────────────────────────────────────────

@app.get("/anomalies")
def get_anomalies(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    date:    Optional[str] = Query(None, description="Filter by date (YYYY-MM-DD)"),
    limit:   int           = Query(100,  description="Max number of results"),
):
    conn = getDBPool().get_connection()
    try:
        query = """
            SELECT
                a.user_id,
                a.recorded_at,
                a.hr_baseline,
                a.hrv_baseline,
                a.skin_temp_baseline,
                a.conductance_baseline,
                a.stress_score,
                r.heart_rate,
                r.hrv,
                r.steps,
                r.skin_temperature,
                r.skin_conductance,
                ROUND(ABS(r.heart_rate - a.hr_baseline), 2)             AS hr_deviation,
                ROUND(ABS(r.hrv - a.hrv_baseline), 2)                   AS hrv_deviation,
                ROUND(ABS(r.skin_temperature - a.skin_temp_baseline), 2) AS temp_deviation,
                ROUND(ABS(r.skin_conductance - a.conductance_baseline), 2) AS conductance_deviation
            FROM analysed_sensor_data a
            JOIN raw_sensor_data r
                ON a.user_id = r.user_id
               AND a.recorded_at = r.recorded_at
            WHERE a.anomaly_flag = 1
        """

        params = []

        if user_id:
            query  += " AND a.user_id = %s"
            params.append(user_id)

        if date:
            query  += " AND DATE(a.recorded_at) = %s"
            params.append(date)

        query += " ORDER BY a.recorded_at DESC LIMIT %s"
        params.append(limit)

        df = pd.read_sql(query, conn, params=params)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

    df["recorded_at"] = df["recorded_at"].astype(str)
    return {
        "total": len(df),
        "anomalies": df.to_dict(orient="records")
    }


@app.get("/anomalies/summary")
def anomaly_summary():
    conn = getDBPool().get_connection()
    try:
        query = """
            SELECT
                DATE(a.recorded_at)          AS day,
                COUNT(*)                     AS anomaly_count,
                AVG(a.stress_score)          AS avg_stress_score,
                AVG(r.heart_rate)            AS avg_heart_rate,
                AVG(r.hrv)                   AS avg_hrv
            FROM analysed_sensor_data a
            JOIN raw_sensor_data r
                ON a.user_id = r.user_id
               AND a.recorded_at = r.recorded_at
            WHERE a.anomaly_flag = 1
            GROUP BY day
            ORDER BY day
        """
        df = pd.read_sql(query, conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

    df["day"] = df["day"].astype(str)
    return df.to_dict(orient="records")


# ─── analysis ─────────────────────────────────────────────────────────────────

@app.post("/analysis/run")
def run_analysis():
    from analysis.RollingBaseLine import run_analysis as _run
    try:
        _run()
        return {"status": "analysis complete"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))