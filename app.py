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
from threading import Timer
from clients import web_client
from database import init_db, periodic_drive_upload
from config import ENV


user_file_store = defaultdict(dict)
pending_ratings = {}
rated_users = set()
user_star_messages = {}


@slack_app.action(re.compile(r"^rating_\d$"))
def handle_rating_button(ack, body, say, client):
    ack()
    user = body["user"]["id"]

    # Prevent double rating
    if user in rated_users:
        return

    rated_users.add(user)

    action = body["actions"][0]
    try:
        rating = int(action["value"])
    except ValueError:
        say("⚠️ Something went wrong reading your rating.")
        return

    # Clean up any pending timeout
    if user in pending_ratings:
        pending_ratings[user].cancel()
        del pending_ratings[user]

    # Log in DB
    profile = get_user_profile(user)
    full_name = profile.get("real_name") or profile.get("display_name") or user
    first_name = full_name.split()[0] if isinstance(full_name, str) else user
    log_message(user, full_name, rating)

    # Update the rating message if we have it
    if user in user_star_messages:
        channel, ts = user_star_messages[user]
        del user_star_messages[user]

        # Build new blocks with feedback
        updated_blocks = body["message"]["blocks"]
        for block in updated_blocks:
            if block["type"] == "actions":
                for element in block["elements"]:
                    if element["type"] == "button":
                        if element["value"] == str(rating):
                            element["text"]["text"] += " ✓"
                            element["style"] = "primary"
                        else:
                            element["style"] = "danger"

        client.chat_update(
            channel=channel,
            ts=ts,
            blocks=updated_blocks,
            text=f"{first_name} rated the reconciliation {rating} ⭐️"
        )


@slack_app.event("message")
def handle_file_dm(event, say):
    if "rules" in event.get("text", "").lower():
        say(rules_message)
        return

    if event.get("channel_type") != "im" or "files" not in event:
        return

    user = event["user"]
    channel = event["channel"]
    profile = get_user_profile(user)
    name = profile.get("real_name") or profile.get("display_name") or user

    # Download and store files
    for file_info in event["files"]:
        download_slack_file(file_info, user, user_file_store)

    if not all(key in user_file_store[user] for key in ("vendor", "soa")):
        say("📄 Waiting for both SOA and Vendor files...")
        return

    vendor_path = user_file_store[user]["vendor"]
    soa_path = user_file_store[user]["soa"]

    # Parse clean/dirty + optional comments
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

    # Cancel previous rating prompt (timeout) and DB log
    if user in pending_ratings:
        pending_ratings[user].cancel()
        del pending_ratings[user]
        log_message(user, name, rating=None)

    # Clear old star UI and rating state
    rated_users.discard(user)
    user_star_messages.pop(user, None)

    # Run reconciliation and prompt for new rating
    if is_clean:
        process_clean_vendor_reconciliation(vendor_path, soa_path, say, channel)
    elif is_dirty:
        process_dirty_vendor_reconciliation(vendor_path, soa_path, say, channel, user_comments)
    else:
        say("❓ Please specify whether the files are `clean` or `dirty` in your message.")
        return

    # Re-prompt for rating after short delay
    Timer(10.0, lambda: prompt_star_rating(
        user=user,
        channel=channel,
        say=say,
        pending_ratings=pending_ratings,
        rated_users=rated_users,
        user_star_messages=user_star_messages
    )).start()



@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    return handler.handle(request)

if __name__ == "__main__":
    # flask_app.run(port=3000)
    init_db()
    periodic_drive_upload(interval_seconds=(60 if ENV=="local" else 7200))
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Flask starting on port {port}")
    flask_app.run(host="0.0.0.0", port=port)

