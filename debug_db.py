import sqlite3
import json

DB_FILE = "sponsor_finder.db"

def inspect_users():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM users")
    rows = c.fetchall()
    conn.close()
    
    print(f"Found {len(rows)} users:")
    for r in rows:
        print(f"ID: {r[0]}, Email: {r[1]}, Name: {r[2]}")
        # print(f"Profile: {r[3]}") 

if __name__ == "__main__":
    inspect_users()
