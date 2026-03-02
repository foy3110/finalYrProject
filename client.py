import asyncio
import websockets
import json
import numpy as np
from datetime import datetime

#Generate fake data

def createData(base_steps):
    # step_increment = int(np.random.randint(0, 20))
    # base_steps += step_increment
    #
    # data = {
    #     "steps": base_steps,
    #     "active_minutes": int(np.random.choice([0, 1], p=[0.7, 0.3])),
    #     "heart_rate": float(np.random.normal(70, 5)),
    #     "sleep_hours": float(round(np.random.normal(7, 0.2), 2))
    # }
    #
    # return data, base_steps

    # gets current hour
    current_hour = datetime.now().hour

    ## morning data
    if 6 <= current_hour < 9:
        step_increment = int(np.random.randint(20, 60))
        heart_rate = float(np.random.normal(85, 5))
        active_minutes = 1

        # Work
    elif 9 <= current_hour < 17:
        step_increment = int(np.random.randint(10, 40))
        heart_rate = float(np.random.normal(75, 5))
        active_minutes = int(np.random.choice([0, 1], p=[0.5, 0.5]))

        # Evening
    elif 17 <= current_hour < 22:
        step_increment = int(np.random.randint(5, 30))
        heart_rate = float(np.random.normal(80, 6))
        active_minutes = int(np.random.choice([0, 1], p=[0.4, 0.6]))

        # Night (sleep state)
    else:
        step_increment = 0
        heart_rate = float(np.random.normal(58, 2))
        active_minutes = 0

    base_steps += step_increment

    data = {
        "steps": base_steps,
        "active_minutes": active_minutes,
        "heart_rate": heart_rate
    }

    return data, base_steps


# -----------------------------
# WebSocket Client Function
# -----------------------------
async def stream_data():
    uri = "ws://127.0.0.1:8000/ws"
    base_steps = 0

    async with websockets.connect(uri) as websocket:
        print("Connected to server")
        timePeriod = 60 # 1 minute
        while True:
            data, base_steps = createData(base_steps)
            await websocket.send(json.dumps(data))
            print("Sent:", data)

            await asyncio.sleep(timePeriod)



asyncio.run(stream_data())