import os
import pymysql
from pymysql.cursors import DictCursor

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": int(os.getenv("DB_PORT", 4000)),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "charset": "utf8mb4",
    "cursorclass": DictCursor,
}

# SSL yalnız əgər tələb olunarsa aktiv olur (default: true)
# Lokal test üçün DB_SSL=false edə bilərsən
if os.getenv("DB_SSL", "true").lower() in ("true", "1", "yes"):
    DB_CONFIG["ssl"] = {"ssl": True}


def get_db_connection():
    """Sadəcə connection obyekti qaytarır. Xəta tutulmur — Flask error handler tutacaq."""
    return pymysql.connect(**DB_CONFIG)
