import pandas as pd
import numpy as np
from serverFol.Database import getPool as getDBPool

# kloads raw sensor dat and analysed densor data
def loadData():
    conn = getDBPool().get_connection()
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
                COALESCE(a.stress_score, 0) AS stress_score
            FROM raw_sensor_data r
            LEFT JOIN analysed_sensor_data a
                ON r.user_id = a.user_id
               AND r.recorded_at = a.recorded_at
            ORDER BY r.user_id, r.recorded_at
        """
        df = pd.read_sql(query, conn)
    finally:
        conn.close()

    df["recorded_at"] = pd.to_datetime(df["recorded_at"])
    df["hour"]        = df["recorded_at"].dt.hour
    df["date"]        = df["recorded_at"].dt.date
    df["day_name"]    = df["recorded_at"].dt.day_name()
    df["is_weekend"]  = df["day_name"].isin(["Saturday", "Sunday"])

    return df

# average values over an hour
def hourlyProfile(df):
    profile = df.groupby("hour").agg(
        avg_heart_rate=("heart_rate", "mean"),
        std_heart_rate=("heart_rate", "std"),
        avg_hrv=("hrv", "mean"),
        avg_steps=("steps", "mean"),
        avg_skin_temp=("skin_temperature", "mean"),
        avg_conductance=("skin_conductance", "mean"),
        avg_stress=("stress_score", "mean"),
        data_points=("heart_rate", "count"),
    ).reset_index()

    return profile

# compare patterns on weekdays vs weekend
def weekdayVsWeekend(df):
    result = df.groupby(["is_weekend", "hour"]).agg(
        avg_heart_rate=("heart_rate", "mean"),
        avgHrv=("hrv", "mean"),
        avgSteps=("steps", "mean"),
        avgStress=("stress_score", "mean"),
    ).reset_index()

    result["period"] = result["is_weekend"].map({True: "weekend", False: "weekday"})
    result = result.drop(columns=["is_weekend"])

    return result

# Estimates onset and wake up using meann
def detectWakeUp(df):
    """Estimate daily sleep onset and wake times from heart rate + steps."""
    results = []

    for (user_id, date), day_df in df.groupby(["user_id", "date"]):
        hourly = day_df.groupby("hour").agg(
            avg_hr=("heart_rate", "mean"),
            total_steps=("steps", "sum"),
        )

        if len(hourly) < 12:
            continue

        # sleep hours: low HR + near-zero steps
        hourly["sleep_score"] = (
            (hourly["avg_hr"] < hourly["avg_hr"].quantile(0.3)).astype(int) +
            (hourly["total_steps"] < 5).astype(int)
        )

        sleepHours = hourly[hourly["sleep_score"] == 2].index.tolist()

        if not sleepHours:
            continue

        # sleep onset = first sleep hour in evening/night window
        evening_sleep = [h for h in sleepHours if h >= 20 or h <= 6]
        morning_wake_candidates = [h for h in range(24) if h not in sleepHours and h >= 4 and h <= 12]

        sleepOnset = min(evening_sleep) if evening_sleep else None
        wakeHour   = min(morning_wake_candidates) if morning_wake_candidates else None

        # peak and trough hours
        peakHrHour   = int(hourly["avg_hr"].idxmax())
        lowestHrHour = int(hourly["avg_hr"].idxmin())
        peakActivity  = int(hourly["total_steps"].idxmax())

        results.append({
            "user_id":            user_id,
            "date":               date,
            "sleep_onset_hour":   float(sleepOnset) if sleepOnset is not None else None,
            "wake_hour":          float(wake_hour) if wake_hour is not None else None,
            "peak_hr_hour":       peakHrHour,
            "lowest_hr_hour":     lowestHrHour,
            "peak_activity_hour": peakActivity,
        })

    return pd.DataFrame(results)


def regularity(daily_df):
    """
    Score how consistent sleep/wake times are across days.
    Lower std = more regular rhythm = higher score.
    """
    if daily_df.empty:
        return daily_df

    scores = []
    for user_id, group in daily_df.groupby("user_id"):
        sleep_std = group["sleep_onset_hour"].dropna().std()
        wake_std  = group["wake_hour"].dropna().std()

        # regularity: 100 = perfectly consistent, 0 = chaotic
        # 1 hour std = 85 score, 2 hours = 70, 3+ hours = low
        avg_std       = (sleep_std + wake_std) / 2 if not np.isnan(sleep_std) and not np.isnan(wake_std) else 5
        regularity    = max(0, min(100, 100 - (avg_std * 15)))

        for idx in group.index:
            scores.append(regularity)

    daily_df["rhythm_regularity_score"] = scores
    return daily_df

# flags days where sleep/wake deviate >2 hours
def detectDisruptions(daily_df):

    if daily_df.empty:
        return daily_df

    disrupted = []
    for user_id, group in daily_df.groupby("user_id"):
        avg_sleep = group["sleep_onset_hour"].dropna().mean()
        avg_wake  = group["wake_hour"].dropna().mean()

        for _, row in group.iterrows():
            sleep_dev = abs(row["sleep_onset_hour"] - avg_sleep) if pd.notna(row["sleep_onset_hour"]) else 0
            wake_dev  = abs(row["wake_hour"] - avg_wake) if pd.notna(row["wake_hour"]) else 0
            disrupted.append(sleep_dev > 2 or wake_dev > 2)

    daily_df["is_disrupted"] = disrupted
    return daily_df

# Sends to db in batches
def saveToDbCircadian(daily_df):
    if daily_df.empty:
        return

    insertQuery = """
        INSERT IGNORE INTO circadian_analysis
        (user_id, date, sleep_onset_hour, wake_hour, peak_hr_hour,
         lowest_hr_hour, peak_activity_hour, rhythm_regularity_score, is_disrupted)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    rows = [
        (
            row["user_id"],
            row["date"],
            row["sleep_onset_hour"],
            row["wake_hour"],
            row["peak_hr_hour"],
            row["lowest_hr_hour"],
            row["peak_activity_hour"],
            row["rhythm_regularity_score"],
            int(row["is_disrupted"]),
        )
        for _, row in daily_df.iterrows()
    ]

    batch_size = 500
    for i in range(0, len(rows), batch_size):
        conn   = getDBPool().get_connection()
        cursor = conn.cursor()
        try:
            cursor.executemany(insertQuery, rows[i:i + batch_size])
            conn.commit()
        finally:
            cursor.close()
            conn.close()

#circadian analysis pipeline
def runCircadianAnalysis():
    print("Loading data")
    df = loadData()
    print(f"  {len(df)} rows loaded")

    print("daily sleep wake times")
    daily_df = detectWakeUp(df)
    print(f"  {len(daily_df)} days analysed")

    print("Scoring ")
    daily_df = regularity(daily_df)

    print("Detecting")
    daily_df = detectDisruptions(daily_df)
    disrupted_count = daily_df["is_disrupted"].sum() if not daily_df.empty else 0
    print(f"  {disrupted_count} disrupted days found")

    print(" circadian results")
    saveToDbCircadian(daily_df)

    print("C complete.")
    return daily_df