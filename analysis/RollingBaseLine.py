import pandas as pd
from serverFol.Database import getPool as getDBPool
from analysis.sleepDetector import *
#gets data from raw data db
def loadSensorData():
    pool = getDBPool().get_connection()

    query = """
    SELECT 
            user_id,
            recorded_at,
            heart_rate,
            hrv,
            steps,
            skin_temperature,
            skin_conductance,
            anomaly_flag
    FROM raw_sensor_data
    ORDER BY user_id, recorded_at
    """
    df = pd.read_sql(query, pool)
    pool.close()

    df["recorded_at"] = pd.to_datetime(df["recorded_at"])

    return df

def rollingBaseLine(df):
    df["recorded_at"] = pd.to_datetime(df["recorded_at"])

    df = df.sort_values(["user_id", "recorded_at"])

    df["hr_baseline"] = (
        df.groupby("user_id")
        .rolling("6h", on="recorded_at")["heart_rate"]
        .mean()
        .reset_index(drop=True)
    )

    df["hrv_baseline"] = (
        df.groupby("user_id")
        .rolling("6h", on="recorded_at")["hrv"]
        .mean()
        .reset_index(drop=True)
    )

    df["temp_baseline"] = (
        df.groupby("user_id")
        .rolling("6h", on="recorded_at")["skin_temperature"]
        .mean()
        .reset_index(drop=True)
    )
    df["conductance_baseline"] = (
        df.groupby("user_id")
        .rolling("6h", on="recorded_at")["skin_conductance"]
        .mean()
        .reset_index(drop=True)
    )
    return df

def calculate_deviation(df):

    df["hr_deviation"] = df["heart_rate"] - df["hr_baseline"]
    df["hrv_deviation"] = df["hrv"] - df["hrv_baseline"]
    df["temp_deviation"] = df["skin_temperature"] - df["temp_baseline"]
    df["conductance_deviation"] = df["skin_conductance"] - df["conductance_baseline"]

    return df

def anomalyDetection(df):
    df["anomaly_score"] = (
            abs(df["hr_deviation"]) +
            abs(df["hrv_deviation"]) +
            abs(df["temp_deviation"]) +
            abs(df["conductance_deviation"])
    )

    threshold = df["anomaly_score"].mean() + (2 * df["anomaly_score"].std())

    df["anomaly"] = df["anomaly_score"] > threshold

    return df

def calculate_stress_score(df):

    df["stress_score"] = (
        (df["hr_deviation"] * 0.4) +
        (-df["hrv_deviation"] * 0.3) +
        (df["conductance_deviation"] * 0.3)
    )

    return df

def db_rollingBaseLine(df):
    connection = getDBPool().get_connection()
    cursor = connection.cursor()

    insert_query = """
                   INSERT IGNORE INTO analysed_sensor_data
                   (user_id, recorded_at, hr_baseline, hrv_baseline,
                    skin_temp_baseline, conductance_baseline, stress_score, anomaly_flag)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s) \
                   """

    for _, row in df.iterrows():
        cursor.execute(insert_query, (
            row["user_id"],
            row["recorded_at"],
            row["hr_baseline"],
            row["hrv_baseline"],
            row["temp_baseline"],
            row["conductance_baseline"],
            row["stress_score"],
            int(row["anomaly_flag"])
        ))

    connection.commit()

    cursor.close()
    connection.close()

def run_analysis():
    df = loadSensorData()
    print(1)
    print(df["recorded_at"].isna().sum())
    df = rollingBaseLine(df)
    print(2)

    df = calculate_deviation(df)
    print(3)

    df = anomalyDetection(df)

    print(4)
    print("Anomalies detected:", df["anomaly"].sum())
    df = calculate_stress_score(df)

    print(5)

    db_rollingBaseLine(df)

    print("Analysis complete")

    runSleepAnalysis(df)
    print("Sleep Analysis complete")
