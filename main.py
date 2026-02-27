import mysql.connector
import pandas as pd
import numpy as np
import time
from datetime import datetime

def sqlConnect():
    print("connecting to MySQL database...")
    mydb = mysql.connector.connect(
        host="localhost",
        user="root",
        passwd="",
        database="smart_health"
    )
    cursor = mydb.cursor()

    print("connected to MySQL database")
    return mydb, cursor

def createData(name, mydb1, cursor):

    interval = 5  # how often new data is generated

    np.random.seed(42)

    # Create CSV file with headers
    #~~~~~~~~~~~~~~Old code to output to csv file~~~~~~~~~~#
    #output_file = "realtime_health_data.csv"
    #columns = ["user", "timestamp", "steps", "active_minutes", "heart_rate", "sleep_hours"]
    #df = pd.DataFrame(columns=columns)
    #df.to_csv(output_file, index=False)

    print("Starting real-time health data simulation...")
    print("Press CTRL + C to stop.\n")

    # Baseline values
    base_steps = 0
    base_sleep = 7

    try:
        while True:
            timestamp = datetime.now()

            # Simulate step accumulation
            step_increment = np.random.randint(0, 20)
            base_steps += step_increment

            # Simulate active minutes (low during rest)
            active_minutes = np.random.choice([0, 1], p=[0.7, 0.3])

            # Simulate heart rate with natural fluctuation
            heart_rate = np.random.normal(70, 5)

            # Simulate sleep variation (only meaningful once per day, but included for demo)
            sleep_hours = round(np.random.normal(base_sleep, 0.2), 2)

            # Append to CSV
            # Create record
            #new_data = {
            #    "user": name,
            #    "timestamp": timestamp,
            #    "steps": base_steps,
            #    "active_minutes": active_minutes,
            #    "heart_rate": round(heart_rate, 1),
            #    "sleep_hours": sleep_hours
            #}
            #pd.DataFrame([new_data]).to_csv(output_file, mode='a', header=False, index=False)

            # sql method
            sql = """
                  INSERT INTO health_data
                      (timestamp, steps, active_minutes, heart_rate, sleep_hours)
                  VALUES (%s, %s, %s, %s, %s) \
                  """
            values = (
                timestamp,
                int(base_steps),
                int(active_minutes),
                float(round(heart_rate, 1)),
                float(sleep_hours)
            )
            cursor.execute(sql, values)
            mydb1.commit()

            print(f"inserted data for {name} at {timestamp}")
            # Wait before generating next data point
            time.sleep(interval)

    except KeyboardInterrupt:
        print("\nSimulation stopped.")
        cursor.close()
        mydb1.close()


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    mydb, cursor = sqlConnect()
    createData('user1', mydb, cursor)


