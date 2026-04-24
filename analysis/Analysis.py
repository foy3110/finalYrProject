import pandas as pd
from serverFol.Database import getPool


def loadSensorData():
    conn = getPool().get_connection()
    try:
        query = """
            SELECT
                r.user_id,
                r.recorded_at,
                r.heart_rate,
                r.hrv,
                r.steps,
                r.skin_temperature,
                r.skin_conductance,
                l.latitude,
                l.longitude
            FROM raw_sensor_data r
            JOIN raw_location_data l
                ON r.user_id = l.user_id
               AND r.recorded_at = l.recorded_at
        """
        df = pd.read_sql(query, conn)
    finally:
        conn.close()
    return df


def dailySummary():
    df = loadSensorData()
    df["recorded_at"] = pd.to_datetime(df["recorded_at"])
    summary = df.groupby(df["recorded_at"].dt.date).agg({
        "heart_rate":       "mean",
        "steps":            "sum",
        "skin_temperature": "mean",
        "skin_conductance": "mean",
    })
    return summary