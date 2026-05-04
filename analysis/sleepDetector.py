import pandas as pd
from serverFol.Database import getPool as getDbPool

# saves the sleep session into sleep analysis
def saveSleep(sleepDf, quality):
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

#save recovery to recovery_analysis db
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

# deep sleep = hrv > baseline *1.2 & hr < baseline *0.9
# rem sleep = hrv  > baseline
#light sleep = anything else that isnt awake
# only runs for sleep sessions(30+ minutes)
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

## gets averages
# uses them to determine score
# recovery = hrv score * .4 + sleep score *0.3 + heart rate score *0.3
def recoveryScore(df, sleepf):
    sleep_duration = sleepf["duration"].sum() if not sleepf.empty and "duration" in sleepf.columns else 0

    avgHrv           = df["hrv"].mean()
    avgHrvBaseline  = df["hrv_baseline"].mean()
    avgHr            = df["heart_rate"].mean()
    avgHrBaseline   = df["hr_baseline"].mean()

    hrvScore   = (avgHrv / avgHrvBaseline) * 100 if avgHrvBaseline else 50
    sleepScore = min(100, (sleep_duration / 480) * 100)
    hrScore    = (avgHrBaseline / avgHr) * 100 if avgHr else 50

    recovery = (hrvScore * 0.4) + (sleepScore * 0.4) + (hrScore * 0.2)
    return max(0, min(100, recovery))

# 0-100 score
# sleep duration - 0.5 * interruption length / 6
def sleepQuality(sleepdf, interruptions):
    if sleepdf.empty or "duration" not in sleepdf.columns:
        return 0
    total_sleep        = sleepdf["duration"].sum()
    interruptionPenalty = sum(interruptions) * 0.5
    return max(0, min(100, (total_sleep - interruptionPenalty) / 6))

# checks if step count is over 10
# adds the lenfth above 10
# adds it as a duration
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

## sleep = steps <10 &
#          heart rate <= baseline *1.05
#            hrv       > = baseline *0.95
#only when its for at least 30 or more minutes/ 30+ records
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

## sleep run function
#called by the pipeline
def runSleepAnalysis(df):
    df, sleepDf        = detectSleepAdvanced(df)
    df                 = estimateSleepStage(df)
    _                  = detectSleepOnset(df)
    interruptions      = detectInterruptions(df)
    quality            = sleepQuality(sleepDf, interruptions)
    recovery           = recoveryScore(df, sleepDf)

    saveSleep(sleepDf, quality)
    if not df.empty:
        saveRecovery(df["user_id"].iloc[0], recovery)

    print(f"Sleep sessions found: {len(sleepDf)}, quality: {quality:.1f}, recovery: {recovery:.1f}")