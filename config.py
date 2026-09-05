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

if os.getenv("DB_SSL", "true").lower() in ("true", "1", "yes"):
    DB_CONFIG["ssl"] = {"ssl": True}


# --- Connection Pooling (DBUtils) ---
# Hər request yeni TCP+SSL bağlantısı açmaq əvəzinə pool istifadə olunur.
# DBUtils quraşdırılmayıbsa avtomatik köhnə üsula qayıdır.
_pool = None
try:
    from dbutils.pooled_db import PooledDB
    _pool = PooledDB(
        creator=pymysql,
        mincached=2,        # həmişə açıq saxlanan bağlantı
        maxcached=8,        # pool-da maksimum boş bağlantı
        maxconnections=20,  # ümumi limit
        blocking=True,      # limit dolu olsa gözlə
        ping=1,             # istifadədən əvvəl canlılıq yoxlaması
        **DB_CONFIG
    )
except ImportError:
    _pool = None


def get_db_connection():
    """Pool varsa pool-dan, yoxsa adi bağlantı.
    Pool bağlantısının close() — ona görə mövcud kod dəyişmir."""
    if _pool is not None:
        return _pool.connection()
    return pymysql.connect(**DB_CONFIG)
