import pandas as pd
from serverFol.Database import getPool as getDBPool
from analysis.sleepDetector import runSleepAnalysis


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


def rollingBaseLine(df):
    df = df.sort_values(["user_id", "recorded_at"])

    for col, alias in [
        ("heart_rate",        "hr_baseline"),
        ("hrv",               "hrv_baseline"),
        ("skin_temperature",  "temp_baseline"),
        ("skin_conductance",  "conductance_baseline"),
    ]:
        df[alias] = (
            df.groupby("user_id", group_keys=False)
            .apply(lambda g: g.set_index("recorded_at")[col].rolling("6h").mean().reset_index(drop=True).set_axis(g.index))
        )

    return df


def calculate_deviation(df):
    df["hr_deviation"]          = df["heart_rate"]       - df["hr_baseline"]
    df["hrv_deviation"]         = df["hrv"]              - df["hrv_baseline"]
    df["temp_deviation"]        = df["skin_temperature"] - df["temp_baseline"]
    df["conductance_deviation"] = df["skin_conductance"] - df["conductance_baseline"]
    return df


def anomalyDetection(df):
    df["anomaly_score"] = (
        abs(df["hr_deviation"]) +
        abs(df["hrv_deviation"]) +
        abs(df["temp_deviation"]) +
        abs(df["conductance_deviation"])
    )
    threshold    = df["anomaly_score"].mean() + 2 * df["anomaly_score"].std()
    df["anomaly"] = df["anomaly_score"] > threshold
    return df


def calculate_stress_score(df):
    df["stress_score"] = (
        (df["hr_deviation"]          *  0.4) +
        (df["hrv_deviation"]         * -0.3) +
        (df["conductance_deviation"] *  0.3)
    )
    return df


def db_rollingBaseLine(df):
    conn   = getDBPool().get_connection()
    cursor = conn.cursor()
    try:
        insert_query = """
            INSERT IGNORE INTO analysed_sensor_data
            (user_id, recorded_at, hr_baseline, hrv_baseline,
             skin_temp_baseline, conductance_baseline, stress_score, anomaly_flag)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
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
                int(row["anomaly_flag"]),
            ))
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def run_analysis():
    print("Loading sensor data...")
    df = loadSensorData()

    print("Computing rolling baselines...")
    df = rollingBaseLine(df)

    print("Computing deviations...")
    df = calculate_deviation(df)

    print("Running anomaly detection...")
    df = anomalyDetection(df)
    print(f"  Anomalies detected: {df['anomaly'].sum()}")

    print("Computing stress scores...")
    df = calculate_stress_score(df)

    print("Writing to DB...")
    db_rollingBaseLine(df)

    print("Running sleep analysis...")
    runSleepAnalysis(df)

    print("Analysis complete.")