from dotenv import load_dotenv
import os

load_dotenv()  # Loads variables from .env

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY")
ENV = os.getenv("ENV")
SHARED_DRIVE_ID = os.getenv("SHARED_DRIVE_ID")