
from mysql.connector import pooling
from serverFol.Config import DBCONFIG

# create pool ONCE at import time (important for cloud)
pool = pooling.MySQLConnectionPool(
    pool_name=DBCONFIG['pool_name'],
    pool_size=DBCONFIG['pool_size'],
    host=DBCONFIG['host'],
    user=DBCONFIG['user'],
    password=DBCONFIG['password'],
    database=DBCONFIG['database'],
)

def getPool():
    return pool