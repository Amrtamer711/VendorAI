from clients import client
import pandas as pd
from io import StringIO
from prompts import generate_table_prompt


# GPT response generator
def generate_gpt_table(user_text, file_path=None, user_comments=None):
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
                {"role": "system", "content": generate_table_prompt},
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

