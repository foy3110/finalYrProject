import mysql.connector
from mysql.connector import Error
import json
import numpy as np
from datetime import datetime, timedelta

# ---------------- Simulation Parameters ---------------- #
anomalyChance = 0.05
baseLat = 50.8225
baseLon = -0.1372

# ---------------- Mental Health Model ---------------- #
def createMentalHealthData(hr, hrv, skinCond, steps):
    mood, stress, anxiety, energy = 6, 4, 3, 6
    if hrv < 30: stress += 3; anxiety += 2; mood -= 2
    if skinCond > 4: stress += 2; anxiety += 1
    if hr > 100: stress += 2; anxiety += 2
    if steps > 4000: mood += 2; energy += 2
    return {
        "mood": max(1, min(10, mood)),
        "stress": max(1, min(10, stress)),
        "anxiety": max(1, min(10, anxiety)),
        "energy": max(1, min(10, energy))
    }

# ---------------- Data Simulation ---------------- #
def createData(baseSteps, currentTime):
    anomalyFlag = False
    mentalData = None
    hour = currentTime.hour

    # Steps and heart rate
    if 6 <= hour < 9:
        stepIncrement = int(np.random.randint(20, 60))
        heartRate = float(np.random.normal(85, 5))
        activeMinutes = 1
    elif 9 <= hour < 17:
        stepIncrement = int(np.random.randint(10, 40))
        heartRate = float(np.random.normal(75, 5))
        activeMinutes = int(np.random.choice([0, 1], p=[0.5, 0.5]))
    elif 17 <= hour < 22:
        stepIncrement = int(np.random.randint(5, 30))
        heartRate = float(np.random.normal(80, 6))
        activeMinutes = int(np.random.choice([0, 1], p=[0.4, 0.6]))
    else:
        stepIncrement = 0
        heartRate = float(np.random.normal(58, 2))
        activeMinutes = 0

    baseSteps += stepIncrement

    # Physiological sensors
    hrv = float(np.random.normal(55, 10))
    skinTemp = float(np.random.normal(34, 1))
    skinCond = float(np.random.normal(1.5, 0.5))

    # Location
    if hour >= 22 or hour < 6:
        latitude = baseLat + np.random.normal(0, 0.00002)
        longitude = baseLon + np.random.normal(0, 0.00002)
    else:
        latitude = baseLat + np.random.normal(0, 0.0005)
        longitude = baseLon + np.random.normal(0, 0.0005)

    # Mental health
    mentalState = createMentalHealthData(heartRate, hrv, skinCond, baseSteps)

    # Adjust physiological based on mental health
    if mentalState["stress"] > 7:
        heartRate += np.random.normal(8, 2)
        skinCond += np.random.normal(1, 0.3)
    if mentalState["energy"] < 4:
        stepIncrement = int(stepIncrement * 0.5)
    if mentalState["mood"] < 3:
        hrv -= np.random.normal(10, 3)

    # MH reporting
    if hour in [9, 14, 19]:
        mentalData = {"type": "momentCheckin", **mentalState}
    elif hour == 22:
        mentalData = {"type": "dailyRecap", **mentalState}

    # Anomaly injection
    if np.random.rand() < anomalyChance:
        anomalyFlag = True
        anomalyType = np.random.choice(["activitySpike", "heartRateSpike", "hrvDrop", "stressSpike"])
        if anomalyType == "activitySpike":
            stepIncrement = int(np.random.randint(180, 250))
            heartRate = float(np.random.normal(130, 10))
        elif anomalyType == "heartRateSpike":
            heartRate = float(np.random.normal(130, 10))
        elif anomalyType == "hrvDrop":
            hrv = float(np.random.normal(10, 2))
        elif anomalyType == "stressSpike":
            skinCond = float(np.random.normal(8, 2))

    data = {
        "timestamp": currentTime.strftime('%Y-%m-%d %H:%M:%S'),
        "steps": baseSteps,
        "step_increment": stepIncrement,
        "active_minutes": activeMinutes,
        "heart_rate": heartRate,
        "hrv": hrv,
        "skinTemp": skinTemp,
        "skinCond": skinCond,
        "latitude": latitude,
        "longitude": longitude,
        "mental_health": json.dumps(mentalData),
        "anomaly_flag": anomalyFlag
    }

    return data, baseSteps

# ---------------- Generate Full Month ---------------- #
def generate_month_data():
    all_data = []
    baseSteps = 0
    startTime = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    totalMinutes = 30 * 24 * 60
    for minuteOffset in range(totalMinutes):
        currentTime = startTime + timedelta(minutes=minuteOffset)
        if currentTime.hour == 0 and currentTime.minute == 0:
            baseSteps = 0
        data, baseSteps = createData(baseSteps, currentTime)
        all_data.append(data)
    return all_data

# ---------------- MySQL Insert ---------------- #
def insert_into_mysql(data_batch, connection):
    cursor = connection.cursor()
    insert_query = """
        INSERT INTO health_data 
        (timestamp, steps, step_increment, active_minutes, heart_rate, hrv, skinTemp, skinCond,
         latitude, longitude, mental_health, anomaly_flag)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    values = [
        (
            d["timestamp"], d["steps"], d["step_increment"], d["active_minutes"],
            d["heart_rate"], d["hrv"], d["skinTemp"], d["skinCond"],
            d["latitude"], d["longitude"], d["mental_health"], d["anomaly_flag"]
        ) for d in data_batch
    ]
    cursor.executemany(insert_query, values)
    connection.commit()
    cursor.close()

# ---------------- Main ---------------- #
def main():
    try:
        connection = mysql.connector.connect(
            host="127.0.0.1",
            user="root",
            password="",  # change if you have a password
            database="smart_health"
        )
        print("Connected to MySQL")

        all_data = generate_month_data()
        batch_size = 500  # safe batch size

        for i in range(0, len(all_data), batch_size):
            batch = all_data[i:i+batch_size]
            insert_into_mysql(batch, connection)
            print(f"Inserted batch {i//batch_size + 1} ({len(batch)} rows)")

        print("All 30 days of data inserted successfully.")

    except Error as e:
        print("Error:", e)
    finally:
        if connection.is_connected():
            connection.close()
            print("MySQL connection closed.")

if __name__ == "__main__":
    main()