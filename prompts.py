import pandas as pd
from clients import client

extract_total_from_table_prompt = """You are a financial assistant at MMG. Your job is to extract the total claimed by the vendor from a Statement of Account (SOA) PDF.
The total is usually labeled something like "Total", "Outstanding", "Balance Due", or similar, and appears at the bottom of the document.
Follow these rules:
1. Respond with only the number — no explanation, no labels, no formatting.
2. Use dot as the decimal separator.
3. Strip any currency symbols, commas, or spaces.
4. If there are multiple totals, select the one that reflects the final amount due from MMG to the vendor."""

def get_column_mapping_prompt(df_soa_raw: pd.DataFrame) -> str:
    return f"""
You are a data assistant. Your task is to rename columns in a vendor Statement of Account (SOA) Excel file.

Your goal is to map each original column to one of the following **target names** (use these names exactly):
• Date  
• Invoice Number  
• Amount  
• Remaining Amount

Here is the list of original columns:
{list(df_soa_raw.columns)}

Follow these strict rules:
1. Only return a valid Python dictionary of column mappings. No explanation or text outside the dictionary.
2. Only include "Remaining Amount" in your mapping **if the original columns clearly contain a second distinct amount-related column**.
3. If there's only one amount column, map it to "Amount" only — do **not** include "Remaining Amount". We will handle duplication in the backend.
4. Do not guess or make assumptions about missing fields. Only map what is clearly present.
5. Use each mapped column name only once.

✅ Example (if two amount columns):
{{"Posting Date": "Date", "Ext Doc No": "Invoice Number", "Amount (LCY)": "Amount", "Remaining (LCY)": "Remaining Amount"}}

✅ Example (if only one amount column):
{{"Posting Date": "Date", "Ext Doc No": "Invoice Number", "Amount (LCY)": "Amount"}}
"""

generate_table_prompt = """You are a financial assistant at MMG (Multi Media Group). Your task is to extract invoice data
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

rules_message = """
📘 *Vendor Reconciliation Rules*

To use the vendor reconciliation bot, follow these steps:

1. 🧾 *Upload two files in a direct message*:
   • One *vendor* file (include "vendor" in the file name)
   • One *SOA* file (include "soa" in the file name)

2. ✍️ *Add a keyword in the message* to indicate parsing mode:
   • `clean` – for structured SOA Excel files  
   • `dirty` – for unstructured SOA Excel/PDF files (uses GPT)

3. ✅ The bot will:
   • Extract, compare, and reconcile invoices
   • Print matched, partially matched, and unmatched rows
   • Generate and save a filled Excel reconciliation sheet

💡 *Advanced - Only for `dirty` mode*:
   • If you add a message *on the next line* after `dirty`, it will be passed as *contextual comments to GPT*.
   • Example:
     ```
     dirty
     This SOA includes finance charges at the bottom and missing invoice dates.```

   This helps GPT extract better tables when the SOA format is messy.

—
If you're unsure, start with `dirty` mode — it's safer for unstructured files.
"""

def get_column_mapping(df_soa_raw: pd.DataFrame, say) -> dict:
    column_map_prompt = get_column_mapping_prompt(df_soa_raw)
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful Python assistant."},
                {"role": "user", "content": column_map_prompt}
            ]
        )
        column_map = eval(response.choices[0].message.content.strip())
        return column_map
    except Exception as e:
        say(f"❌ GPT column mapping failed: {e}")
        return