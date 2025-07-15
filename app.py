from collections import defaultdict
from flask import request, jsonify
from database import init_db
from recon import process_clean_vendor_reconciliation, process_dirty_vendor_reconciliation
from file_handler import download_slack_file
from prompts import rules_message
from clients import slack_app, flask_app, handler
import os
from utils import get_user_profile, prompt_star_rating
import re
from database import log_message

user_file_store = defaultdict(dict)

@slack_app.action(re.compile(r"^rate_([1-5])$"))
def handle_rating(ack, body, say):
    ack()
    user_id = body["user"]["id"]
    username = body["user"].get("username") or body["user"].get("name") or "Unknown"
    rating = int(body["actions"][0]["value"])

    log_message(user_id, username, rating)
    say(f"Thanks for rating this reconciliation {rating} ⭐")

@slack_app.event("message")
def handle_file_dm(event, say):
    if "rules" in event.get("text", "").lower():
        say(rules_message)
        return

    if event.get("channel_type") == "im" and "files" in event:
        user = event["user"]
        channel = event["channel"]
        profile = get_user_profile(user)
        name = profile.get("display_name") or profile.get("real_name")

        for file_info in event["files"]:
            download_slack_file(file_info, user, user_file_store)

        if not all(key in user_file_store[user] for key in ("vendor", "soa")):
            say("📄 Waiting for both SOA and Vendor files...")
            return

        vendor_path = user_file_store[user]["vendor"]
        soa_path = user_file_store[user]["soa"]

        message_lines = event.get("text", "").splitlines()
        message_lines = [line.strip() for line in message_lines if line.strip()]

        is_clean = is_dirty = False
        user_comments = None

        if message_lines:
            first_line_lower = message_lines[0].lower()
            is_clean = "clean" in first_line_lower
            is_dirty = "dirty" in first_line_lower

            if is_dirty and len(message_lines) > 1:
                user_comments = "\n".join(message_lines[1:])


        if is_clean:
            process_clean_vendor_reconciliation(vendor_path, soa_path, say, channel)
            prompt_star_rating(say, user_id=user, user_name=name)  

        elif is_dirty:
            process_dirty_vendor_reconciliation(vendor_path, soa_path, say, channel, user_comments)
            prompt_star_rating(say, user_id=user, user_name=name)  
        else:
            say("❓ Please specify whether the files are `clean` or `dirty` in your message.")

@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    if request.json and "challenge" in request.json:
        return jsonify({"challenge": request.json["challenge"]})
    return handler.handle(request)

if __name__ == "__main__":
    # flask_app.run(port=3000)
    init_db()
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Flask starting on port {port}")
    flask_app.run(host="0.0.0.0", port=port)

