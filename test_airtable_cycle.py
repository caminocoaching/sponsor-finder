import toml
import requests
import json
import os
from datetime import datetime

SECRETS_PATH = ".streamlit/secrets.toml"

# Mock the AirtableManager logic with the mapping we just deployed
FIELD_MAP = {
    "User Email": "user email",
    "Business Name": "business name",
    "Sector": "sector",
    "Address": "address",
    "Website": "website",
    "Status": "status",
    "Contact Name": "contact name",
    "Last Contact": "last contact",
    "Next Action": "next action",
    # "Notes JSON": "notes json" <-- REMOVED
}

def test_cycle():
    if not os.path.exists(SECRETS_PATH):
        print("❌ Secrets file not found.")
        return

    data = toml.load(SECRETS_PATH)
    conf = data.get("airtable", {})
    api_key = conf.get("api_key")
    base_id = conf.get("base_id")
    table_name = conf.get("table_name")

    print(f"Config: Base={base_id}, Table={table_name}")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    url = f"https://api.airtable.com/v0/{base_id}/{table_name}"

    # 1. ADD SCRIPT
    test_user_email = "test@example.com"
    print(f"\n--- 1. Attempting to ADD record for {test_user_email} ---")
    
    fields = {
        FIELD_MAP["User Email"]: test_user_email,
        FIELD_MAP["Business Name"]: "Test Corp Fixed",
        FIELD_MAP["Sector"]: "Tech",
        FIELD_MAP["Status"]: "Pipeline",
        FIELD_MAP["Contact Name"]: "Tester McTest",
        # FIELD_MAP["Notes JSON"]: ... SKIPPED
    }
    
    payload = {"records": [{"fields": fields}]}
    
    resp_add = requests.post(url, headers=headers, json=payload)
    if resp_add.status_code == 200:
        print("✅ ADD Successful!")
    else:
        print(f"❌ ADD Failed: {resp_add.status_code} - {resp_add.text}")
        return

    # 2. FETCH SCRIPT
    print(f"\n--- 2. Attempting to FETCH records for {test_user_email} ---")
    
    at_col = FIELD_MAP["User Email"]
    filter_formula = f"{{{at_col}}} = '{test_user_email}'"
    
    params = {
        "filterByFormula": filter_formula
    }
    
    resp_get = requests.get(url, headers=headers, params=params)
    if resp_get.status_code == 200:
        records = resp_get.json().get("records", [])
        print(f"✅ FETCH Successful! Found {len(records)} records.")
        for r in records:
            f = r['fields']
            print(f"   - Found: {f.get(FIELD_MAP['Business Name'], 'Unknown')}")
    else:
         print(f"❌ FETCH Failed: {resp_get.status_code} - {resp_get.text}")

if __name__ == "__main__":
    test_cycle()
