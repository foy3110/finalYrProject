import pandas as pd
from Database import getPool

def loadSensorData():
    pool = getPool().get_connection()

    query = """
    SELECT 
        timestamp, 
        heart_rate, 
        steps,
        body_temperature,
        skin_conducance,
        latitude,
        longitude,
    FROM raw_sensor_data AND raw_location_data
        """

    df = pd.read_sql(query, pool)
    pool.close()
    return df

def dailySummary():
    df = loadSensorData()

    df['timestamp'] = pd.to_datetime(df['timestamp'])

    summary = df.groupby(df['timestamp'].dt.date).agg({
        "heart_rate": "mean",
        "steps": "sum",
        "body_temperature": "mean",
        "skin_conducance": "mean",
    })

    return summary

def stressDetection():
    df = loadSensorData()


