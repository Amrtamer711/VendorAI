from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from slack_sdk import WebClient
from openai import OpenAI
from config import SLACK_BOT_TOKEN, SLACK_SIGNING_SECRET, OPENAI_API_KEY
from collections import defaultdict
from flask import Flask

slack_app = App(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGNING_SECRET)
flask_app = Flask(__name__)
handler = SlackRequestHandler(slack_app)
web_client = WebClient(token=SLACK_BOT_TOKEN)
client = OpenAI(api_key=OPENAI_API_KEY, timeout=3600)

user_history = defaultdict(list)
user_file_store = defaultdict(dict)
MAX_HISTORY_LENGTH = 6
