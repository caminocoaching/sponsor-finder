import requests
import streamlit as st
import math

# Load Secrets
try:
    if "google_api_key" in st.secrets:
        api_key = st.secrets["google_api_key"]
    elif "google" in st.secrets and "api_key" in st.secrets["google"]:
        api_key = st.secrets["google"]["api_key"]
    else:
        # Fallback to direct load or env var if needed (unlikely in this context)
        # Based on file check: google_api_key = "AIza..." at top level
        import toml
        with open(".streamlit/secrets.toml", "r") as f:
            c = toml.load(f)
            api_key = c.get("google_api_key")
except Exception as e:
    print(f"Error loading key: {e}")
    exit()

def test_search():
    print(f"Using API Key: {api_key[:5]}...")
    
    query = "Transport & haulage"
    location = "Swindon, UK"
    
    # URL
    url = "https://places.googleapis.com/v1/places:searchText"
    
    # Headers
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.businessStatus,nextPageToken"
    }
    
    # Payload (Use the 'else' branch logic for > 30 miles)
    payload = {
        "textQuery": f"{query} near {location}"
    }

    print(f"Sending request to {url}")
    print(f"Payload: {payload}")
    
    resp = requests.post(url, json=payload, headers=headers)
    print(f"Status Code: {resp.status_code}")
    
    if resp.status_code != 200:
        print(f"Error: {resp.text}")
        return

    data = resp.json()
    places = data.get("places", [])
    print(f"Page 1 Results: {len(places)}")
    
    next_token = data.get("nextPageToken")
    print(f"Next Token Present: {bool(next_token)}")
    if next_token:
        print(f"Next Token Preview: {next_token[:20]}...")
        
        # Try Page 2
        import time
        print("Waiting 2s...")
        time.sleep(2)
        
        payload["pageToken"] = next_token
        resp2 = requests.post(url, json=payload, headers=headers)
        data2 = resp2.json()
        places2 = data2.get("places", [])
        print(f"Page 2 Results: {len(places2)}")
        print(f"Total Results: {len(places) + len(places2)}")
    else:
        print("No next page token returned. API returned single page.")

if __name__ == "__main__":
    test_search()
