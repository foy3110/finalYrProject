from mysql.connector import pooling
from serverFol.Config import DBCONFIG
import os
import mysql.connector.pooling

#connector for the serverFol
def getPool():
    dbconfig = {
        "host": os.getenv("DB_HOST"),
        "port": int(os.getenv("DB_PORT", 3306)),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "database": os.getenv("DB_NAME"),
    }

    pool = mysql.connector.pooling.MySQLConnectionPool(
        pool_name="mypool",
        pool_size=5,
        **dbconfig
    )

    return pool