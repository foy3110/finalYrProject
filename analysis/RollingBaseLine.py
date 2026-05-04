import pandas as pd
from serverFol.Database import getPool as getDBPool
from analysis.sleepDetector import runSleepAnalysis

##loads sensor data to from raw sensor data db
def loadSensorData():
    conn = getDBPool().get_connection()
    try:
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
        df = pd.read_sql(query, conn)
    finally:
        conn.close()

    df["recorded_at"] = pd.to_datetime(df["recorded_at"])
    return df

#baseline = 1/ number of readings * 1 sum of the data
def rollingBaseLine(df):
    df = df.sort_values(["user_id", "recorded_at"]).copy()

    for col, alias in [
        ("heart_rate",       "hr_baseline"),
        ("hrv",              "hrv_baseline"),
        ("skin_temperature", "temp_baseline"),
        ("skin_conductance", "conductance_baseline"),
    ]:
        baselines = []
        for user_id, group in df.groupby("user_id"):
            g = group.set_index("recorded_at")[col]
            rolled = g.rolling("6h").mean()
            rolled.index = group.index
            baselines.append(rolled)
        df[alias] = pd.concat(baselines).sort_index()

    return df

## 	Deviation = reading – baseline
def calculateDeviation(df):
    df["hr_deviation"]          = df["heart_rate"]       - df["hr_baseline"]
    df["hrv_deviation"]         = df["hrv"]              - df["hrv_baseline"]
    df["temp_deviation"]        = df["skin_temperature"] - df["temp_baseline"]
    df["conductance_deviation"] = df["skin_conductance"] - df["conductance_baseline"]
    return df

#mean anomaly score =sum of all reaadings + 2 * standard deviation
# only top 2.5% values should be flagged
def anomalyDetection(df):
    df["anomaly_score"] = (
        abs(df["hr_deviation"]) +
        abs(df["hrv_deviation"]) +
        abs(df["temp_deviation"]) +
        abs(df["conductance_deviation"])
    )
    threshold     = df["anomaly_score"].mean() + 2 * df["anomaly_score"].std()
    df["anomaly"] = df["anomaly_score"] > threshold
    return df

#stress score is calculated using the formual
#stress_score = (hr_deviation * 0.4) + (negative hrv deviation * 0.3) + (conductance deviation * 0.3)
#it gives a score out of 100
def calculateStressScore(df):
    df["stress_score"] = (
        (df["hr_deviation"]          *  0.4) +
        (df["hrv_deviation"]         * -0.3) +
        (df["conductance_deviation"] *  0.3)
    )
    return df

## inserts batches of data at a time
def dbRollingBaseLine(df):
    insert_query = """
        INSERT IGNORE INTO analysed_sensor_data
        (user_id, recorded_at, hr_baseline, hrv_baseline,
         skin_temp_baseline, conductance_baseline, stress_score, anomaly_flag)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """

    rows = [
        (
            row["user_id"],
            row["recorded_at"],
            row["hr_baseline"],
            row["hrv_baseline"],
            row["temp_baseline"],
            row["conductance_baseline"],
            row["stress_score"],
            int(row["anomaly_flag"]),
        )
        for _, row in df.iterrows()
    ]

    batch_size = 500
    total      = len(rows)
    for i in range(0, total, batch_size):
        conn   = getDBPool().get_connection()
        cursor = conn.cursor()
        try:
            cursor.executemany(insert_query, rows[i:i + batch_size])
            conn.commit()
            print(f"  Wrote batch {i // batch_size + 1}/{(total - 1) // batch_size + 1}")
        finally:
            cursor.close()
            conn.close()

## analysis pipeline
def runAnalysis():
    print(" sensor data")
    df = loadSensorData()
    print(f"  Loaded {len(df)} rows")

    print("rolling baselines")
    df = rollingBaseLine(df)

    print(" deviations")
    df = calculateDeviation(df)

    print("anomaly detection")
    df = anomalyDetection(df)
    print(f"  Anomalies detected: {df['anomaly'].sum()}")

    print(" stress scores")
    df = calculateStressScore(df)

    print("writing to db")
    dbRollingBaseLine(df)

    print("sleep analysis")
    runSleepAnalysis(df)

    print("Analysis complete")