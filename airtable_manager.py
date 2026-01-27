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

        # Formula: {User Email} = 'user_email'
        filter_formula = f"{{User Email}} = '{user_email}'"
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
                
                # Parse JSON Notes safely
                notes_str = fields.get("Notes JSON", "{}")
                try:
                    if not notes_str or not notes_str.strip():
                        notes = {}
                    else:
                        notes = json.loads(notes_str)
                except:
                    notes = {}

                leads.append({
                    "id": r.get("id"), # Use Airtable Record ID
                    "Business Name": fields.get("Business Name", ""),
                    "Sector": fields.get("Sector", ""),
                    "Address": fields.get("Address", ""),
                    "Website": fields.get("Website", ""),
                    "Status": fields.get("Status", "Pipeline"),
                    "Contact Name": fields.get("Contact Name", ""),
                    "Last Contact": fields.get("Last Contact", "Never"),
                    "Next Action": fields.get("Next Action", ""),
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

        # Prepare payload
        fields = {
            "User Email": user_email,
            "Business Name": lead_data.get("Business Name", ""),
            "Sector": lead_data.get("Sector", ""),
            "Address": lead_data.get("Address", ""),
            "Website": lead_data.get("Website", ""),
            "Status": lead_data.get("Status", "Pipeline"),
            "Contact Name": lead_data.get("Contact Name", ""),
            "Last Contact": lead_data.get("Last Contact", "Never"),
            "Next Action": lead_data.get("Next Action", datetime.now().strftime("%Y-%m-%d")),
            "Notes JSON": json.dumps(lead_data.get("Notes", {}))
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
            "Status": new_status,
            "Last Contact": datetime.now().strftime("%Y-%m-%d")
        }
        if next_date:
            fields["Next Action"] = next_date

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
        if not self.is_configured():
            return False

        fields = {
            "Notes JSON": json.dumps(notes_data)
        }

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
            print(f"Airtable Notes Error: {e}")
            return False

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
