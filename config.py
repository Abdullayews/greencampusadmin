import os

import pymysql
from pymysql.cursors import DictCursor
from dbutils.pooled_db import PooledDB

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": int(os.getenv("DB_PORT", 4000)),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "charset": "utf8mb4",
    "cursorclass": DictCursor,
}

if os.getenv("DB_SSL", "true").lower() in ("true", "1", "yes"):
    DB_CONFIG["ssl"] = {"ssl": True}

# ---------------------------------------------------------------------------
# Connection Pool (DBUtils) — close() pool-a qaytarır, with_db dəyişmir
# ---------------------------------------------------------------------------
POOL = PooledDB(
    creator=pymysql,
    maxconnections=int(os.getenv("DB_POOL_MAX", 10)),
    mincached=2,
    maxcached=int(os.getenv("DB_POOL_CACHED", 5)),
    blocking=True,
    ping=1,
    **DB_CONFIG
)


def get_db_connection():
    return POOL.connection()
