from collections import defaultdict
from flask import request, jsonify
from database import init_db
from recon import process_clean_vendor_reconciliation, process_dirty_vendor_reconciliation
from file_handler import download_slack_file
from prompts import rules_message
from clients import slack_app, flask_app, handler

user_file_store = defaultdict(dict)

@slack_app.event("message")
def handle_file_dm(event, say):
    if "rules" in event.get("text", "").lower():
        say(rules_message)
        return

    if event.get("channel_type") == "im" and "files" in event:
        user = event["user"]
        channel = event["channel"]
        for file_info in event["files"]:
            download_slack_file(file_info, user, user_file_store)

        if not all(key in user_file_store[user] for key in ("vendor", "soa")):
            say("📄 Waiting for both SOA and Vendor files...")
            return

        vendor_path = user_file_store[user]["vendor"]
        soa_path = user_file_store[user]["soa"]

        message_lines = event.get("text", "").splitlines()
        message_flags = [line.lower().strip() for line in message_lines if line.strip()]
        is_clean = any("clean" in line for line in message_flags)
        is_dirty = any("dirty" in line for line in message_flags)

        user_comments = None
        if is_dirty and len(message_flags) > 1:
            dirty_index = next(i for i, line in enumerate(message_flags) if "dirty" in line)
            user_comments = "\n".join(message_flags[dirty_index + 1:])

        if is_clean:
            process_clean_vendor_reconciliation(vendor_path, soa_path, say, channel)
        elif is_dirty:
            process_dirty_vendor_reconciliation(vendor_path, soa_path, say, channel, user_comments)
        else:
            say("❓ Please specify whether the files are `clean` or `dirty` in your message.")

@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    if request.json and "challenge" in request.json:
        return jsonify({"challenge": request.json["challenge"]})
    return handler.handle(request)

if __name__ == "__main__":
    # init_db()
    # flask_app.run(port=3000)
    flask_app.run(host="0.0.0.0", port=10000)

