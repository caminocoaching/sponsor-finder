import toml
import requests
import json
import os

SECRETS_PATH = ".streamlit/secrets.toml"

def check():
    if not os.path.exists(SECRETS_PATH):
        print("❌ Secrets file not found.")
        return

    data = toml.load(SECRETS_PATH)
    conf = data.get("airtable", {})
    api_key = conf.get("api_key")
    base_id = conf.get("base_id")
    table_name = "leads" # Hardcoded based on previous success

    if not api_key or not base_id:
        print("❌ Missing config.")
        return

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    url = f"https://api.airtable.com/v0/{base_id}/{table_name}"
    print(f"Inspecting Table: '{table_name}' ...")
    
    resp = requests.get(url, headers=headers, params={"maxRecords": 1})
    
    if resp.status_code == 200:
        records = resp.json().get("records", [])
        if records:
            fields = records[0].get("fields", {})
            print(f"✅ Connection Successful! Found {len(records)} record(s).")
            print("\n--- ACTUAL COLUMNS IN AIRTABLE ---")
            for k in fields.keys():
                print(f"[ ] {k}")
            print("----------------------------------")
            
            # Check for critical missing ones
            expected = ["User Email", "Business Name", "Status", "Website"]
            missing = [e for e in expected if e not in fields]
            if missing:
                print(f"⚠️ WARNING: specific columns might be missing (or empty in the first record): {missing}")
            else:
                print("✅ Key columns usually present.")
                
        else:
            print("✅ Table 'leads' exists but is EMPTY. Add 1 dummy row in Airtable to verify columns.")
    else:
        print(f"❌ Error {resp.status_code}: {resp.text}")

if __name__ == "__main__":
    check()
