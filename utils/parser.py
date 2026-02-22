import pandas as pd
import re
import os
import json
from pathlib import Path

_COUNTRY_MAPPING_PATH = Path(__file__).parent.parent / "config" / "country_mapping.json"

def _load_country_mapping():
    try:
        with open(_COUNTRY_MAPPING_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

_COUNTRY_MAPPING = _load_country_mapping()

class KiteParser:
    @staticmethod
    def clean_excel_value(val):
        if isinstance(val, str):
            # Matches ="value" or similar Excel-style quoting
            match = re.match(r'^="?([^"]*)"?$', val)
            if match:
                return match.group(1)
        return val

    @classmethod
    def parse(cls, file_path):
        # We know it uses semicolons based on research
        df = pd.read_csv(file_path, sep=';', encoding='utf-8-sig')
        
        # Clean all columns from the ="value" format
        for col in df.columns:
            df[col] = df[col].apply(cls.clean_excel_value)
            
        # Rename header to clean identifiers if needed
        df.columns = [cls.clean_excel_value(col) for col in df.columns]
        
        # Detect currency from headers
        currency = "Unknown"
        for col in df.columns:
            if "QUANTITY (" in col:
                cur_match = re.search(r'\((.*?)\)', col)
                if cur_match:
                    currency = cur_match.group(1)
                break
        
        # Detect Country/Company
        # Handle both string paths and Streamlit UploadedFile objects
        if hasattr(file_path, 'name'):
            filename = file_path.name.lower()
        else:
            filename = os.path.basename(str(file_path)).lower()
        
        company = "Unknown"
        kite = "Unknown"

        for entry in _COUNTRY_MAPPING:
            if entry["pattern"].lower() in filename:
                kite = entry["country"]
                company = entry["company"]
                break

        df['company'] = company
        df['kite'] = kite
        df['currency'] = currency
        
        # Normalize numeric columns
        # Some columns use comma as decimal separator in Spanish reports
        def clean_number(x):
            if isinstance(x, str):
                x = x.replace(',', '.')
                try:
                    return float(x)
                except ValueError:
                    return x
            return x

        if 'AMOUNT (bytes/SMS/seconds)' in df.columns:
            df['amount_value'] = df['AMOUNT (bytes/SMS/seconds)'].apply(clean_number)
            
        quantity_col = [col for col in df.columns if 'QUANTITY' in col][0]
        df['total_cost'] = df[quantity_col].apply(clean_number)

        # Quota extraction from TARIFF (e.g., "0,55EUR/5242880bytes")
        def extract_quota(tariff_str):
            if isinstance(tariff_str, str):
                match = re.search(r'/(\d+)bytes', tariff_str)
                if match:
                    return int(match.group(1))
            return 0

        df['quota_bytes'] = df['TARIFF'].apply(extract_quota)

        # Classify record type based on DESCRIPTION
        def classify_record(desc):
            if not isinstance(desc, str):
                return 'other'
            desc_lower = desc.lower()
            if 'monthly fee' in desc_lower:
                return 'fee'
            if 'usage included' in desc_lower:
                return 'usage'
            if 'overage' in desc_lower:
                return 'overage'
            if 'non-billable' in desc_lower or 'status' in desc_lower:
                return 'status_change'
            return 'other'

        df['record_type'] = df['DESCRIPTION'].apply(classify_record)

        # Normalize PERIOD_START and PERIOD_END to full timestamps
        for col in ['PERIOD_START', 'PERIOD_END']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')

        return df

if __name__ == "__main__":
    # Test with Spain file
    spain_file = "/Users/alzuno/Desktop/Personales/KiteAnalyzer/Files/MonthlySubscriptionDetail_EU_Location_World1771f0368d6VtF9_0_20260131.0.csv"
    if os.path.exists(spain_file):
        print("Parsing Spain file...")
        df_sp = KiteParser.parse(spain_file)
        print(df_sp[['ICC', 'COMMERCIAL_PLAN', 'amount_value', 'total_cost', 'currency', 'country']].head())
        
    # Test with Ecuador file
    ecuador_file = "/Users/alzuno/Desktop/Personales/KiteAnalyzer/Files/MonthlySubscriptionDetail_LOCATION_WORLD_DEMO169c4ebdc971N_0_20260201.0.csv"
    if os.path.exists(ecuador_file):
        print("\nParsing Ecuador file...")
        df_ec = KiteParser.parse(ecuador_file)
        print(df_ec[['ICC', 'COMMERCIAL_PLAN', 'amount_value', 'total_cost', 'currency', 'country']].head())
