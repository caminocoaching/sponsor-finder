import sqlite3
import json
from datetime import datetime

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
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Explicitly select columns to match expected tuple indices
    c.execute("SELECT id, email, name, profile_json FROM users WHERE email=?", (email,))
    user = c.fetchone()
    conn.close()
    if user:
        try:
            # Handle empty string or None
            p_json = user[3]
            profile = json.loads(p_json) if p_json and p_json.strip() else {}
        except json.JSONDecodeError:
            profile = {}
            
        return {"id": user[0], "email": user[1], "name": user[2], "profile": profile}
    return None

def get_user_profile(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, email, name, profile_json FROM users WHERE id=?", (user_id,))
    user = c.fetchone()
    conn.close()
    if user:
        try:
            p_json = user[3]
            profile = json.loads(p_json) if p_json and p_json.strip() else {}
        except json.JSONDecodeError:
            profile = {}
        return {"id": user[0], "email": user[1], "name": user[2], "profile": profile}
    return None

def save_user_profile(email, name, profile_data):
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
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Avoid duplicates based on business name
    c.execute("SELECT id FROM leads WHERE business_name=? AND user_id=?", (business_name, user_id))
    if c.fetchone():
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
    
    conn.commit()
    conn.close()
    return True

def get_leads(user_id):
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
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    notes_json = json.dumps(notes_data)
    c.execute("UPDATE leads SET notes_json=? WHERE id=?", (notes_json, lead_id))
    conn.commit()
    conn.close()

def delete_lead(lead_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM leads WHERE id=?", (lead_id,))
    conn.commit()
    conn.close()
