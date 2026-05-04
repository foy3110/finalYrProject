import mysql.connector
from mysql.connector import Error
import numpy as np
from datetime import datetime, timedelta

# Railway DB config
DB_CONFIG = {
    "host":     "shuttle.proxy.rlwy.net",
    "port":     28489,
    "user":     "root",
    "password": "BfdXtpjtSMaUnTSBroOmDfbxXfVZhCZL",
    "database": "railway",
}

ANOMALYCHANCE = 0.05
BASELAT       = 50.8225
BASELON       = -0.1372
USERID        = "1"

    # creates mental health data
def createMentalHealthData(hr, hrv, skinCond, steps):
    mood, stress, anxiety, energy = 6, 4, 3, 6
    if hrv < 30:        stress += 3; anxiety += 2; mood -= 2
    if skinCond > 4:    stress += 2; anxiety += 1
    if hr > 100:        stress += 2; anxiety += 2
    if steps > 4000:    mood += 2;   energy += 2
    return {
        "mood":    max(1, min(10, mood)),
        "stress":  max(1, min(10, stress)),
        "anxiety": max(1, min(10, anxiety)),
        "energy":  max(1, min(10, energy)),
    }


def createData(baseSteps, currentTime):
    anomalyFlag = False
    hour = currentTime.hour

    if 6 <= hour < 9:
        stepIncrement = int(np.random.randint(20, 60))
        heartRate     = float(np.random.normal(85, 5))
    elif 9 <= hour < 17:
        stepIncrement = int(np.random.randint(10, 40))
        heartRate     = float(np.random.normal(75, 5))
    elif 17 <= hour < 22:
        stepIncrement = int(np.random.randint(5, 30))
        heartRate     = float(np.random.normal(80, 6))
    else:
        stepIncrement = 0
        heartRate     = float(np.random.normal(58, 2))

    baseSteps += stepIncrement
    hrv      = float(np.random.normal(55, 10))
    skinTemp = float(np.random.normal(34, 1))
    skinCond = float(np.random.normal(1.5, 0.5))

    if hour >= 22 or hour < 6:
        latitude  = BASELAT + np.random.normal(0, 0.00002)
        longitude = BASELON + np.random.normal(0, 0.00002)
    else:
        latitude  = BASELAT + np.random.normal(0, 0.0005)
        longitude = BASELON + np.random.normal(0, 0.0005)

    mentalState = createMentalHealthData(heartRate, hrv, skinCond, baseSteps)

    if mentalState["stress"] > 7:
        heartRate += np.random.normal(8, 2)
        skinCond  += np.random.normal(1, 0.3)
    if mentalState["energy"] < 4:
        stepIncrement = int(stepIncrement * 0.5)
    if mentalState["mood"] < 3:
        hrv -= np.random.normal(10, 3)

    if np.random.rand() < ANOMALYCHANCE:
        anomalyFlag = True
        anomalyType = np.random.choice(["activitySpike", "heartRateSpike", "hrvDrop", "stressSpike"])
        if anomalyType == "activitySpike":
            stepIncrement = int(np.random.randint(180, 250))
            heartRate     = float(np.random.normal(130, 10))
        elif anomalyType == "heartRateSpike":
            heartRate = float(np.random.normal(130, 10))
        elif anomalyType == "hrvDrop":
            hrv = float(np.random.normal(10, 2))
        elif anomalyType == "stressSpike":
            skinCond = float(np.random.normal(8, 2))

    timestamp = currentTime.strftime("%Y-%m-%d %H:%M:%S")

    sensor_row = (
        USERID, heartRate, hrv, baseSteps,
        skinTemp, skinCond, timestamp, anomalyFlag
    )
    location_row = (
        USERID, latitude, longitude, timestamp, anomalyFlag
    )

    return sensor_row, location_row, baseSteps


def generateMonthData():
    sensor_rows   = []
    location_rows = []
    baseSteps     = 0
    startTime     = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    for minuteOffset in range(30 * 24 * 60):
        currentTime = startTime + timedelta(minutes=minuteOffset)
        if currentTime.hour == 0 and currentTime.minute == 0:
            baseSteps = 0
        sensor_row, location_row, baseSteps = createData(baseSteps, currentTime)
        sensor_rows.append(sensor_row)
        location_rows.append(location_row)

    return sensor_rows, location_rows


def insertBatch(cursor, sensor_batch, location_batch):
    cursor.executemany(
        """
        INSERT INTO raw_sensor_data
            (user_id, heart_rate, hrv, steps,
             skin_temperature, skin_conductance, recorded_at, anomaly_flag)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        sensor_batch
    )
    cursor.executemany(
        """
        INSERT INTO raw_location_data
            (user_id, latitude, longitude, recorded_at, anomaly_flag)
        VALUES (%s, %s, %s, %s, %s)
        """,
        location_batch
    )


def main():
    connection = None
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        print("Connected to Railway MySQL")

        sensor_rows, location_rows = generateMonthData()
        print(f"Generated {len(sensor_rows)} rows — inserting...")

        cursor     = connection.cursor()
        batch_size = 500

        for i in range(0, len(sensor_rows), batch_size):
            insertBatch(
                cursor,
                sensor_rows[i:i + batch_size],
                location_rows[i:i + batch_size],
            )
            connection.commit()
            print(f"Inserted batch {i // batch_size + 1} ({min(batch_size, len(sensor_rows) - i)} rows)")

        cursor.close()
        print("All 30 days of data inserted successfully.")

    except Error as e:
        print("Error:", e)
    finally:
        if connection and connection.is_connected():
            connection.close()
            print("Connection closed.")


if __name__ == "__main__":
    main()