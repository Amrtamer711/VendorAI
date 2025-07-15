from clients import client
import pandas as pd
from io import StringIO


# GPT response generator
def generate_gpt_table(user_text, file_path=None, user_comments=None):
    system_prompt = """You are a financial assistant at MMG (Multi Media Group). Your task is to extract invoice data
from vendor Statements of Account (SOAs) uploaded as PDF documents. Your output must follow these strict rules:

1. Output only a markdown table and nothing else — no explanations, summaries, or introductions.
2. The table must contain exactly four columns with these headers (case-sensitive):
   | Date | Invoice Number | Amount | Remaining Amount |
3. Each row must represent one invoice, with its date, invoice number, amount, and remaining amount.
4. Dates must be formatted as DD/Mon/YYYY (e.g., 28/Dec/2024).
5. Amounts must be raw numbers only — no commas, no currency symbols.
6. For extracting the correct Invoice Number column, apply the following logic:
   - Prioritize columns named (in order): "Invoice Number" → "Document No" → "External Document No"
   - Within those columns, extract values that follow this pattern: an uppercase letter prefix followed by digits or special characters, e.g.:
     • INVMMT-24-279
     • S-INV+-04868
     • PINV-004934
   - Ignore suffixes or extra labels like "May 2022" that come **after** the actual invoice number.
7. At the end of the SOA, there may be additional charges such as interest or finance fees that do not have a `Date` or `Invoice Number`. Only include such a row **if the row is clearly labeled with the word "interest" (case-insensitive)** in the original document. If detected, include a single additional row at the bottom of the table like this:
   | - | INTEREST | <amount> | <remaining amount> |
   Be VERY alert of this situation, as it can happen in any SOA. But do not confuse it for an actual invoice row or the total row at the bottom.
8. The markdown table must begin and end with pipe (`|`) characters for every row, including the header.
9. Do not include any TOTAL row. Exclude any totals or summaries at the bottom of the table.
10. If any row has missing or unclear data (and is not an interest charge), skip it — do not guess or add placeholders.
11. If there is no separate "Remaining Amount" column, assume the "Amount" is also the "Remaining Amount" and duplicate that value in both columns.
"""

    try:
        # Upload file to OpenAI
        if file_path:
            file_upload = client.files.create(
                file=open(file_path, 'rb'),
                purpose="user_data"
            )
            file_id = file_upload.id

            print(f"📤 Uploaded file to OpenAI: {file_id}")

            response = client.responses.create(
            model="gpt-4.1",
            input=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "input_file", "file_id": file_id},
                        {"type": "input_text", "text": user_text}
                    ] + (
                        [{"type": "input_text", "text": f"Additional context: {user_comments}"}]
                        if user_comments else []
                    )
                }
            ],
            store=False  # Do not store the file permanently
        )
            client.files.delete(file_id)

            return response.output_text
        else:
            return "No file provided."

    except Exception as e:
        print("❌ OpenAI file+response call failed:", e)
        return "Sorry, I couldn't process the document."

def extract_claimed_total_from_pdf(file_path: str) -> float:
    system_prompt = """You are a financial assistant at MMG. Your job is to extract the total claimed by the vendor from a Statement of Account (SOA) PDF.
The total is usually labeled something like "Total", "Outstanding", "Balance Due", or similar, and appears at the bottom of the document.
Follow these rules:
1. Respond with only the number — no explanation, no labels, no formatting.
2. Use dot as the decimal separator.
3. Strip any currency symbols, commas, or spaces.
4. If there are multiple totals, select the one that reflects the final amount due from MMG to the vendor."""

    try:
        file_upload = client.files.create(
            file=open(file_path, 'rb'),
            purpose="user_data"
        )
        file_id = file_upload.id

        print(f"📤 Uploaded for claimed total extraction: {file_id}")

        response = client.responses.create(
            model="gpt-4.1",
            input=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "input_file", "file_id": file_id},
                        {"type": "input_text", "text": "Extract only the claimed total amount."}
                    ]
                }
            ],
            store=False  # Do not store the file permanently
        )
        client.files.delete(file_id)

        output = response.output_text.strip()
        return float(output)

    except Exception as e:
        print(f"❌ Claimed total extraction failed: {e}")
        return 0.0  # fallback or raise if preferred


def extract_table_from_gpt_output(output_text):
    lines = output_text.strip().splitlines()
    table_lines = [line for line in lines if line.strip().startswith("|") and line.strip().endswith("|")]
    cleaned = "\n".join(["|".join([col.strip() for col in row.strip().strip("|").split("|")]) for row in table_lines if "---" not in row])
    df = pd.read_csv(StringIO(cleaned), sep="|")
    df.columns = [col.strip() for col in df.columns]
    df.reset_index(inplace=True)
    return df

