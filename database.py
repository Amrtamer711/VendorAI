import sqlite3
import threading
from datetime import datetime, timezone

DB_PATH = "usage_logs.db"
db_lock = threading.Lock()

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS usage_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            username TEXT,
            rating INTEGER,
            timestamp TEXT
        );
        """)
        conn.commit()

def log_message(user_id, user_name, rating):
    timestamp = datetime.now(timezone.utc).isoformat()
    with db_lock:
        with sqlite3.connect("chat_logs.db") as conn:
            conn.execute("""
                INSERT INTO usage_logs (user_id, username, rating)
                VALUES (?, ?, ?)
            """, (user_id, user_name, rating, timestamp))
            conn.commit()
