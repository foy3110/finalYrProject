import os

DBCONFIG = {
    "host":      os.getenv("DB_HOST"),
    "port":      int(os.getenv("DB_PORT") or 3306),
    "user":      os.getenv("DB_USER"),
    "password":  os.getenv("DB_PASSWORD"),
    "database":  os.getenv("DB_NAME"),
    "pool_name": "health_pool",
    "pool_size": 5,
}