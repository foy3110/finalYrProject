import pandas as pd
from serverFol.Database import getPool as getDbPool


def save_sleep(sleepDf, quality):
    if sleepDf.empty:
        return

    conn = getDbPool().get_connection()
    cursor = conn.cursor()
    try:
        query = """
            INSERT IGNORE INTO sleep_analysis
            (user_id, sleep_start, sleep_end, duration_minutes, quality_score)
            VALUES (%s, %s, %s, %s, %s)
        """
        for _, row in sleepDf.iterrows():
            cursor.execute(query, (
                int(row["user_id"]),
                row["start"],
                row["end"],
                int(row["duration"]),
                float(quality),
            ))
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def saveRecovery(user_id, recovery):
    conn = getDbPool().get_connection()
    cursor = conn.cursor()
    try:
        query = """
            INSERT INTO recovery_analysis (user_id, date, recovery_score)
            VALUES (%s, CURDATE(), %s)
        """
        cursor.execute(query, (int(user_id), float(recovery)))
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def estimateSleepStage(df):
    conditions = []
    for _, row in df.iterrows():
        if not row.get("sleep_candidate", False):
            conditions.append("awake")
            continue
        if row["hrv"] > row["hrv_baseline"] * 1.2 and row["heart_rate"] < row["hr_baseline"] * 0.9:
            conditions.append("deep_sleep")
        elif row["hrv"] > row["hrv_baseline"]:
            conditions.append("rem_sleep")
        else:
            conditions.append("light_sleep")
    df["sleep_stage"] = conditions
    return df


def detectSleepOnset(df):
    df["sleep_start_flag"] = (
        (df["sleep_candidate"] == True) &
        (df["sleep_candidate"].shift() == False)
    )
    return df[df["sleep_start_flag"]]


def recoveryScore(df, sleep_df):
    sleep_duration = sleep_df["duration"].sum() if not sleep_df.empty and "duration" in sleep_df.columns else 0

    avg_hrv           = df["hrv"].mean()
    avg_hrv_baseline  = df["hrv_baseline"].mean()
    avg_hr            = df["heart_rate"].mean()
    avg_hr_baseline   = df["hr_baseline"].mean()

    hrv_score   = (avg_hrv / avg_hrv_baseline) * 100 if avg_hrv_baseline else 50
    sleep_score = min(100, (sleep_duration / 480) * 100)
    hr_score    = (avg_hr_baseline / avg_hr) * 100 if avg_hr else 50

    recovery = (hrv_score * 0.4) + (sleep_score * 0.4) + (hr_score * 0.2)
    return max(0, min(100, recovery))


def sleepQuality(sleep_df, interruptions):
    if sleep_df.empty or "duration" not in sleep_df.columns:
        return 0
    total_sleep        = sleep_df["duration"].sum()
    interruption_penalty = sum(interruptions) * 0.5
    return max(0, min(100, (total_sleep - interruption_penalty) / 6))


def detectInterruptions(df):
    df["awake"] = df["steps"] > 10
    df["block"] = (df["awake"] != df["awake"].shift()).cumsum()
    interruptions = []
    for _, group in df.groupby("block"):
        if not group["awake"].iloc[0]:
            continue
        duration = len(group) * 5
        if 5 <= duration <= 20:
            interruptions.append(duration)
    return interruptions


def detectSleepAdvanced(df):
    df["sleep_candidate"] = (
        (df["steps"] < 10) &
        (df["heart_rate"] <= df["hr_baseline"] * 1.05) &
        (df["hrv"] >= df["hrv_baseline"] * 0.95)
    )
    df["block"] = (df["sleep_candidate"] != df["sleep_candidate"].shift()).cumsum()

    sleep_blocks = []
    for _, group in df.groupby("block"):
        if not group["sleep_candidate"].iloc[0]:
            continue
        duration = len(group) * 5
        if duration >= 30:
            sleep_blocks.append({
                "user_id":  group["user_id"].iloc[0],
                "start":    group["recorded_at"].iloc[0],
                "end":      group["recorded_at"].iloc[-1],
                "duration": duration,
            })

    sleep_df = pd.DataFrame(sleep_blocks)
    return df, sleep_df


def runSleepAnalysis(df):
    df, sleepDf        = detectSleepAdvanced(df)
    df                 = estimateSleepStage(df)
    _                  = detectSleepOnset(df)
    interruptions      = detectInterruptions(df)
    quality            = sleepQuality(sleepDf, interruptions)
    recovery           = recoveryScore(df, sleepDf)

    save_sleep(sleepDf, quality)
    if not df.empty:
        saveRecovery(df["user_id"].iloc[0], recovery)

    print(f"Sleep sessions found: {len(sleepDf)}, quality: {quality:.1f}, recovery: {recovery:.1f}")