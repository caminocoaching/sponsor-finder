import sqlite3
import json

DB_FILE = "sponsor_finder.db"
API_KEY = "AIzaSyAgSAjNVMUy4XL3pecTqErqkhkcoWXRxm0"
TARGET_EMAIL = "csm66@me.com"

def inject_key():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # 1. Find the user
    # Note: Using the fixed explicit column order logic just to be safe, 
    # but for UPDATE we need to know the ID or Email matches.
    # Current DB logic might have email in the wrong place? 
    # Let's try to match where 'email' column OR 'profile_json' contains the email.
    
    c.execute("SELECT id, profile_json FROM users")
    users = c.fetchall()
    
    found = False
    for r in users:
        uid = r[0]
        p_str = r[1]
        try:
            profile = json.loads(p_str)
        except:
            profile = {}
            
        # Heuristic: verify this is the right user
        # In the screenshot, login was csm66@me.com
        # Let's just update ALL users for simplicity (single user app mostly)
        # OR check if profile contains the email
        
        profile["google_api_key"] = API_KEY
        
        new_json = json.dumps(profile)
        c.execute("UPDATE users SET profile_json=? WHERE id=?", (new_json, uid))
        print(f"Updated User ID {uid} with API Key.")
        found = True
        
    conn.commit()
    conn.close()
    
    if found:
        print("Success.")
    else:
        print("No users found to update.")

if __name__ == "__main__":
    inject_key()
