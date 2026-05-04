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


def insertIntoDB(data: dict):
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


#websocket
@app.websocket("/ws")
async def websocketEndpoint(websocket: WebSocket):
    await websocket.accept()
    print("WebSocket client connected")
    try:
        while True:
            data = await websocket.receive_json()
            try:
                insertIntoDB(data)
                print(f"Inserted data @ {data.get('timestamp')}")
            except Exception as e:
                print(f"DB insert error: {e}")
    except WebSocketDisconnect:
        print("WebSocket client disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")


#health
@app.get("/health")
def healthCheck():
    return {"status": "ok"}


#summaries
@app.get("/summary/daily")
def dailySummary():
    conn = getDBPool().get_connection()
    try:
        query = """
            SELECT
                DATE(recorded_at)     AS day,
                AVG(heart_rate)       AS avg_heart_rate,
                AVG(hrv)              AS avgHrv,
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
def hourlySummary():

    conn = getDBPool().get_connection()
    try:
        query = """
            SELECT
                DATE_FORMAT(recorded_at, '%%Y-%%m-%%d %%H:00:00') AS hour,
                AVG(heart_rate)       AS avg_heart_rate,
                AVG(hrv)              AS avgHrv,
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


#anomalies
@app.get("/anomalies")
def getAnomalies(
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
                ROUND(ABS(r.heart_rate - a.hr_baseline), 2)               AS hr_deviation,
                ROUND(ABS(r.hrv - a.hrv_baseline), 2)                     AS hrv_deviation,
                ROUND(ABS(r.skin_temperature - a.skin_temp_baseline), 2)   AS temp_deviation,
                ROUND(ABS(r.skin_conductance - a.conductance_baseline), 2) AS conductance_deviation
            FROM analysed_sensor_data a
            JOIN raw_sensor_data r
                ON a.user_id = r.user_id
               AND a.recorded_at = r.recorded_at
            WHERE a.anomaly_flag = 1
        """
        params = []
        if user_id:
            query += " AND a.user_id = %s"
            params.append(user_id)
        if date:
            query += " AND DATE(a.recorded_at) = %s"
            params.append(date)
        query += " ORDER BY a.recorded_at DESC LIMIT %s"
        params.append(limit)

        df = pd.read_sql(query, conn, params=params)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

    df["recorded_at"] = df["recorded_at"].astype(str)
    return {"total": len(df), "anomalies": df.to_dict(orient="records")}


@app.get("/anomalies/summary")
def anomalySummary():
    conn = getDBPool().get_connection()
    try:
        query = """
            SELECT
                DATE(a.recorded_at) AS day,
                COUNT(*)            AS anomaly_count,
                AVG(a.stress_score) AS avg_stress_score,
                AVG(r.heart_rate)   AS avg_heart_rate,
                AVG(r.hrv)          AS avgHrv
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


#sleep
@app.get("/sleep")
def getSleep(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    limit:   int           = Query(30,   description="Max results"),
):
    conn = getDBPool().get_connection()
    try:
        query = """
            SELECT
                user_id,
                sleep_start,
                sleep_end,
                duration_minutes,
                quality_score
            FROM sleep_analysis
            WHERE 1=1
        """
        params = []
        if user_id:
            query += " AND user_id = %s"
            params.append(user_id)
        query += " ORDER BY sleep_start DESC LIMIT %s"
        params.append(limit)

        df = pd.read_sql(query, conn, params=params)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

    df["sleep_start"] = df["sleep_start"].astype(str)
    df["sleep_end"]   = df["sleep_end"].astype(str)

    avg_duration = round(df["duration_minutes"].mean(), 1) if not df.empty else 0
    avg_quality  = round(df["quality_score"].mean(), 1)    if not df.empty else 0

    return {
        "total_sessions":    len(df),
        "avg_duration_mins": avg_duration,
        "avg_quality_score": avg_quality,
        "sessions":          df.to_dict(orient="records"),
    }


@app.get("/sleep/summary")
def sleepSummary():
    conn = getDBPool().get_connection()
    try:
        query = """
            SELECT
                DATE(sleep_start)        AS night,
                SUM(duration_minutes)    AS total_sleep_mins,
                AVG(quality_score)       AS avg_quality,
                COUNT(*)                 AS sessions
            FROM sleep_analysis
            GROUP BY night
            ORDER BY night
        """
        df = pd.read_sql(query, conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

    df["night"]          = df["night"].astype(str)
    df["sleep_hours"]    = round(df["total_sleep_mins"] / 60, 1)
    return df.to_dict(orient="records")


#recovery

@app.get("/recovery")
def getRecovery(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    limit:   int           = Query(30,   description="Max results"),
):
    conn = getDBPool().get_connection()
    try:
        query = """
            SELECT user_id, date, recovery_score
            FROM recovery_analysis
            WHERE 1=1
        """
        params = []
        if user_id:
            query += " AND user_id = %s"
            params.append(user_id)
        query += " ORDER BY date DESC LIMIT %s"
        params.append(limit)

        df = pd.read_sql(query, conn, params=params)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

    df["date"] = df["date"].astype(str)

    avg_recovery = round(df["recovery_score"].mean(), 1) if not df.empty else 0

    return {
        "avg_recovery_score": avg_recovery,
        "scores":             df.to_dict(orient="records"),
    }


#stress
@app.get("/stress/trends")
def stressTrends():
    conn = getDBPool().get_connection()
    try:
        query = """
            SELECT
                DATE(recorded_at)    AS day,
                AVG(stress_score)    AS avgStress,
                MAX(stress_score)    AS max_stress,
                MIN(stress_score)    AS min_stress,
                COUNT(*)             AS data_points
            FROM analysed_sensor_data
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


@app.get("/stress/hourly")
def stressHourly():
    conn = getDBPool().get_connection()
    try:
        query = """
            SELECT
                HOUR(recorded_at)    AS hour_of_day,
                AVG(stress_score)    AS avgStress,
                COUNT(*)             AS data_points
            FROM analysed_sensor_data
            GROUP BY hour_of_day
            ORDER BY hour_of_day
        """
        df = pd.read_sql(query, conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

    return df.to_dict(orient="records")


# location

@app.get("/location/heatmap")
def locationHeatmap(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    date:    Optional[str] = Query(None, description="Filter by date (YYYY-MM-DD)"),
    limit:   int           = Query(500,  description="Max points"),
):
    conn = getDBPool().get_connection()
    try:
        query = """
            SELECT
                l.user_id,
                l.latitude,
                l.longitude,
                l.recorded_at,
                r.heart_rate,
                r.steps,
                COALESCE(a.stress_score, 0) AS stress_score
            FROM raw_location_data l
            JOIN raw_sensor_data r
                ON l.user_id = r.user_id
               AND l.recorded_at = r.recorded_at
            LEFT JOIN analysed_sensor_data a
                ON l.user_id = a.user_id
               AND l.recorded_at = a.recorded_at
            WHERE 1=1
        """
        params = []
        if user_id:
            query += " AND l.user_id = %s"
            params.append(user_id)
        if date:
            query += " AND DATE(l.recorded_at) = %s"
            params.append(date)
        query += " ORDER BY l.recorded_at DESC LIMIT %s"
        params.append(limit)

        df = pd.read_sql(query, conn, params=params)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

    df["recorded_at"] = df["recorded_at"].astype(str)
    return {
        "total_points": len(df),
        "points":       df.to_dict(orient="records"),
    }


@app.get("/location/clusters")
def locationClusters(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
):
    conn = getDBPool().get_connection()
    try:
        query = """
            SELECT
                ROUND(latitude, 3)  AS latCluster,
                ROUND(longitude, 3) AS lonCluster,
                COUNT(*)            AS visitCount,
                AVG(r.heart_rate)   AS avgHeartRate,
                AVG(COALESCE(a.stress_score, 0)) AS avgStress
            FROM raw_location_data l
            JOIN raw_sensor_data r
                ON l.user_id = r.user_id
               AND l.recorded_at = r.recorded_at
            LEFT JOIN analysed_sensor_data a
                ON l.user_id = a.user_id
               AND l.recorded_at = a.recorded_at
            WHERE 1=1
        """
        params = []
        if user_id:
            query += " AND l.user_id = %s"
            params.append(user_id)
        query += " GROUP BY lat_cluster, lon_cluster ORDER BY visit_count DESC LIMIT 20"

        df = pd.read_sql(query, conn, params=params)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

    return df.to_dict(orient="records")


# correlations
@app.get("/analysis/correlations")
def correlations():
    conn = getDBPool().get_connection()
    try:
        query = """
            SELECT
                r.heart_rate,
                r.hrv,
                r.steps,
                r.skin_temperature,
                r.skin_conductance,
                COALESCE(a.stress_score, 0) AS stress_score
            FROM raw_sensor_data r
            LEFT JOIN analysed_sensor_data a
                ON r.user_id = a.user_id
               AND r.recorded_at = a.recorded_at
        """
        df = pd.read_sql(query, conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

    corr = df.corr().round(3)
    return {
        "correlation_matrix": corr.to_dict(),
        "key_findings": {
            "hr_vs_stress":        float(corr.loc["heart_rate", "stress_score"]),
            "hrv_vs_stress":       float(corr.loc["hrv", "stress_score"]),
            "steps_vs_hr":         float(corr.loc["steps", "heart_rate"]),
            "conductance_vs_stress": float(corr.loc["skin_conductance", "stress_score"]),
        }
    }


#circadian rthym

@app.get("/analysis/circadian")
def circadianRhythm():
    conn = getDBPool().get_connection()
    try:
        query = """
            SELECT
                HOUR(recorded_at)     AS hour_of_day,
                AVG(heart_rate)       AS avg_heart_rate,
                AVG(hrv)              AS avgHrv,
                AVG(steps)            AS avgSteps,
                AVG(skin_temperature) AS avg_skin_temp,
                AVG(skin_conductance) AS avg_skin_conductance,
                COUNT(*)              AS data_points
            FROM raw_sensor_data
            GROUP BY hour_of_day
            ORDER BY hour_of_day
        """
        df = pd.read_sql(query, conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

    peakHrHour  = int(df.loc[df["avg_heart_rate"].idxmax(), "hour_of_day"])  if not df.empty else 0
    lowHrHour   = int(df.loc[df["avg_heart_rate"].idxmin(), "hour_of_day"])  if not df.empty else 0
    peakStepHr  = int(df.loc[df["avgSteps"].idxmax(), "hour_of_day"])       if not df.empty else 0

    return {
        "hourly_averages": df.to_dict(orient="records"),
        "insights": {
            "peak_heart_rate_hour":  peakHrHour,
            "lowest_heart_rate_hour": lowHrHour,
            "most_active_hour":      peakStepHr,
        }
    }


# ─── activity classification ─────────────────────────────────────────────────

@app.get("/activity/classification")
def activityClassification():
    conn = getDBPool().get_connection()
    try:
        query = """
            SELECT
                recorded_at,
                heart_rate,
                steps
            FROM raw_sensor_data
            ORDER BY recorded_at
        """
        df = pd.read_sql(query, conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

    def classify(row):
        if row["steps"] == 0 and row["heart_rate"] < 65:
            return "sleep"
        elif row["steps"] < 5 and row["heart_rate"] < 80:
            return "sedentary"
        elif row["steps"] < 30 and row["heart_rate"] < 100:
            return "light_activity"
        elif row["heart_rate"] >= 100 or row["steps"] >= 30:
            return "exercise"
        return "sedentary"

    df["activity"] = df.apply(classify, axis=1)

    totals   = df["activity"].value_counts().to_dict()
    pcts     = df["activity"].value_counts(normalize=True).mul(100).round(1).to_dict()
    total    = len(df)

    return {
        "total_readings":     total,
        "activity_counts":    totals,
        "activity_percentages": pcts,
        "minutes_estimate": {k: v for k, v in totals.items()},
    }


@app.get("/activity/daily")
def activityDaily():
    conn = getDBPool().get_connection()
    try:
        query = """
            SELECT
                DATE(recorded_at) AS day,
                heart_rate,
                steps
            FROM raw_sensor_data
            ORDER BY recorded_at
        """
        df = pd.read_sql(query, conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

    def classify(row):
        if row["steps"] == 0 and row["heart_rate"] < 65:
            return "sleep"
        elif row["steps"] < 5 and row["heart_rate"] < 80:
            return "sedentary"
        elif row["steps"] < 30 and row["heart_rate"] < 100:
            return "light_activity"
        elif row["heart_rate"] >= 100 or row["steps"] >= 30:
            return "exercise"
        return "sedentary"

    df["activity"] = df.apply(classify, axis=1)
    df["day"]      = df["day"].astype(str)

    pivot = df.groupby(["day", "activity"]).size().unstack(fill_value=0).reset_index()
    return pivot.to_dict(orient="records")


# ─── analysis ─────────────────────────────────────────────────────────────────

@app.post("/analysis/run")
def runAnalysis():
    from analysis.RollingBaseLine import runAnalysis as _run
    try:
        _run()
        return {"status": "analysis complete"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))