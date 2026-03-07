import json
from mysql.connector import pooling
from Database import getPool as getDBPool
from fastapi import FastAPI, WebSocket
from datetime import datetime
from sleepDetector import ColeKripkeDetector

app = FastAPI()
db = None
sd = ColeKripkeDetector()

#insert to db
def insertIntoDb(data):
    connection = getDBPool().get_connection()
    cursor = connection.cursor()

    user1 = "1" # temp for now

    sql = """
          INSERT INTO raw_sensor_data
          (user_id, heart_rate, hrv, steps, skin_temperature, skin_conductance, recorded_at)
          VALUES (%s, %s, %s, %s, %s, %s, %s) \
          """

    values = (
        user1,
        data['heart_rate'],
        data['hrv'],
        data['steps'],
        data['skinTemp'],
        data['skinCond'],
        data['timestamp']


    )

    cursor.execute(sql, values)
    connection.commit()

    sql ="""
    INSERT INTO raw_location_data
        (user_id, latitude, longitude, recorded_at)
        VALUES (%s, %s, %s, %s) \
        """
    values = (
        user1,
        data["location"]['latitude'],
        data["location"]['longitude'],
        data['timestamp']
    )
    cursor.execute(sql, values)
    connection.commit()

    cursor.close()
    connection.close() # return to pool
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Connected")

    while True:
        data = await websocket.receive_json()
        insertIntoDb(data)

        print("inserted", data)
