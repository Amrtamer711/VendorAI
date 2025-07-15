import sqlite3
import threading
from datetime import datetime, timezone

DB_PATH = "chat_logs.db"
db_lock = threading.Lock()

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            user_name TEXT,
            channel_id TEXT,
            role TEXT,
            message TEXT,
            timestamp TEXT
        );
        """)
        conn.commit()

def log_message(user_id, user_name, channel_id, role, message):
    timestamp = datetime.now(timezone.utc).isoformat()
    with db_lock:
        with sqlite3.connect("chat_logs.db") as conn:
            conn.execute("""
                INSERT INTO chat_logs (user_id, user_name, channel_id, role, message, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, user_name, channel_id, role, message, timestamp))
            conn.commit()
