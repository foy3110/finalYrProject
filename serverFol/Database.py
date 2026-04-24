from mysql.connector import pooling
from serverFol.Config import DBCONFIG

_pool = None


def getPool():
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name=DBCONFIG["pool_name"],
            pool_size=DBCONFIG["pool_size"],
            host=DBCONFIG["host"],
            port=DBCONFIG["port"],
            user=DBCONFIG["user"],
            password=DBCONFIG["password"],
            database=DBCONFIG["database"],
        )
    return _pool