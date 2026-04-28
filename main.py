import pandas as pd
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware

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
    conn = getDBPool().get_connection()
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
                    DATE (recorded_at) AS day, AVG (heart_rate) AS avg_heart_rate, AVG (hrv) AS avg_hrv, MAX (steps) AS total_steps, AVG (skin_temperature) AS avg_skin_temp, AVG (skin_conductance) AS avg_skin_conductance, SUM (anomaly_flag) AS anomaly_count
                FROM raw_sensor_data
                GROUP BY day
                ORDER BY day \
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
                SELECT DATE_FORMAT(recorded_at, '%Y-%m-%d %H:00:00') AS hour,
                AVG(heart_rate)       AS avg_heart_rate,
                AVG(hrv)              AS avg_hrv,
                MAX(steps)            AS total_steps,
                AVG(skin_temperature) AS avg_skin_temp,
                AVG(skin_conductance) AS avg_skin_conductance,
                SUM(anomaly_flag)     AS anomaly_count
                FROM raw_sensor_data
                GROUP BY hour
                ORDER BY hour \
                """
        df = pd.read_sql(query, conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

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

