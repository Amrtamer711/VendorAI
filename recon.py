from utils import prepare_soa_df, prepare_vendor_df, reconcile_and_report
from file_handler import inject_recon_values_to_excel, send_file_to_user, cleanup_files, convert_excel_to_pdf_mac
from gpt_utils import extract_claimed_total_from_pdf, generate_gpt_table, extract_table_from_gpt_output
from prompts import get_column_mapping
import pandas as pd
from utils import prompt_star_rating

def process_dirty_vendor_reconciliation(vendor_path, soa_path, say, channel, user_comments=None):
    soa_path_pdf = convert_excel_to_pdf_mac(soa_path) if soa_path.endswith(".xlsx") else soa_path
    soa_output = generate_gpt_table("Extract all invoice numbers, dates, amounts...", file_path=soa_path_pdf, user_comments=user_comments)
    try:
        df_soa = extract_table_from_gpt_output(soa_output)
        df_soa = prepare_soa_df(df_soa)
        df_vendor = prepare_vendor_df(pd.read_excel(vendor_path))
    except Exception as e:
        say(f"❌ Failed to prepare data: {e}")
        return

    vendor_claimed_total = extract_claimed_total_from_pdf(soa_path_pdf)
    say(f"*FULL SOA PARSED TABLE:*\n```{df_soa.to_string(index=False)}```")
    say(f"Vendor Remaining Amount: `{df_soa['Remaining Amount'].sum():,.2f}`")
    say(f"Vendor Total Claim: `{vendor_claimed_total:,.2f}`")

    df_fully, df_partial, df_unmatched, unbooked_difference, _ = reconcile_and_report(df_vendor, df_soa, say)
    print(df_unmatched)
    inject_recon_values_to_excel(df_fully, df_partial, df_unmatched, unbooked_difference, vendor_claimed_total)
    send_file_to_user(channel, "filled_recon.xlsx", say)
    cleanup_files(vendor_path, soa_path, soa_path_pdf)

def process_clean_vendor_reconciliation(vendor_path, soa_path, say, channel):
    try:
        df_vendor = pd.read_excel(vendor_path)
        df_soa_raw = pd.read_excel(soa_path)
        column_map = get_column_mapping(df_soa_raw, say)
        df_soa = df_soa_raw.rename(columns=column_map)
        
        # Only keep relevant columns
        required_cols = ["Date", "Invoice Number", "Amount", "Remaining Amount"]
        available_cols = df_soa.columns.tolist()

        # If "Remaining Amount" is not present, duplicate "Amount"
        if "Remaining Amount" not in available_cols and "Amount" in available_cols:
            df_soa["Remaining Amount"] = df_soa["Amount"]
            say("ℹ️ Only one amount column was detected. 'Remaining Amount' has been copied from 'Amount'.")
        elif "Remaining Amount" not in available_cols:
            say("❌ Neither 'Amount' nor 'Remaining Amount' found. Aborting.")
            return

        # Keep only relevant columns (preserve order)
        df_soa = df_soa[[col for col in required_cols if col in df_soa.columns]]
        df_soa = df_soa.reset_index().rename(columns={"index": "Row"})

        vendor_claimed_total = df_soa.iloc[-1]["Remaining Amount"]
        df_soa = df_soa.iloc[:-1]
        df_soa = prepare_soa_df(df_soa)
        df_vendor = prepare_vendor_df(df_vendor)

        say(f"*FULL SOA PARSED TABLE:*\n```{df_soa.to_string(index=False)}```")
        say(f"Vendor Remaining Amount: `{df_soa['Remaining Amount'].sum():,.2f}`")
        say(f"🧾 Vendor claimed total (last row): `{vendor_claimed_total:,.2f}`")
    except Exception as e:
        say(f"❌ Data preparation failed: {e}")
        return

    df_fully, df_partial, df_unmatched, unbooked_difference, vendor_claimed_total = reconcile_and_report(df_vendor, df_soa, say)
    inject_recon_values_to_excel(df_fully, df_partial, df_unmatched, unbooked_difference, vendor_claimed_total)
    send_file_to_user(channel, "filled_recon.xlsx", say)
    cleanup_files(vendor_path, soa_path)
