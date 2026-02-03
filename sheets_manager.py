import gspread
import pandas as pd
import json
from datetime import datetime
from google.oauth2.service_account import Credentials

# Scopes required for the API
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

class SheetManager:
    def __init__(self):
        self.client = None
        self.sheet = None
        self.worksheet = None
        
    def connect(self, service_account_info, sheet_url):
        """
        Connects to Google Sheets using the provided service account dictionary
        and opens the sheet by URL.
        """
        try:
            creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
            self.client = gspread.authorize(creds)
            self.sheet = self.client.open_by_url(sheet_url)
            self.worksheet = self.sheet.get_worksheet(0) # Default to first sheet
            
            # Ensure headers exist immediately upon connection
            self._ensure_headers()
            
            return True, "Connected successfully"
        except Exception as e:
            return False, str(e)

    def _ensure_headers(self):
        """Check if headers exist, if not create them."""
        expected_headers = [
            "ID", "Business Name", "Sector", "Address", "Website", 
            "Status", "Contact Name", "Last Contact", "Next Action", "Notes JSON", "Value"
        ]
        
        current_headers = self.worksheet.row_values(1)
        if not current_headers:
            self.worksheet.append_row(expected_headers)
            return
            
        # Optional: could check if headers match and update potential mismatches
        # For now, we assume if row 1 exists, it's set up or user-managed.

    def get_leads(self):
        """
        Fetch all leads as a list of dictionaries.
        """
        if not self.worksheet:
            return []
            
        try:
            records = self.worksheet.get_all_records()
        except Exception as e:
            # st.error(f"Sheet Read Error: {e}") # Optional: propagate error?
            return []

        # Clean up keys if necessary, ensure ID is int
        leads = []
        for r in records:
            # Parse Notes JSON safely
            notes_str = str(r.get("Notes JSON", "{}"))
            try:
                if not notes_str.strip():
                     notes = {}
                else:
                    notes = json.loads(notes_str)
            except:
                notes = {}
                
            leads.append({
                "id": r.get("ID"), # Make sure to generate IDs for new rows
                "Business Name": r.get("Business Name"),
                "Sector": r.get("Sector"),
                "Address": r.get("Address"),
                "Website": r.get("Website"),
                "Status": r.get("Status"),
                "Contact Name": r.get("Contact Name"),
                "Last Contact": r.get("Last Contact"),
                "Next Action": r.get("Next Action"),
                "Notes": notes,
                "Value": r.get("Value", 0)
            })
        return leads

    def add_leads_bulk(self, leads_list):
        """
        Appends multiple leads efficiently.
        leads_list: list of dicts
        """
        if not self.worksheet:
            return False, "Not Connected"
            
        try:
            # 1. Get max ID
            records = self.worksheet.get_all_records()
            if records:
                ids = [int(r['ID']) for r in records if str(r['ID']).isdigit()]
                current_max_id = max(ids) if ids else 0
            else:
                current_max_id = 0
                self._ensure_headers()
        except Exception as e:
            return False, f"Failed to read sheet for ID gen: {e}"
            
        # 2. Prepare Rows
        rows_to_add = []
        for i, lead in enumerate(leads_list):
            new_id = current_max_id + 1 + i
            row = [
                new_id,
                lead.get("Business Name", ""),
                lead.get("Sector", ""),
                lead.get("Address", ""),
                lead.get("Website", ""),
                lead.get("Status", "Pipeline"),
                lead.get("Contact Name", ""),
                lead.get("Last Contact", "Never"),
                lead.get("Next Action", datetime.now().strftime("%Y-%m-%d")),
                json.dumps(lead.get("Notes", {}))
            ]
            rows_to_add.append(row)
            
        # 3. Bulk Append
        if rows_to_add:
            try:
                self.worksheet.append_rows(rows_to_add)
                return True, f"Added {len(rows_to_add)} leads"
            except Exception as e:
                return False, f"Failed to append rows: {e}"
        return False, "No data to add"

    def add_lead(self, lead_data):
        """
        Appends a new lead. Generates a new ID based on max ID found.
        lead_data: dict with keys matching headers (except ID)
        """
        if not self.worksheet:
            return False
            
        try:
            # Calc new ID
            records = self.worksheet.get_all_records()
            if records:
                # Extract IDs, filter out empty ones
                ids = [int(r['ID']) for r in records if str(r['ID']).isdigit()]
                new_id = max(ids) + 1 if ids else 1
            else:
                new_id = 1
                self._ensure_headers() # Ensure headers if empty sheet
        except Exception:
            return False # Read failed
            
        row = [
            new_id,
            lead_data.get("Business Name", ""),
            lead_data.get("Sector", ""),
            lead_data.get("Address", ""),
            lead_data.get("Website", ""),
            lead_data.get("Status", "Pipeline"),
            lead_data.get("Contact Name", ""),
            lead_data.get("Last Contact", "Never"),
            lead_data.get("Next Action", datetime.now().strftime("%Y-%m-%d")),
            json.dumps(lead_data.get("Notes", {})),
            lead_data.get("Value", 0)
        ]
        
        try:
            self.worksheet.append_row(row)
            return True
        except Exception:
            return False

    def update_lead_status(self, lead_id, new_status, next_date=None):
        """Find row by ID and update status."""
        try:
            cell = self.worksheet.find(str(lead_id), in_column=1)
        except gspread.exceptions.CellNotFound:
            return False
            
        row_idx = cell.row
        
        # Column indices (1-based):
        # ID=1, BusName=2, Sect=3, Addr=4, Web=5, Stat=6, Cont=7, Last=8, Next=9, Notes=10
        
        # Update Status (Col 6)
        self.worksheet.update_cell(row_idx, 6, new_status)
        
        # Update Last Contact (Col 8) to Today
        self.worksheet.update_cell(row_idx, 8, datetime.now().strftime("%Y-%m-%d"))
        
        # Update Next Action (Col 9) if provided
        if next_date:
            self.worksheet.update_cell(row_idx, 9, next_date)
            
        return True

    def update_lead_notes(self, lead_id, notes_data):
        try:
            cell = self.worksheet.find(str(lead_id), in_column=1)
        except gspread.exceptions.CellNotFound:
            return False
        
        row_idx = cell.row
        notes_json = json.dumps(notes_data)
        self.worksheet.update_cell(row_idx, 10, notes_json) # Col 10
        return True

    def update_lead_contact(self, lead_id, contact_name):
        try:
            cell = self.worksheet.find(str(lead_id), in_column=1)
        except gspread.exceptions.CellNotFound:
            return False
        
        row_idx = cell.row
        self.worksheet.update_cell(row_idx, 7, contact_name) # Col 7 is Contact Name
        return True

    def update_lead_value(self, lead_id, value):
        try:
            cell = self.worksheet.find(str(lead_id), in_column=1)
        except gspread.exceptions.CellNotFound:
            return False
        
        row_idx = cell.row
        self.worksheet.update_cell(row_idx, 11, value) # Col 11 is Value
        return True

    def delete_lead(self, lead_id):
        try:
            cell = self.worksheet.find(str(lead_id), in_column=1)
        except gspread.exceptions.CellNotFound:
            return False
        self.worksheet.delete_rows(cell.row)
        return True

# Singleton instance
sheet_manager = SheetManager()
