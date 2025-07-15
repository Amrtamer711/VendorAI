import pandas as pd
import re
from clients import web_client

def prepare_vendor_df(df):
    df = df[["Posting Date", "External Document No.", "Amount (LCY)", "Remaining Amt. (LCY)"]].copy()
    df.rename(columns={
        "Posting Date": "Date",
        "External Document No.": "Invoice Number",
        "Amount (LCY)": "Amount",
        "Remaining Amt. (LCY)": "Remaining Amount"
    }, inplace=True)

    df["Date"] = pd.to_datetime(df["Date"], errors='coerce').dt.strftime('%Y-%m-%d')
    df["Invoice Number"] = df["Invoice Number"].astype(str).str.strip()
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
    df_fully = pd.DataFrame(matched_fully)
    df_partial = pd.DataFrame(matched_partial)
    df_unmatched = pd.DataFrame(unmatched_rows)

    say(f"✅ *PAYMENTS BOOKED (MATCHED):*\n```{df_fully.to_string(index=False)}```")
    say(f"Total agreed to pay: `{sum(agreed_to_pay):,.2f}`")

    if not df_partial.empty:
        say(f"🔍 *PAYMENTS NOT BOOKED (MISMATCHED AMOUNTS):*\n```{df_partial.to_string(index=False)}```")
        say(f"Payment not booked total: `{sum(x['Difference'] for x in unbooked_difference):,.2f}`")

    if not df_unmatched.empty:
        say(f"❌ *INVOICES NOT BOOKED/RECEIVED:*\n```{df_unmatched.to_string(index=False)}```")
        say(f"Unmatched amount total: `{df_unmatched['Amount'].sum():,.2f}`")

    # Optional: Return the 3 tables for downstream use (e.g., Excel injection)
    return df_fully, df_partial, df_unmatched, unbooked_difference, 1000000

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