from fastapi import FastAPI, WebSocket
from serverFol.Database import getPool
import json
import asyncio

app = FastAPI()

print("Server starting...")

# -----------------------
# SIMPLE BUFFER (IMPORTANT)
# -----------------------
buffer = []
BATCH_SIZE = 50


def insert_batch(batch):
    connection = getPool().get_connection()
    cursor = connection.cursor()

    sql_sensor = """
    INSERT INTO raw_sensor_data
    (user_id, heart_rate, hrv, steps, skin_temperature, skin_conductance, recorded_at, anomaly_flag)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """

    sql_location = """
    INSERT INTO raw_location_data
    (user_id, latitude, longitude, recorded_at, anomaly_flag)
    VALUES (%s, %s, %s, %s, %s)
    """

    for data in batch:
        user = "1"

        cursor.execute(sql_sensor, (
            user,
            data["heart_rate"],
            data["hrv"],
            data["steps"],
            data["skinTemp"],
            data["skinCond"],
            data["timestamp"],
            data["anomaly_flag"]
        ))

        cursor.execute(sql_location, (
            user,
            data["location"]["latitude"],
            data["location"]["longitude"],
            data["timestamp"],
            data["anomaly_flag"]
        ))

    connection.commit()
    cursor.close()
    connection.close()


async def batch_writer():
    while True:
        await asyncio.sleep(5)

        if len(buffer) >= BATCH_SIZE:
            batch = buffer[:BATCH_SIZE]
            del buffer[:BATCH_SIZE]

            try:
                insert_batch(batch)
                print(f"Inserted batch of {len(batch)}")
            except Exception as e:
                print("DB batch error:", e)


@app.on_event("startup")
async def startup():
    asyncio.create_task(batch_writer())
    print("Batch worker started")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Client connected")

    while True:
        try:
            data = await websocket.receive_json()
            buffer.append(data)

        except Exception as e:
            print("WebSocket error:", e)
            break