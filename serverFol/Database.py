from mysql.connector import pooling
from serverFol.Config import DBCONFIG

#connector for the serverFol
def getPool():
    pool = pooling.MySQLConnectionPool(
            pool_name=DBCONFIG['pool_name'],
            pool_size=DBCONFIG['pool_size'],
            host=DBCONFIG['host'],
            user=DBCONFIG['user'],
            password=DBCONFIG['password'],
            database=DBCONFIG['serverFol'],
    )
    return pool