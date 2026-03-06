import asyncio
import websockets
import json
import numpy as np
from datetime import datetime

#Generate fake data
anomalyChance = 0.05 # Chance an anamoly occurs


def createData(baseSteps, currentDay):
    anomalyFlag = False

    # gets current hour and day
    currentHour = datetime.now().hour
    print(currentHour)
    now = datetime.now()
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

##--------------- ANOMALY injection ----------------
    if np.random.rand() < anomalyChance:
        anomalyFlag = True
        anomalyType = np.random.choice([
            "activitySpike",
            "heartRateSpike",
            "nightActivitySpike"
        ])
        if anomalyType == "activitySpike":
            stepIncrement = int(np.random.randint(180, 250))
            heartRate = float(np.random.normal(120, 10))

        elif anomalyType == "heartRateSpike":
            heartRate = float(np.random.normal(70, 5))

        elif anomalyType == "nightActivitySpike" and 22 <= currentHour < 6:
            stepIncrement = int(np.random.randint(50, 120))
            heartRate = float(np.random.normal(95, 6))

        print("--- anomaly ---")
# ---------------- data package ---------------------
    data = {
        "steps": baseSteps,
        "step_increment": stepIncrement,
        "active_minutes": activeMinutes,
        "heart_rate": heartRate,
        "flag": anomalyFlag,
        "date + hour": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    }

    return data, baseSteps, currentDay


# -----------------------------
# WebSocket Client Function
# -----------------------------
async def stream_data():
    uri = "ws://127.0.0.1:8000/ws"
    baseSteps = 0

    async with websockets.connect(uri) as websocket:
        print("Connected to server")
        timePeriod =60 # 1 minute

        currentDay = datetime.now().date()
        print(currentDay, "today")

        while True:
            data, baseSteps, currentDay = createData(baseSteps, currentDay)
            await websocket.send(json.dumps(data))
            print("Sent:", data)

            await asyncio.sleep(timePeriod)



asyncio.run(stream_data())