import asyncio
import websockets
import json
import numpy as np
from datetime import datetime

#Generate fake data

# Chance an anomaly occurs
anomalyChance = 0.05
timePeriod = 60  # 1 minute

#base latitude and longitudinal data
baseLat = 50.8225
baseLon = -0.1372


#-----Mental-Health-Model-----#
def createMentalHealthData(hr, hrv, skinCond, steps):
    mood = 6
    stress = 4
    anxiety = 3
    energy = 6

    #hrv
    if hrv < 30:
        stress += 3
        anxiety += 2
        mood -= 2
    # skin conductance
    if skinCond > 4:
        stress += 2
        anxiety += 1
    #heart rate
    if hr > 100:
        stress += 2
        anxiety += 2
    # physical activity effect
    if steps >4000:
        mood += 2
        energy += 2

    mood = max(1, min(10, mood))
    stress = max(1, min(10, stress))
    anxiety = max(1, min(10, anxiety))
    energy = max(1, min(10, energy))

    return {
        "mood": mood,
        "stress": stress,
        "anxiety": anxiety,
        "energy": energy
    }


def createData(baseSteps, currentDay):
    anomalyFlag = False
    mentalData = None

    # gets current hour and day
    currentHour = datetime.now().hour
    now = datetime.now()
    print("now:", now)

    #resets step counter when new day

    if now.date() != currentDay:
        print("--- new-day ---")
        baseSteps = 0
        currentDay = datetime.now().date()


    ## morning data
    if 6 <= currentHour < 9:
        stepIncrement = int(np.random.randint(20, 60))
        heartRate = float(np.random.normal(85, 5))
        activeMinutes = 1

        # Work
    elif 9 <= currentHour < 17:
        stepIncrement = int(np.random.randint(10, 40))
        heartRate = float(np.random.normal(75, 5))
        activeMinutes = int(np.random.choice([0, 1], p=[0.5, 0.5]))

        # Evening
    elif 17 <= currentHour < 22:
        stepIncrement = int(np.random.randint(5, 30))
        heartRate = float(np.random.normal(80, 6))
        activeMinutes = int(np.random.choice([0, 1], p=[0.4, 0.6]))

        # Night (sleep state)
    else:
        stepIncrement = 0
        heartRate = float(np.random.normal(58, 2))
        activeMinutes = 0

    baseSteps += stepIncrement

    #---------physiological-sensors---------

    hrv = float(np.random.normal(55, 10))
    skinTemp = float(np.random.normal(34, 1))
    skinCond = float(np.random.normal(1.5, 0.5))

    #---------Location-Sim---------
    if 22 <= currentHour < 6:
        #sleep movement basically stationary except noise
        latitude = baseLat + np.random.normal(0, 0.00002)
        longitude = baseLon + np.random.normal(0, 0.00002)
    else:
        latitude = baseLat + np.random.normal(0, 0.0005)
        longitude = baseLon + np.random.normal(0, 0.0005)

    #---------MH-Based-On-Physical---------
    mentalState = createMentalHealthData(
        heartRate,
        hrv,
        skinCond,
        baseSteps
    )

    #---------Physical-Based-On-MH----------
    if mentalState["stress"]> 7:
        heartRate += np.random.normal(8, 2)
        skinCond += np.random.normal(1, 0.3)

    if mentalState["energy"] < 4:
        stepIncrement = int(stepIncrement * 0.5)


    if mentalState["mood"] < 3:
        hrv -= np.random.normal(10, 3)

    #---------------MH-Reporting---------------
    if currentHour in [9,14,19]:
        mentalData = {
            "type":"momentCheckin",
            **mentalState
        }
    elif currentHour == 22:
        mentalData = {"type":"dailyRecap",
            **mentalState}

    ##--------------- ANOMALY injection ----------------
    if np.random.rand() < anomalyChance:
        anomalyFlag = True
        anomalyType = np.random.choice([
            "activitySpike",
            "heartRateSpike",
            "hrvDrop",
            "stressSpike",
        ])
        if anomalyType == "activitySpike":
            stepIncrement = int(np.random.randint(180, 250))
            heartRate = float(np.random.normal(120, 10))

        elif anomalyType == "heartRateSpike":
            heartRate = float(np.random.normal(70, 5))

        elif anomalyType == "hrvDrop":

            hrv = float(np.random.normal(15, 3))

        elif anomalyType == "stressSpike":

            skinCond = float(np.random.normal(6, 1))

        print("--- anomaly ---")
# ---------------- data package ---------------------
    data = {
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),

        "steps": baseSteps,
        "step_increment": stepIncrement,
        "active_minutes": activeMinutes,

        "heart_rate": heartRate,
        "hrv": hrv,
        "skinTemp": skinTemp,
        "skinCond": skinCond,

        "location":{
            "latitude": latitude,
            "longitude": longitude,
        },

        "mental_health": mentalData,

        "flag": anomalyFlag,
    }

    return data, baseSteps, currentDay


# -----------------------------
# WebSocket Client Function
# -----------------------------
async def stream_data():
    uri = "ws://127.0.0.1:8000/ws"

    baseSteps = 0
    currentDay = datetime.now().date()

    async with websockets.connect(uri) as websocket:
        print("Connected to server")

        while True:

            data, baseSteps, currentDay = createData(
                baseSteps,
                currentDay

            )
            await websocket.send(json.dumps(data))
            print("Sent:", data)

            await asyncio.sleep(timePeriod)



asyncio.run(stream_data())