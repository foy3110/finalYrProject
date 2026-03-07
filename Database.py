from mysql.connector import pooling
from Config import DBCONFIG

#connector for the database
def getPool():
    pool = pooling.MySQLConnectionPool(
            pool_name=DBCONFIG['pool_name'],
            pool_size=DBCONFIG['pool_size'],
            host=DBCONFIG['host'],
            user=DBCONFIG['user'],
            password=DBCONFIG['password'],
            database=DBCONFIG['database'],
    )
    return pool