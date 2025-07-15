import pandas as pd
import re
from clients import web_client
from database import log_message
from slack_sdk.models.blocks import SectionBlock, ActionsBlock, ButtonElement
from slack_sdk.models.blocks.basic_components import MarkdownTextObject
from slack_sdk.models.blocks import Block

def clean_invoice_number(val):
    if isinstance(val, float) and val.is_integer():
        return str(int(val))
    return str(val).strip()

# def prompt_star_rating(user, channel, say, pending_ratings):
    # blocks = [
    #     SectionBlock(text=MarkdownTextObject(text="⭐ *Rate the reconciliation results:*")).to_dict(),
    #     ActionsBlock(
    #         elements=[
    #             ButtonElement(text="⭐", value="1", action_id="rate_1"),
    #             ButtonElement(text="⭐⭐", value="2", action_id="rate_2"),
    #             ButtonElement(text="⭐⭐⭐", value="3", action_id="rate_3"),
    #             ButtonElement(text="⭐⭐⭐⭐", value="4", action_id="rate_4"),
    #             ButtonElement(text="⭐⭐⭐⭐⭐", value="5", action_id="rate_5"),
    #         ]
    #     ).to_dict()
    # ]
    # say(blocks=blocks, channel=channel)
from threading import Timer
from database import log_message  # or wherever this is defined

from threading import Timer
from database import log_message

def prompt_star_rating(user, channel, say, pending_ratings, rated_users, user_star_messages):
    response = say(
        channel=channel,
        text="How would you rate this reconciliation?",
        blocks=[
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "*How would you rate this reconciliation?*"}
            },
            {
                "type": "actions",
                "block_id": "rating_buttons",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": f"{i} ⭐️"},
                        "value": str(i),
                        "action_id": f"rating_{i}"
                    } for i in range(1, 6)
                ]
            }
        ]
    )

    # Save the message ts for future updates
    ts = response["ts"]
    user_star_messages[user] = (channel, ts)

    # Set up a fallback timeout in case they don’t rate
    def fallback():
        if user not in rated_users:
            profile = get_user_profile(user)
            full_name = profile.get("real_name") or profile.get("display_name") or user
            log_message(user, full_name, rating=None)
        pending_ratings.pop(user, None)
        user_star_messages.pop(user, None)

    if user in pending_ratings:
        pending_ratings[user].cancel()

    t = Timer(60.0, fallback)
    t.start()
    pending_ratings[user] = t




def prepare_vendor_df(df):
    required_cols = ["Posting Date", "External Document No.", "Amount (LCY)", "Remaining Amt. (LCY)"]
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in vendor file: {missing}")

    df = df[required_cols].copy()
    df.rename(columns={
        "Posting Date": "Date",
        "External Document No.": "Invoice Number",
        "Amount (LCY)": "Amount",
        "Remaining Amt. (LCY)": "Remaining Amount"
    }, inplace=True)

    df["Date"] = pd.to_datetime(df["Date"], errors='coerce').dt.strftime('%Y-%m-%d')

    def clean_invoice_number(val):
        if pd.isna(val):
            return None
        if isinstance(val, float) and val.is_integer():
            return str(int(val))
        return str(val).strip()

    df["Invoice Number"] = df["Invoice Number"].apply(clean_invoice_number)
    df = df[
        df["Invoice Number"].notna() &
        (df["Invoice Number"].str.lower() != "nan") &
        (df["Invoice Number"] != "")
    ]

    df["Amount"] = pd.to_numeric(df["Amount"], errors='coerce').abs()
    df["Remaining Amount"] = pd.to_numeric(df["Remaining Amount"], errors='coerce').abs()

    return df.reset_index(drop=True)




def prepare_soa_df(df):
    df = df[df["Date"].astype(str).str.upper() != "TOTAL"].copy()
    df["Date"] = pd.to_datetime(df["Date"], format="%d/%b/%Y", errors='coerce').dt.strftime('%Y-%m-%d')
    df["Invoice Number"] = df["Invoice Number"].astype(str).str.strip()
    df["Amount"] = pd.to_numeric(df["Amount"], errors='coerce').abs()
    df["Remaining Amount"] = pd.to_numeric(df["Remaining Amount"], errors='coerce').abs()
    df.rename(columns={"index": "Row"}, inplace=True)
    return df.reset_index(drop=True)

def reconcile_and_report(df_vendor, df_soa, say):
    matched_fully = []
    matched_partial = []
    unmatched_rows = []

    agreed_to_pay = []
    unbooked_difference = []

    for _, soa_row in df_soa.iterrows():
        raw_invoice = str(soa_row["Invoice Number"]).strip()
        candidate = raw_invoice.split()[0]
        match = df_vendor[df_vendor["Invoice Number"] == candidate]

        if not match.empty:
            vendor_row = match.iloc[0]
            soa_remain = soa_row["Remaining Amount"]
            vendor_remain = vendor_row["Remaining Amount"]
            row_data = {
                "Row": soa_row["Row"],
                "Invoice Number": candidate,
                "Date_soa": soa_row["Date"],
                "Date_vendor": vendor_row["Date"],
                "SOA Amount": soa_row["Amount"],
                "Vendor Amount": vendor_row["Amount"],
                "SOA Remaining": soa_remain,
                "Vendor Remaining": vendor_remain
            }

            if abs(soa_remain - vendor_remain) < 1:
                matched_fully.append(row_data)
                agreed_to_pay.append(soa_remain)
            else:
                matched_partial.append(row_data)
                unbooked_difference.append({
                    "Invoice Number": candidate,
                    "Difference": round(max(soa_remain - vendor_remain, 0), 2)
                })
        else:
            unmatched_rows.append({
                "Row": soa_row["Row"],
                "Invoice Number": raw_invoice,
                "Amount": soa_row["Amount"],
                "Remaining Amount": soa_row["Remaining Amount"],
                "Date_soa": soa_row["Date"]
            })

    # Convert all to DataFrames
    df_fully = pd.DataFrame(matched_fully, columns=[
    "Row", "Invoice Number", "Date_soa", "Date_vendor",
    "SOA Amount", "Vendor Amount", "SOA Remaining", "Vendor Remaining"
    ])
    df_partial = pd.DataFrame(matched_partial, columns=df_fully.columns)

    df_unmatched = pd.DataFrame(unmatched_rows, columns=[
        "Row", "Invoice Number", "Amount", "Remaining Amount", "Date_soa"
    ])

    say(f"✅ *PAYMENTS BOOKED (MATCHED):*\n```{df_fully.to_string(index=False)}```")
    say(f"Total agreed to pay: `{sum(agreed_to_pay):,.2f}`")

    if not df_partial.empty:
        say(f"🔍 *PAYMENTS NOT BOOKED (MISMATCHED AMOUNTS):*\n```{df_partial.to_string(index=False)}```")
        say(f"Payment not booked total: `{sum(x['Difference'] for x in unbooked_difference):,.2f}`")

    if not df_unmatched.empty:
        say(f"❌ *INVOICES NOT BOOKED/RECEIVED:*\n```{df_unmatched.to_string(index=False)}```")
        say(f"Unmatched amount total: `{df_unmatched['Amount'].sum():,.2f}`")

    # Optional: Return the 3 tables for downstream use (e.g., Excel injection)
    return df_fully, df_partial, df_unmatched, unbooked_difference

def markdown_to_slack(md: str) -> str:
    # Convert bold (**text** or *text*)
    md = re.sub(r'\*\*(.+?)\*\*', r'*\1*', md)
    md = re.sub(r'\*(.+?)\*', r'*\1*', md)

    # Convert italic (__text__ or _text_)
    md = re.sub(r'__(.+?)__', r'_\1_', md)
    md = re.sub(r'_(.+?)_', r'_\1_', md)

    # Convert strikethrough
    md = re.sub(r'~~(.+?)~~', r'~\1~', md)

    # Convert inline code
    md = re.sub(r'`([^`]+)`', r'`\1`', md)

    # Convert code blocks
    md = re.sub(r'```(?:\w+)?\n(.*?)\n```', r'```\1```', md, flags=re.DOTALL)

    # Convert links [text](url) -> <url|text>
    md = re.sub(r'\[(.*?)\]\((.*?)\)', r'<\2|\1>', md)

    # Convert - or * bullet points to •
    md = re.sub(r'^[\-\*]\s+', r'• ', md, flags=re.MULTILINE)

    # Convert numbered lists to dot bullets
    md = re.sub(r'^\d+\.\s+', r'• ', md, flags=re.MULTILINE)

    # Remove headings (#, ##, ###) – Slack doesn't support them
    md = re.sub(r'^#{1,6}\s+', '', md, flags=re.MULTILINE)

    # Remove extra trailing spaces
    md = re.sub(r'[ \t]+$', '', md, flags=re.MULTILINE)

    return md.strip()

def get_user_profile(user_id):
    try:
        response = web_client.users_info(user=user_id)
        profile = response["user"]["profile"]
        return {
            "display_name": profile.get("display_name"),
            "real_name": profile.get("real_name"),
            "email": profile.get("email"),
            "title": profile.get("title"),
            "image": profile.get("image_512")
        }
    except Exception as e:
        print(f"❌ Failed to get user info: {e}")
        return {"display_name": "there"}