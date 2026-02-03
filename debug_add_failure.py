import toml
import requests
import json
import os
from datetime import datetime

SECRETS_PATH = ".streamlit/secrets.toml"

# Mock the logic currently deployed in airtable_manager.py
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
    # "Notes JSON": "notes json"
}

def debug_add():
    if not os.path.exists(SECRETS_PATH):
        print("❌ Secrets file not found.")
        return

    data = toml.load(SECRETS_PATH)
    conf = data.get("airtable", {})
    api_key = conf.get("api_key")
    base_id = conf.get("base_id")
    table_name = conf.get("table_name")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    url = f"https://api.airtable.com/v0/{base_id}/{table_name}"

    # SIMULATE THE EXACT DATA FROM THE APP
    user_email = "csm66@me.com" # From user screenshot
    lead_data = {
        "Business Name": "ITS Logistics Hungary Kft.",
        "Sector": "Transport & haulage",
        "Address": "Vecsés, Almáskert út 4, 2220 Hungary",
        "Website": "http://www.itslogistics.hu/",
        "Status": "Pipeline",
        "Contact Name": "",
        "Last Contact": "Never",
        "Next Action": datetime.now().strftime("%Y-%m-%d"),
        "Notes": {}
    }

    # Prepare payload with MAPPED keys (as per current airtable_manager.py)
    fields = {
        FIELD_MAP["User Email"]: user_email,
        FIELD_MAP["Business Name"]: lead_data.get("Business Name", ""),
        FIELD_MAP["Sector"]: lead_data.get("Sector", ""),
        FIELD_MAP["Address"]: lead_data.get("Address", ""),
        FIELD_MAP["Website"]: lead_data.get("Website", ""),
        FIELD_MAP["Status"]: lead_data.get("Status", "Pipeline"),
        FIELD_MAP["Contact Name"]: lead_data.get("Contact Name", ""),
        FIELD_MAP["Last Contact"]: lead_data.get("Last Contact", "Never"),
        FIELD_MAP["Next Action"]: lead_data.get("Next Action")
    }

    print(f"Attempting to add to URL: {url}")
    print("Payload Fields:", json.dumps(fields, indent=2))

    payload = {"records": [{"fields": fields}]}
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            print("✅ SUCCESS! Record added.")
            print(response.json())
        else:
            print(f"❌ FAILED: {response.status_code}")
            print(f"Error Message: {response.text}")
            
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")

if __name__ == "__main__":
    debug_add()
