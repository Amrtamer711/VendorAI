import os
import time
import threading
import sqlite3
from datetime import datetime, timezone
import pytz
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from config import SHARED_DRIVE_ID, ENV

# DB path and name
if ENV == "render":
    DB_NAME = "usage_logs_render.db"
    DB_PATH = "/VendorAI/Data/usage_logs_render.db"
    JSON_PATH = "/VendorAI/Data/routes-key.json"
else:
    DB_NAME = "usage_logs_local.db"
    DB_PATH = "usage_logs.db"
    JSON_PATH = "routes-key.json"


# Google Drive setup
SCOPES = ["https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file(JSON_PATH, scopes=SCOPES)
drive_service = build("drive", "v3", credentials=creds)

# Thread safety
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
    utc_now = datetime.now(timezone.utc)
    gst = pytz.timezone("Asia/Dubai")
    local_time = utc_now.astimezone(gst)
    timestamp = local_time.isoformat()

    with db_lock:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                INSERT INTO usage_logs (user_id, username, rating, timestamp)
                VALUES (?, ?, ?, ?)
            """, (user_id, user_name, rating, timestamp))
            conn.commit()

def upload_db_file():
    file_metadata = {
        "name": DB_NAME,
        "parents": [SHARED_DRIVE_ID],
        "mimeType": "application/octet-stream"
    }
    media = MediaFileUpload(DB_PATH, mimetype="application/octet-stream")

    drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id, name",
        supportsAllDrives=True
    ).execute()

def periodic_drive_upload(interval_seconds=3600):
    def loop():
        while True:
            try:
                upload_db_file()
                print(f"✅ Uploaded {DB_NAME} to Drive")
            except Exception as e:
                print(f"❌ Drive upload failed: {e}")
            time.sleep(interval_seconds)

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
