import os
import pymysql
from pymysql.cursors import DictCursor
from pymysql.err import OperationalError
from flask import jsonify

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": int(os.getenv("DB_PORT", 4000)), 
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "charset": "utf8mb4",
    "cursorclass": DictCursor,
    "ssl": {"ssl": True} 
}

def get_db_connection():
    try:
        return pymysql.connect(**DB_CONFIG)
    except OperationalError as e:
        return jsonify({"success": False, "message": f"DB Bağlantı xətası: {e}"}), 500
