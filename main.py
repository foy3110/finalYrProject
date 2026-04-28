from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException

app = FastAPI(title="Smart Health API")


def getDBPool():
    """Lazy import so a bad DB config never crashes startup."""
    from serverFol.Database import getPool
    return getPool()


# ─── helpers ─────────────────────────────────────────────────────────────────

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


# ─── REST endpoints ───────────────────────────────────────────────────────────

@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/summary/daily")
def daily_summary():
    from analysis.Analysis import dailySummary
    try:
        summary = dailySummary()
        return summary.reset_index().to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analysis/run")
def run_analysis():
    from analysis.RollingBaseLine import run_analysis as _run
    try:
        _run()
        return {"status": "analysis complete"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))