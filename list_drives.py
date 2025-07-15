from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from config import SHARED_DRIVE_ID

# 🔧 Make sure this scope is used
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

creds = Credentials.from_service_account_file("routes-key.json", scopes=SCOPES)
drive_service = build('drive', 'v3', credentials=creds)

# List shared drives
response = drive_service.drives().list(pageSize=100).execute()
drives = response.get('drives', [])

if not drives:
    print("🚫 No shared drives found.")
else:
    print("📁 Shared Drives your service account can access:")
    for drive in drives:
        print(f"- {drive['name']} (ID: {drive['id']})")


response = drive_service.files().list(
    corpora="drive",
    driveId=SHARED_DRIVE_ID,
    includeItemsFromAllDrives=True,
    supportsAllDrives=True,
    q="'{}' in parents and trashed = false".format(SHARED_DRIVE_ID),
    fields="files(id, name, mimeType)"
).execute()

items = response.get("files", [])

if not items:
    print("📭 No files found.")
else:
    print("📁 Files/Folders in Shared Drive:")
    for item in items:
        icon = "📄" if item["mimeType"] != "application/vnd.google-apps.folder" else "📁"
        print(f"{icon} {item['name']} (ID: {item['id']})")