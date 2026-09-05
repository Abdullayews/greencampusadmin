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

_pool = PooledDB(
    creator=pymysql,
    minconnections=2,
    maxconnections=10,
    maxusage=100,          # 100 sorğudan sonra bağlantı yenilənir
    blocking=True,         # pool boşsa gözlə (xəta yox)
    ping=1,                # ölü bağlantını avtomatik yoxla/yenilə
    **DB_CONFIG
)


def get_db_connection():
    """Pool-dan bağlantı — close() onu geri qaytarır, bağlamır."""
    return _pool.connection()
