import requests
import json
import streamlit as st
from datetime import datetime

class AirtableManager:
    def __init__(self):
        self.api_key = None
        self.base_id = None
        self.table_name = None
        self.headers = None
        self.setup_from_secrets()

        # INTERNAL (App) -> EXTERNAL (Airtable)
        self.FIELD_MAP = {
            "User Email": "user email",
            "Business Name": "business name",
            "Sector": "sector",
            "Address": "address",
            "Website": "website",
            "Status": "status",
            "Contact Name": "contact name",
            "Last Contact": "last contact",
            "Next Action": "next action"
            # "Notes JSON": "notes json"  <-- Disabled: Column missing in User Base
        }
        # Reverse map for fetching
        self.REVERSE_MAP = {v: k for k, v in self.FIELD_MAP.items()}

    def setup_from_secrets(self):
        """Attempts to load configuration from st.secrets."""
        if "airtable" in st.secrets:
            self.api_key = st.secrets["airtable"].get("api_key")
            self.base_id = st.secrets["airtable"].get("base_id")
            self.table_name = st.secrets["airtable"].get("table_name", "Leads")
            
            if self.api_key:
                self.headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }

    def is_configured(self):
        return bool(self.api_key and self.base_id and self.table_name)

    def _get_url(self):
        return f"https://api.airtable.com/v0/{self.base_id}/{self.table_name}"

    def get_leads(self, user_email):
        """
        Fetch all leads for a specific user email.
        Uses filterByFormula to isolate user data.
        """
        if not self.is_configured():
            return []

        # Formula: {user email} = 'user_email'
        # Note: We must use the mapped AIRTABLE column name here
        at_col = self.FIELD_MAP["User Email"]
        filter_formula = f"{{{at_col}}} = '{user_email}'"
        params = {
            "filterByFormula": filter_formula
        }

        all_records = []
        offset = None

        try:
            while True:
                if offset:
                    params["offset"] = offset
                
                response = requests.get(self._get_url(), headers=self.headers, params=params)
                response.raise_for_status()
                data = response.json()
                
                all_records.extend(data.get("records", []))
                
                offset = data.get("offset")
                if not offset:
                    break
            
            # Convert Airtable records to App format
            leads = []
            for r in all_records:
                fields = r.get("fields", {})
                
                # Helper to get field via Lowercase key
                def get_f(internal_key, default=""):
                    external_key = self.FIELD_MAP.get(internal_key, internal_key)
                    return fields.get(external_key, default)

                # Notes disabled for now
                notes = {}

                leads.append({
                    "id": r.get("id"), # Use Airtable Record ID
                    "Business Name": get_f("Business Name"),
                    "Sector": get_f("Sector"),
                    "Address": get_f("Address"),
                    "Website": get_f("Website"),
                    "Status": get_f("Status", "Pipeline"),
                    "Contact Name": get_f("Contact Name"),
                    "Last Contact": get_f("Last Contact", "Never"),
                    "Next Action": get_f("Next Action"),
                    "Notes": notes
                })
            return leads

        except Exception as e:
            # st.error(f"Airtable Fetch Error: {e}")
            print(f"Airtable Error: {e}")
            return []

    def add_lead(self, user_email, lead_data):
        """
        Adds a new lead for the user.
        """
        if not self.is_configured():
            return False

        # Prepare payload with MAPPED keys
        fields = {
            self.FIELD_MAP["User Email"]: user_email,
            self.FIELD_MAP["Business Name"]: lead_data.get("Business Name", ""),
            self.FIELD_MAP["Sector"]: lead_data.get("Sector", ""),
            self.FIELD_MAP["Address"]: lead_data.get("Address", ""),
            self.FIELD_MAP["Website"]: lead_data.get("Website", ""),
            self.FIELD_MAP["Status"]: lead_data.get("Status", "Pipeline"),
            self.FIELD_MAP["Contact Name"]: lead_data.get("Contact Name", ""),
            self.FIELD_MAP["Last Contact"]: lead_data.get("Last Contact", "Never"),
            self.FIELD_MAP["Next Action"]: lead_data.get("Next Action", datetime.now().strftime("%Y-%m-%d"))
            # "Notes JSON": ... SKIPPED
        }

        payload = {
            "records": [
                {"fields": fields}
            ]
        }

        try:
            response = requests.post(self._get_url(), headers=self.headers, json=payload)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"Airtable Add Error: {e}")
            return False

    def update_lead_status(self, lead_id, new_status, next_date=None):
        """
        Updates the status and optionally next action date.
        lead_id must be the Airtable Record ID.
        """
        if not self.is_configured():
            return False

        fields = {
            self.FIELD_MAP["Status"]: new_status,
            self.FIELD_MAP["Last Contact"]: datetime.now().strftime("%Y-%m-%d")
        }
        if next_date:
            fields[self.FIELD_MAP["Next Action"]] = next_date

        payload = {
            "records": [
                {
                    "id": lead_id,
                    "fields": fields
                }
            ]
        }

        try:
            response = requests.patch(self._get_url(), headers=self.headers, json=payload)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"Airtable Update Error: {e}")
            return False

    def update_lead_notes(self, lead_id, notes_data):
        """
        Updates the notes JSON.
        """
        # Feature disabled because writing to 'Notes JSON' fails if column missing
        print("Warning: Notes update skipped because 'Notes JSON' column is missing in Airtable.")
        return True

    def delete_lead(self, lead_id):
        """
        Deletes a record.
        """
        if not self.is_configured():
            return False

        params = {
            "records": [lead_id]
        }

        try:
            # DELETE method in Airtable API takes query params for records
            delete_url = f"{self._get_url()}?records[]={lead_id}"
            response = requests.delete(delete_url, headers=self.headers)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"Airtable Delete Error: {e}")
            return False

# Singleton
airtable_manager = AirtableManager()
