import requests
import json
import streamlit as st
from datetime import datetime

class AirtableManager:
    def __init__(self):
        self.api_key = None
        self.base_id = None
        self.table_name = None
        self.users_table_name = "Users" # Default
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
            "Last Contact": "last contact",
            "Next Action": "next action",
            "Contact Name": "contact name",
            "Value": "revenue",
            # "Notes JSON": "notes json"      # Missing in Airtable
        }
        # Reverse map for fetching
        self.REVERSE_MAP = {v: k for k, v in self.FIELD_MAP.items()}



    def setup_from_secrets(self):
        """Attempts to load configuration from st.secrets."""
        if "airtable" in st.secrets:
            self.api_key = st.secrets["airtable"].get("api_key")
            self.base_id = st.secrets["airtable"].get("base_id")
            self.table_name = st.secrets["airtable"].get("table_name", "Leads")
            self.users_table_name = st.secrets["airtable"].get("users_table_name", "Users")
            
            if self.api_key:
                self.headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }

    def is_configured(self):
        return bool(self.api_key and self.base_id and self.table_name)

    def _get_url(self, table_name=None):
        t_name = table_name if table_name else self.table_name
        return f"https://api.airtable.com/v0/{self.base_id}/{t_name}"

    # --- USER PROFILE METHODS ---
    def get_user_by_email(self, email):
        """
        Fetch user profile from 'Users' table.
        """
        if not self.is_configured(): return None
        
        filter_formula = f"{{Email}} = '{email}'"
        params = {"filterByFormula": filter_formula}
        
        try:
            response = requests.get(self._get_url(self.users_table_name), headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            records = data.get("records", [])
            
            if records:
                r = records[0]
                fields = r.get("fields", {})
                p_json = fields.get("Profile JSON", "{}")
                try:
                    profile = json.loads(p_json)
                except:
                    profile = {}
                    
                return {
                    "id": r.get("id"), # Airtable ID
                    "email": fields.get("Email"),
                    "name": fields.get("Name"),
                    "profile": profile
                }
        except Exception as e:
            print(f"Airtable User Fetch Error: {e}")
            
        return None

    def save_user_profile(self, email, name, profile_data):
        """
        Create or Update user in 'Users' table.
        """
        if not self.is_configured(): return False
        
        # Check existence
        existing = self.get_user_by_email(email)
        
        profile_str = json.dumps(profile_data)
        fields = {
            "Email": email,
            "Name": name,
            "Profile JSON": profile_str
        }
        
        try:
            if existing:
                # Update
                payload = {"records": [{"id": existing["id"], "fields": fields}]}
                url = self._get_url(self.users_table_name)
                requests.patch(url, headers=self.headers, json=payload).raise_for_status()
            else:
                # Create
                payload = {"records": [{"fields": fields}]}
                url = self._get_url(self.users_table_name)
                requests.post(url, headers=self.headers, json=payload).raise_for_status()
            return True
        except Exception as e:
            print(f"Airtable User Save Error: {e}")
            return False


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

                # Parse Notes
                notes_raw = get_f("Notes JSON", "{}")
                try:
                    notes = json.loads(notes_raw)
                except:
                    notes = {"raw": notes_raw} # Fallback if not JSON
                if not isinstance(notes, dict): notes = {}

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
                    "Notes": notes,
                    "Value": get_f("Value", 0)
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

        # Validate Last Contact (Airtable DATE field cannot take "Never")
        lc = lead_data.get("Last Contact", "")
        if lc in ["Never", ""]:
            lc = None
            
        # Serialize Notes
        notes_input = lead_data.get("Notes", {})
        if isinstance(notes_input, dict):
            notes_str = json.dumps(notes_input)
        else:
            notes_str = str(notes_input)

        # Prepare payload with MAPPED keys
        # Prepare payload with MAPPED keys
        # Verify field exists in map before adding
        fields = {}
        
        # User Email (Required)
        if "User Email" in self.FIELD_MAP:
             fields[self.FIELD_MAP["User Email"]] = user_email
             
        # Optional fields
        mappings = [
            ("Business Name", lead_data.get("Business Name", "")),
            ("Sector", lead_data.get("Sector", "")),
            ("Address", lead_data.get("Address", "")),
            ("Website", lead_data.get("Website", "")),
            ("Status", lead_data.get("Status", "Pipeline")),
            ("Contact Name", lead_data.get("Contact Name", "")),
            ("Last Contact", lc),
            ("Next Action", lead_data.get("Next Action", datetime.now().strftime("%Y-%m-%d"))),
            ("Notes JSON", notes_str),
            ("Value", lead_data.get("Value", 0))
        ]
        
        for app_key, val in mappings:
            # ONLY add if mapped and the column actually exists in our hardcoded map
            # (We assume the hardcoded map matches Airtable, which we are editing now)
            if app_key in self.FIELD_MAP:
                 fields[self.FIELD_MAP[app_key]] = val

        payload = {
            "records": [
                {"fields": fields}
            ]
        }

        try:
            response = requests.post(self._get_url(), headers=self.headers, json=payload)
            if response.status_code != 200:
                st.error(f"Airtable Add API Error ({response.status_code}): {response.text}")
                response.raise_for_status()
            
            # Return the New Record ID
            data = response.json()
            if "records" in data and len(data["records"]) > 0:
                return data["records"][0]["id"]
            return True # Fallback if ID not found but success
        except Exception as e:
            st.error(f"Airtable Add Error: {e}")
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
        if not self.is_configured(): return False
        
        notes_str = json.dumps(notes_data)
        
        fields = {
            self.FIELD_MAP["Notes JSON"]: notes_str
        }
        
        payload = {"records": [{"id": lead_id, "fields": fields}]}
        
        try:
            response = requests.patch(self._get_url(), headers=self.headers, json=payload)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"Airtable Notes Update Error: {e}")
            return False 

    def update_lead_contact(self, lead_id, contact_name):
        """
        Updates the Contact Name.
        """
        if not self.is_configured(): return False
        
        fields = {
            self.FIELD_MAP["Contact Name"]: contact_name
        }
        
        payload = {"records": [{"id": lead_id, "fields": fields}]}
        
        try:
            response = requests.patch(self._get_url(), headers=self.headers, json=payload)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"Airtable Contact Update Error: {e}")
            return False 

    def update_lead_value(self, lead_id, value):
        """
        Updates the Revenue/Value field.
        """
        if not self.is_configured(): return False
        
        fields = {
            self.FIELD_MAP["Value"]: value
        }
        
        payload = {"records": [{"id": lead_id, "fields": fields}]}
        
        try:
            response = requests.patch(self._get_url(), headers=self.headers, json=payload)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"Airtable Value Update Error: {e}")
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
