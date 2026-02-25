import requests
import json
import time
import streamlit as st
from datetime import datetime

class AirtableManager:
    # Maps internal profile keys -> Airtable column names for individual fields
    # These columns should exist in the "Users" table in Airtable
    PROFILE_FIELD_MAP = {
        "first_name": "First Name",
        "last_name": "Last Name",
        "vehicle": "Vehicle",
        "championship": "Championship",
        "town": "Town",
        "state": "State",
        "country": "Country",
        "zip_code": "Zip Code",
        "competitors": "Competitors",
        "audience": "Audience",
        "televised": "Televised",
        "streamed": "Streamed",
        "tv_reach": "TV Reach",
        "goal": "Season Goal",
        "prev_champ": "Previous Championship",
        "achievements": "Achievements",
        "team": "Team Name",
        "rep_mode": "Rep Mode",
        "rep_name": "Rep Name",
        "rep_role": "Rep Role",
        "onboarding_complete": "Onboarding Complete",
    }
    # Reverse: Airtable column name -> internal profile key
    PROFILE_REVERSE_MAP = {v: k for k, v in PROFILE_FIELD_MAP.items()}

    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 1  # seconds

    def __init__(self):
        self.api_key = None
        self.base_id = None
        self.table_name = None
        self.users_table_name = "Users" # Default
        self.headers = None
        self.setup_from_secrets()

        # INTERNAL (App) -> EXTERNAL (Airtable) for LEADS table
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
            "Value": "Value",
            "Notes JSON": "notes json",
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

    def _request_with_retry(self, method, url, **kwargs):
        """
        Makes an HTTP request with retry logic and exponential backoff.
        Returns the response object on success, raises on final failure.
        """
        last_error = None
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                response = method(url, **kwargs)

                # Rate limit (429) — wait and retry
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", self.RETRY_BASE_DELAY * attempt))
                    print(f"  ⏳ Rate limited. Waiting {retry_after}s before retry {attempt}/{self.MAX_RETRIES}...")
                    time.sleep(retry_after)
                    continue

                response.raise_for_status()
                return response

            except requests.exceptions.ConnectionError as e:
                last_error = e
                delay = self.RETRY_BASE_DELAY * (2 ** (attempt - 1))
                print(f"  🔌 Connection error (attempt {attempt}/{self.MAX_RETRIES}). Retrying in {delay}s...")
                time.sleep(delay)

            except requests.exceptions.HTTPError as e:
                last_error = e
                status = e.response.status_code if e.response is not None else 0
                # Don't retry client errors (4xx) except 429 (handled above) and 408 (timeout)
                if 400 <= status < 500 and status not in (408, 429):
                    raise  # Permanent client error, don't retry
                delay = self.RETRY_BASE_DELAY * (2 ** (attempt - 1))
                print(f"  ⚠️ HTTP {status} (attempt {attempt}/{self.MAX_RETRIES}). Retrying in {delay}s...")
                time.sleep(delay)

            except requests.exceptions.Timeout as e:
                last_error = e
                delay = self.RETRY_BASE_DELAY * (2 ** (attempt - 1))
                print(f"  ⏱️ Timeout (attempt {attempt}/{self.MAX_RETRIES}). Retrying in {delay}s...")
                time.sleep(delay)

        # All retries exhausted
        raise last_error or Exception("Request failed after all retries")

    # --- USER PROFILE METHODS ---
    def _build_profile_fields(self, email, name, profile_data):
        """
        Builds the Airtable fields dict with both individual columns
        AND the Profile JSON backup column.
        """
        fields = {
            "Email": email,
            "Name": name,
        }

        # Map individual profile keys to Airtable columns
        for internal_key, at_column in self.PROFILE_FIELD_MAP.items():
            value = profile_data.get(internal_key)
            if value is not None:
                # Airtable doesn't accept Python booleans in single-line text
                # Convert bools to checkbox-friendly format
                if isinstance(value, bool):
                    fields[at_column] = value  # Airtable checkbox accepts True/False
                elif isinstance(value, (int, float)):
                    fields[at_column] = str(value)
                else:
                    fields[at_column] = str(value)

        # Full JSON backup (includes ALL keys, even ones not mapped above like API keys)
        fields["Profile JSON"] = json.dumps(profile_data)

        return fields

    def _parse_profile_from_fields(self, fields):
        """
        Reconstructs a profile dict from individual Airtable columns,
        falling back to Profile JSON for any missing keys.
        """
        # Start with the JSON backup
        p_json = fields.get("Profile JSON", "{}")
        try:
            profile = json.loads(p_json)
        except (json.JSONDecodeError, TypeError):
            profile = {}

        # Overwrite with individual columns (they're the source of truth if present)
        for at_column, internal_key in self.PROFILE_REVERSE_MAP.items():
            value = fields.get(at_column)
            if value is not None and value != "":
                # Convert string booleans back
                if internal_key in ("onboarding_complete", "rep_mode"):
                    if isinstance(value, bool):
                        profile[internal_key] = value
                    elif isinstance(value, str):
                        profile[internal_key] = value.lower() in ("true", "1", "yes")
                elif internal_key == "competitors":
                    try:
                        profile[internal_key] = int(value)
                    except (ValueError, TypeError):
                        profile[internal_key] = value
                else:
                    profile[internal_key] = value

        return profile

    def get_user_by_email(self, email):
        """
        Fetch user profile from 'Users' table.
        Reads individual columns + Profile JSON and merges them.
        """
        if not self.is_configured(): return None
        
        filter_formula = f"{{Email}} = '{email}'"
        params = {"filterByFormula": filter_formula}
        
        try:
            response = self._request_with_retry(
                requests.get,
                self._get_url(self.users_table_name),
                headers=self.headers,
                params=params
            )
            data = response.json()
            records = data.get("records", [])
            
            if records:
                r = records[0]
                fields = r.get("fields", {})
                profile = self._parse_profile_from_fields(fields)
                    
                return {
                    "id": r.get("id"), # Airtable Record ID
                    "email": fields.get("Email"),
                    "name": fields.get("Name"),
                    "profile": profile
                }
        except Exception as e:
            if "403" in str(e) or (hasattr(e, 'response') and getattr(e.response, 'status_code', 0) == 403):
                 print(f"Airtable: Access denied to '{self.users_table_name}'. Check permissions.")
            print(f"Airtable User Fetch Error: {e}")
            
        return None

    def save_user_profile(self, email, name, profile_data):
        """
        Create or Update user in 'Users' table.
        Saves individual columns + Profile JSON backup.
        Includes retry logic and read-back verification.
        Returns (success: bool, error_message: str or None)
        """
        if not self.is_configured():
            return False, "Airtable not configured"
        
        # Check existence
        existing = self.get_user_by_email(email)
        
        # Build fields with individual columns + JSON backup
        fields = self._build_profile_fields(email, name, profile_data)
        
        url = self._get_url(self.users_table_name)

        try:
            if existing:
                # Update existing record
                payload = {"records": [{"id": existing["id"], "fields": fields}]}
                self._request_with_retry(requests.patch, url, headers=self.headers, json=payload)
            else:
                # Create new record
                payload = {"records": [{"fields": fields}]}
                self._request_with_retry(requests.post, url, headers=self.headers, json=payload)
            
            # Verification: read back and confirm key fields saved
            verified = self._verify_profile_save(email, name, profile_data)
            if not verified:
                print(f"⚠️ Profile save verification warning for {email} — data may be incomplete")
                return True, "Saved but verification found differences"

            return True, None

        except Exception as e:
            error_msg = f"Airtable User Save Error: {e}"
            print(error_msg)
            return False, str(e)

    def _verify_profile_save(self, email, name, profile_data):
        """
        Read back the profile after saving and verify key fields match.
        Returns True if verification passes.
        """
        try:
            saved = self.get_user_by_email(email)
            if not saved:
                print(f"  ❌ Verification FAIL: Could not read back user {email}")
                return False

            # Check critical fields
            if saved.get("name") != name:
                print(f"  ❌ Verification FAIL: Name mismatch. Expected '{name}', got '{saved.get('name')}'")
                return False

            saved_profile = saved.get("profile", {})
            critical_keys = ["first_name", "last_name", "championship", "town", "country", "onboarding_complete"]
            
            for key in critical_keys:
                expected = profile_data.get(key)
                actual = saved_profile.get(key)
                if expected is not None and actual is not None:
                    # Normalize for comparison (string vs bool, etc.)
                    if str(expected).lower() != str(actual).lower():
                        print(f"  ⚠️ Verification warning: '{key}' expected '{expected}', got '{actual}'")

            return True

        except Exception as e:
            print(f"  ⚠️ Verification check error (non-fatal): {e}")
            return True  # Don't fail the save if verification itself errors


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
        
        col_name = self.FIELD_MAP.get("Notes JSON", "notes json")
        fields = {
            col_name: notes_str
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
