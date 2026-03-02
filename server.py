import json
import mysql.connector
from fastapi import FastAPI, WebSocket
from datetime import datetime

app = FastAPI()
db = None

##DB connection
def connect_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="smart_health",
    )
#insert to db
def insert_into_db(data):
    db = connect_db()
    cursor = db.cursor()
    user1 = "user"
    sql = """
    INSERT INTO health_data
    (user_id, timestamp, steps, active_minutes, heart_rate)
    VALUES (%s,%s, %s, %s, %s)
    """
    values = (
        user1,
        datetime.now(),
        int(data["steps"]),
        int(data["active_minutes"]),
        float(data["heart_rate"]),
    )
    cursor.execute(sql, values)
    db.commit()

    cursor.close()
    db.close()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Connected")

    while True:
        data = await websocket.receive_json()

        insert_into_db(data)

        print("inserted", data)
