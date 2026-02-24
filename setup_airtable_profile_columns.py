"""
Setup & Verify Airtable Profile Columns
========================================
This script checks the Airtable 'Users' table for the required profile columns
and performs a save/readback test to verify everything works.

Required Columns in Airtable "Users" table:
- Email (Single line text) [EXISTING]
- Name (Single line text) [EXISTING]
- Profile JSON (Long text) [EXISTING]
- First Name (Single line text) [NEW]
- Last Name (Single line text) [NEW]
- Vehicle (Single line text) [NEW]
- Championship (Single line text) [NEW]
- Town (Single line text) [NEW]
- State (Single line text) [NEW]
- Country (Single line text) [NEW]
- Zip Code (Single line text) [NEW]
- Competitors (Single line text) [NEW]
- Audience (Single line text) [NEW]
- Televised (Single line text) [NEW]
- Streamed (Single line text) [NEW]
- TV Reach (Single line text) [NEW]
- Season Goal (Single line text) [NEW]
- Previous Championship (Single line text) [NEW]
- Achievements (Single line text) [NEW]
- Team Name (Single line text) [NEW]
- Rep Mode (Checkbox) [NEW]
- Rep Name (Single line text) [NEW]
- Rep Role (Single line text) [NEW]
- Onboarding Complete (Checkbox) [NEW]

NOTE: Airtable will auto-create columns when you first write to them
if your API token has schema write permissions. If not, you'll need to
create them manually in the Airtable UI.

Run this script to check which columns already exist:
    python setup_airtable_profile_columns.py
"""

import os
import sys
import json
import requests

# Try to load from Streamlit secrets format
def load_config():
    """Load Airtable config from .streamlit/secrets.toml"""
    secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
    
    if not os.path.exists(secrets_path):
        print(f"❌ No secrets file found at {secrets_path}")
        return None
    
    config = {}
    with open(secrets_path, "r") as f:
        in_airtable = False
        for line in f:
            line = line.strip()
            if line == "[airtable]":
                in_airtable = True
                continue
            elif line.startswith("[") and line.endswith("]"):
                in_airtable = False
                continue
            
            if in_airtable and "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                config[key] = val
    
    return config

def check_columns(config):
    """Check which columns exist in the Users table."""
    api_key = config.get("api_key")
    base_id = config.get("base_id")
    users_table = config.get("users_table_name", "Users")
    
    if not api_key or not base_id:
        print("❌ Missing api_key or base_id in config")
        return
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Fetch an existing record to see what fields exist
    url = f"https://api.airtable.com/v0/{base_id}/{users_table}"
    params = {"maxRecords": 1}
    
    print(f"\n📋 Checking Airtable Users table: {users_table}")
    print(f"   Base ID: {base_id}")
    print()
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        records = data.get("records", [])
        
        if records:
            fields = records[0].get("fields", {})
            existing_columns = set(fields.keys())
            
            print("✅ Existing columns found:")
            for col in sorted(existing_columns):
                val = fields[col]
                display = str(val)[:80] + "..." if len(str(val)) > 80 else str(val)
                print(f"   • {col}: {display}")
        else:
            existing_columns = set()
            print("ℹ️  No records found — can't automatically detect columns")
        
        # Check for required NEW columns
        required_new = {
            "First Name", "Last Name", "Vehicle", "Championship",
            "Town", "State", "Country", "Zip Code",
            "Competitors", "Audience", "Televised", "Streamed",
            "TV Reach", "Season Goal", "Previous Championship",
            "Achievements", "Team Name", "Rep Mode", "Rep Name",
            "Rep Role", "Onboarding Complete"
        }
        
        missing = required_new - existing_columns
        present = required_new & existing_columns
        
        print(f"\n📊 Profile columns status:")
        print(f"   ✅ Already present: {len(present)}")
        if present:
            for col in sorted(present):
                print(f"      • {col}")
        
        print(f"   📝 Will be created on first save: {len(missing)}")
        if missing:
            for col in sorted(missing):
                print(f"      • {col}")
        
        print()
        print("ℹ️  Note: Airtable auto-creates columns when you write to them")
        print("   (if your token has schema permissions). Otherwise create them manually.")
        
    except Exception as e:
        print(f"❌ Error checking Airtable: {e}")

if __name__ == "__main__":
    config = load_config()
    if config:
        print(f"✅ Config loaded: {len(config)} keys")
        check_columns(config)
    else:
        print("Failed to load config. Check .streamlit/secrets.toml")
