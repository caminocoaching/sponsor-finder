import sqlite3
import json
from datetime import datetime

import streamlit as st
from sheets_manager import sheet_manager
from airtable_manager import airtable_manager

DB_FILE = "sponsor_finder.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Create Users Table

    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE,
                    name TEXT,
                    profile_json TEXT
                )''')
    
    # Simple migration: Add email column if it doesn't exist (for existing dev sets)
    try:
        c.execute("ALTER TABLE users ADD COLUMN email TEXT")
    except sqlite3.OperationalError:
        pass # Column likely exists
    
    # Create Leads Table
    c.execute('''CREATE TABLE IF NOT EXISTS leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    business_name TEXT,
                    sector TEXT,
                    location TEXT,
                    website TEXT,
                    status TEXT,
                    contact_name TEXT,
                    last_contact_date TEXT,
                    next_action_date TEXT,
                    notes_json TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )''')
    
    # Simple migration: Add email column if it doesn't exist (for existing dev sets)
    try:
        c.execute("ALTER TABLE users ADD COLUMN email TEXT")
    except sqlite3.OperationalError:
        pass # Column likely exists

    # Migration: Add website if missing
    try:
        c.execute("ALTER TABLE leads ADD COLUMN website TEXT")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

# ... (user functions unchanged)

def get_user_by_email(email):
    # 1. Fetch Local SQLite Data (Baseline)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, email, name, profile_json FROM users WHERE email=?", (email,))
    user_local = c.fetchone()
    conn.close()

    local_profile = {}
    local_data = None
    if user_local:
        try:
            p_json = user_local[3]
            local_profile = json.loads(p_json) if p_json and p_json.strip() else {}
        except:
            local_profile = {}
        local_data = {"id": user_local[0], "email": user_local[1], "name": user_local[2], "profile": local_profile}

    # 2. Fetch Airtable Data (Overwrite/Sync)
    if airtable_manager.is_configured():
        at_user = airtable_manager.get_user_by_email(email)
        if at_user:
            # MERGE STRATEGY: Local < Airtable (Airtable wins)
            # But if Airtable profile is empty, keep local!
            merged_profile = local_profile.copy()
            at_profile = at_user.get("profile", {})
            
            # Only update keys that are present and not empty in Airtable
            for k, v in at_profile.items():
                if v: # Is not None/Empty
                    merged_profile[k] = v
            
            # Return combined object
            # Prefer Airtable ID (string) if we want to write back to it, but app uses ID for local DB specific logic...
            # Actually, app uses ID for simple checks. Let's return local ID if available to keep SQLite happy, 
            # but maybe we need both. For now, let's stick to returning what matches the system.
            # If we return at_user, ID is string. If we return local, ID is int.
            
            # If we have local data, use local ID but merged profile
            if local_data:
                local_data["profile"] = merged_profile
                return local_data
            else:
                # User exists in Airtable but not Locally? Sync down.
                # (Ideally we should insert into local here)
                return at_user

    return local_data

def get_user_profile(user_id):
    # Retrieve by ID (usually from session state)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, email, name, profile_json FROM users WHERE id=?", (user_id,))
    user = c.fetchone()
    conn.close()
    
    if user:
        email = user[1]
        name = user[2]
        try:
            p_json = user[3]
            local_profile = json.loads(p_json) if p_json and p_json.strip() else {}
        except:
            local_profile = {}
            
        # Check Airtable for updates
        if airtable_manager.is_configured():
             at_user = airtable_manager.get_user_by_email(email)
             if at_user:
                 at_profile = at_user.get("profile", {})
                 # Merge: Update local with non-empty Airtable values
                 for k, v in at_profile.items():
                     if v: local_profile[k] = v
        
        return {"id": user[0], "email": email, "name": name, "profile": local_profile}
    
    return None

def save_user_profile(email, name, profile_data):
    # 1. Save to Airtable
    if airtable_manager.is_configured():
        airtable_manager.save_user_profile(email, name, profile_data)

    # 2. Save to Local SQLite (Always keep a backup/cache)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Check if user exists
    c.execute("SELECT id FROM users WHERE email=?", (email,))
    exists = c.fetchone()
    
    profile_json = json.dumps(profile_data)
    
    if exists:
        user_id = exists[0]
        c.execute("UPDATE users SET name=?, profile_json=? WHERE email=?", (name, profile_json, email))
    else:
        c.execute("INSERT INTO users (email, name, profile_json) VALUES (?, ?, ?)", (email, name, profile_json))
        user_id = c.lastrowid
    
    conn.commit()
    conn.close()
    return user_id

def add_lead(user_id, business_name, sector, location, website="", status="Pipeline", notes_json="{}", next_action_date=None, contact_name="", last_contact_date="Never"):
    # Priority: Airtable -> GSheets -> SQLite
    
    # 1. Airtable (Centralized)
    if airtable_manager.is_configured():
        user = get_user_profile(user_id)
        if user and user.get("email"):
             if isinstance(notes_json, str):
                try:
                    notes_dict = json.loads(notes_json)
                except:
                    notes_dict = {}
             else:
                notes_dict = notes_json

             data = {
                "Business Name": business_name,
                "Sector": sector,
                "Address": location,
                "Website": website,
                "Status": status,
                "Contact Name": contact_name,
                "Last Contact": last_contact_date,
                "Next Action": next_action_date,
                "Notes": notes_dict
            }
             at_result = airtable_manager.add_lead(user["email"], data)
             if at_result:
                 return at_result
             else:
                 st.warning("⚠️ Failed to save to Airtable. Saving locally instead...")
        else:
             st.error("Airtable Configured but User Email not found in DB.")

    # 2. GSheets Handling (Legacy/Optional)
    if "use_sheets" in st.session_state and st.session_state["use_sheets"]:
        if isinstance(notes_json, str):
            try:
                notes_dict = json.loads(notes_json)
            except:
                notes_dict = {}
        else:
            notes_dict = notes_json
            
        data = {
            "Business Name": business_name,
            "Sector": sector,
            "Address": location,
            "Website": website,
            "Status": status,
            "Contact Name": contact_name,
            "Last Contact": last_contact_date,
            "Next Action": next_action_date,
            "Notes": notes_dict
        }
        return sheet_manager.add_lead(data)

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Avoid duplicates based on business name
    c.execute("SELECT id FROM leads WHERE business_name=? AND user_id=?", (business_name, user_id))
    existing = c.fetchone()
    if existing:
        conn.close()
        return False # Duplicate
    
    # Ensure notes is a string
    if isinstance(notes_json, dict):
        notes_json = json.dumps(notes_json)
        
    if not next_action_date:
        next_action_date = datetime.now().strftime("%Y-%m-%d")

    c.execute('''INSERT INTO leads (user_id, business_name, sector, location, website, status, contact_name, last_contact_date, next_action_date, notes_json)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (user_id, business_name, sector, location, website, status, contact_name, last_contact_date, next_action_date, notes_json))
    
    new_id = c.lastrowid
    conn.commit()
    conn.close()
    return new_id

def get_leads(user_id):
    if airtable_manager.is_configured():
        user = get_user_profile(user_id)
        if user and user.get("email"):
             return airtable_manager.get_leads(user["email"])

    if "use_sheets" in st.session_state and st.session_state["use_sheets"]:
        return sheet_manager.get_leads()

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Explicit Select to handle schema variations safely
    # Note: 'website' might obtain NULL if not filled, which is fine.
    try:
        c.execute('''SELECT id, business_name, sector, location, status, contact_name, last_contact_date, next_action_date, notes_json, website 
                     FROM leads WHERE user_id=? ORDER BY id DESC''', (user_id,))
    except sqlite3.OperationalError:
        # Fallback if website col doesn't exist (migration failed?)
        c.execute('''SELECT id, business_name, sector, location, status, contact_name, last_contact_date, next_action_date, notes_json, "" 
                     FROM leads WHERE user_id=? ORDER BY id DESC''', (user_id,))
        
    rows = c.fetchall()
    conn.close()
    
    leads = []
    for r in rows:
        website_val = r[9] if r[9] else ""
        
        leads.append({
            "id": r[0],
            "Business Name": r[1],
            "Sector": r[2],
            "Address": r[3],
            "Status": r[4],
            "Contact Name": r[5],
            "Last Contact": r[6],
            "Next Action": r[7],
            "Notes": json.loads(r[8]) if r[8] else {},
            "Website": website_val
        })
    return leads

def update_lead_status(lead_id, status, next_date=None):
    if airtable_manager.is_configured():
        return airtable_manager.update_lead_status(lead_id, status, next_date)

    if "use_sheets" in st.session_state and st.session_state["use_sheets"]:
        return sheet_manager.update_lead_status(lead_id, status, next_date)

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    if next_date:
        c.execute("UPDATE leads SET status=?, next_action_date=?, last_contact_date=? WHERE id=?", 
                  (status, next_date, datetime.now().strftime("%Y-%m-%d"), lead_id))
    else:
        c.execute("UPDATE leads SET status=?, last_contact_date=? WHERE id=?", 
                  (status, datetime.now().strftime("%Y-%m-%d"), lead_id))
    conn.commit()
    conn.close()

def update_lead_notes(lead_id, notes_data):
    if airtable_manager.is_configured():
        return airtable_manager.update_lead_notes(lead_id, notes_data)

    if "use_sheets" in st.session_state and st.session_state["use_sheets"]:
        return sheet_manager.update_lead_notes(lead_id, notes_data)

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    notes_json = json.dumps(notes_data)
    c.execute("UPDATE leads SET notes_json=? WHERE id=?", (notes_json, lead_id))
    conn.commit()
    conn.close()

def delete_lead(lead_id):
    if airtable_manager.is_configured():
        return airtable_manager.delete_lead(lead_id)

    if "use_sheets" in st.session_state and st.session_state["use_sheets"]:
        return sheet_manager.delete_lead(lead_id)

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM leads WHERE id=?", (lead_id,))
    conn.commit()
    conn.close()
