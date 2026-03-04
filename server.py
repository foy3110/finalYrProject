import json
import mysql.connector
from mysql.connector import pooling

from fastapi import FastAPI, WebSocket
from datetime import datetime
from sleepDetector import ColeKripkeDetector

app = FastAPI()
db = None
sd = ColeKripkeDetector()

# pool connection
pool = pooling.MySQLConnectionPool(
        pool_name="health_pool",
        pool_size=5,
        host="localhost",
        user="root",
        password="",
        database="smart_health",
)
##DB connection


#insert to db
def insertIntoDb(data):
    connection = pool.get_connection()
    cursor = connection.cursor()

    user1 = "user" # temp for now

    sql = """
          INSERT INTO health_data
          (user_id, timestamp, steps, step_increment, active_minutes, heart_rate, sleep_state, flag)
          VALUES (%s, %s, %s, %s, %s, %s, %s, %s) \
          """

    values = (
        user1,
        datetime.now(),
        data["steps"],
        data["step_increment"],
        data["active_minutes"],
        data["heart_rate"],
        data["sleep_state"],
        data["flag"],
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
        sleepState = sd.update(data["step_increment"])
        if sleepState is not None:
            data["sleep_state"] = sleepState
        else:
            data["sleep_state"] = 0
        insertIntoDb(data)

        print("inserted", data)
