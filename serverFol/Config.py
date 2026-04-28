import os


def _port():
    val = os.getenv("DB_PORT", "").strip()
    try:
        return int(val)
    except (ValueError, TypeError):
        return 3306


DBCONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": _port(),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "smart_health"),
    "pool_name": "health_pool",
    "pool_size": 5,
}