import asyncio
import websockets
import json
import numpy as np
from datetime import datetime

# ─── config ──────────────────────────────────────────────────────────────────
ANOMALY_CHANCE = 0.05
TIME_PERIOD    = 60        # seconds between sends
BASE_LAT       = 50.8225
BASE_LON       = -0.1372
SERVER_URI     = "wss://finalyrproject-production-20f4.up.railway.app/ws"


# ─── mental health model ─────────────────────────────────────────────────────

def createMentalHealthData(hr, hrv, skinCond, steps):
    mood, stress, anxiety, energy = 6, 4, 3, 6
    if hrv < 30:        stress += 3; anxiety += 2; mood -= 2
    if skinCond > 4:    stress += 2; anxiety += 1
    if hr > 100:        stress += 2; anxiety += 2
    if steps > 4000:    mood += 2;   energy += 2

    if stress > 7:
        pass  # physiological feedback applied in createData

    return {
        "mood":    max(1, min(10, mood)),
        "stress":  max(1, min(10, stress)),
        "anxiety": max(1, min(10, anxiety)),
        "energy":  max(1, min(10, energy)),
    }


# ─── data generation ─────────────────────────────────────────────────────────

def createData(baseSteps, currentDay):
    anomalyFlag = False
    mentalData  = None

    now         = datetime.now()
    currentHour = now.hour

    if now.date() != currentDay:
        print("--- new day ---")
        baseSteps  = 0
        currentDay = now.date()

    if 6 <= currentHour < 9:
        stepIncrement = int(np.random.randint(20, 60))
        heartRate     = float(np.random.normal(85, 5))
        activeMinutes = 1
    elif 9 <= currentHour < 17:
        stepIncrement = int(np.random.randint(10, 40))
        heartRate     = float(np.random.normal(75, 5))
        activeMinutes = int(np.random.choice([0, 1], p=[0.5, 0.5]))
    elif 17 <= currentHour < 22:
        stepIncrement = int(np.random.randint(5, 30))
        heartRate     = float(np.random.normal(80, 6))
        activeMinutes = int(np.random.choice([0, 1], p=[0.4, 0.6]))
    else:
        stepIncrement = 0
        heartRate     = float(np.random.normal(58, 2))
        activeMinutes = 0

    baseSteps += stepIncrement

    hrv      = float(np.random.normal(55, 10))
    skinTemp = float(np.random.normal(34, 1))
    skinCond = float(np.random.normal(1.5, 0.5))

    if 22 <= currentHour or currentHour < 6:
        latitude  = BASE_LAT + np.random.normal(0, 0.00002)
        longitude = BASE_LON + np.random.normal(0, 0.00002)
    else:
        latitude  = BASE_LAT + np.random.normal(0, 0.0005)
        longitude = BASE_LON + np.random.normal(0, 0.0005)

    mentalState = createMentalHealthData(heartRate, hrv, skinCond, baseSteps)

    if mentalState["stress"] > 7:
        heartRate += np.random.normal(8, 2)
        skinCond  += np.random.normal(1, 0.3)
    if mentalState["energy"] < 4:
        stepIncrement = int(stepIncrement * 0.5)
    if mentalState["mood"] < 3:
        hrv -= np.random.normal(10, 3)

    if currentHour in [9, 14, 19]:
        mentalData = {"type": "momentCheckin", **mentalState}
    elif currentHour == 22:
        mentalData = {"type": "dailyRecap", **mentalState}

    if np.random.rand() < ANOMALY_CHANCE:
        anomalyFlag = True
        anomalyType = np.random.choice(["activitySpike", "heartRateSpike", "hrvDrop", "stressSpike"])
        if anomalyType == "activitySpike":
            stepIncrement = int(np.random.randint(180, 250))
            heartRate     = float(np.random.normal(120, 10))
        elif anomalyType == "heartRateSpike":
            heartRate = float(np.random.normal(130, 10))
        elif anomalyType == "hrvDrop":
            hrv = float(np.random.normal(15, 3))
        elif anomalyType == "stressSpike":
            skinCond = float(np.random.normal(6, 1))
        print(f"--- anomaly: {anomalyType} ---")

    data = {
        "timestamp":     now.strftime("%Y-%m-%d %H:%M:%S"),
        "steps":         baseSteps,
        "step_increment": stepIncrement,
        "active_minutes": activeMinutes,
        "heart_rate":    heartRate,
        "hrv":           hrv,
        "skinTemp":      skinTemp,
        "skinCond":      skinCond,
        "location": {
            "latitude":  latitude,
            "longitude": longitude,
        },
        "mental_health": mentalData,
        "flag":          anomalyFlag,
    }

    return data, baseSteps, currentDay


# ─── websocket client ─────────────────────────────────────────────────────────

async def stream_data():
    baseSteps  = 0
    currentDay = datetime.now().date()

    async with websockets.connect(SERVER_URI) as websocket:
        print(f"Connected to {SERVER_URI}")
        while True:
            data, baseSteps, currentDay = createData(baseSteps, currentDay)
            await websocket.send(json.dumps(data))
            print(f"Sent @ {data['timestamp']}")
            await asyncio.sleep(TIME_PERIOD)


if __name__ == "__main__":
    asyncio.run(stream_data())