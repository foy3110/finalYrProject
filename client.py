import asyncio
import websockets
import json
from datetime import datetime

uri = "wss://finalyrproject-production-20f4.up.railway.app/ws"

async def stream_data():
    while True:
        try:
            async with websockets.connect(uri) as ws:
                print("Connected")

                while True:
                    data = {
                        "heart_rate": 80,
                        "hrv": 60,
                        "steps": 10,
                        "skinTemp": 36.5,
                        "skinCond": 0.3,
                        "timestamp": str(datetime.now()),
                        "anomaly_flag": 0,
                        "location": {
                            "latitude": 51.5,
                            "longitude": -0.12
                        }
                    }

                    await ws.send(json.dumps(data))
                    print("sent")

                    await asyncio.sleep(1)

        except Exception as e:
            print("Reconnecting...", e)
            await asyncio.sleep(3)

asyncio.run(stream_data())