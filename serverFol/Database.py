import os

from mysql.connector import pooling
from serverFol.Config import DBCONFIG

# create pool ONCE at import time (important for cloud)
pool = pooling.MySQLConnectionPool(
    DBCONFIG={
        "host": os.getenv("DB_HOST"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "database": os.getenv("DB_NAME"),
        "pool_name": "health_pool",
        "pool_size": 5
    }
)

def getPool():
    return pool