import asyncio
import time
import search_service
from search_service import search_outscraper

# Mock geocoder to avoid needing Google API Key for basic search logic test
def mock_get_lat_long(api_key, location_name):
    # Return approx coords for Swindon/Birmingham/Manchester to pass the check
    if "Swindon" in location_name: return 51.568, -1.772
    if "Birmingham" in location_name: return 52.486, -1.890
    if "Manchester" in location_name: return 53.480, -2.242
    return 51.507, -0.127 # London default

search_service.get_lat_long = mock_get_lat_long

import streamlit as st

# Mock streamlit secrets and toast/error/warning to run in terminal
if not hasattr(st, "secrets"):
    st.secrets = {}
if not hasattr(st, "toast"):
    st.toast = lambda msg, icon="": print(f"[TOAST] {icon} {msg}")
if not hasattr(st, "warning"):
    st.warning = lambda msg, icon="": print(f"[WARNING] {icon} {msg}")
if not hasattr(st, "error"):
    st.error = lambda msg, icon="": print(f"[ERROR] {icon} {msg}")

# You need to provide your API Key here or load it from a file/secrets
# For this test script, we will try to load it from the app's secrets.toml if possible, 
# or expect the user to have it in the environment or passed in.
# For now, I'll attempt to read it from the user's pasted content if it was there, but it wasn't.
# I will assume the user has a valid key in their secrets or I can grab it from their profile if I could access DB,
# but simplest is to ask or try to find where it's stored.
# `start_service.py` functions take `api_key` as an argument.

# Let's try to find an API key from the environment or secrets file if available.
import toml
import os

API_KEY = ""
try:
    with open(".streamlit/secrets.toml", "r") as f:
        secrets = toml.load(f)
        # Try various keys
        if "outscraper_api_key" in secrets:
            API_KEY = secrets["outscraper_api_key"]
        elif "airtable" in secrets and "outscraper_api_key" in secrets["airtable"]:
            API_KEY = secrets["airtable"]["outscraper_api_key"]
            
        print(f"Loaded Key: {API_KEY[:5]}...{API_KEY[-5:] if len(API_KEY)>10 else ''}")
except Exception as e:
    print(f"Could not load secrets: {e}")

if not API_KEY:
    print("❌ No API Key found in secrets.toml. Please create one or set it in this script.")
    # Fallback to a valid key if I knew one, but I don't.
    # The previous code context didn't reveal the full key.
    # I will proceed, assuming the user might put it in or I will see if I can find it in `db_manager` usage.
    pass

GOOGLE_KEY = "" # Optional, for geocoding latitude/longitude if needed by `search_outscraper`

def run_tests():
    print('\n' + '█'*70)
    print('   QUERY FORMAT TESTING (PYTHON PORT)')
    print('█'*70)

    test_cases = [
        {
            'sector': 'Transport & haulage', # Using the mapped name from the app
            'query': 'Haulage companies', # Using the optimized query
            'location': 'Swindon',
            'radius': 50
        },
        {
            'sector': 'Construction',
            'query': 'Building supplies',
            'location': 'Birmingham',
            'radius': 30
        },
        {
            'sector': 'Food & beverage',
            'query': 'Food manufacturer',
            'location': 'Manchester',
            'radius': 40
        }
    ]

    for test in test_cases:
        print(f"\n{'='*70}")
        print(f"Testing: {test['query']} in {test['location']} ({test['radius']} miles)")
        print(f"{'='*70}")

        try:
            # Note: search_outscraper returns (results, token)
            # It expects: api_key, query, location_str, radius, limit, google_api_key
            results, token = search_outscraper(
                api_key=API_KEY,
                query=test['query'],
                location_str=test['location'],
                radius=test['radius'],
                limit=5, # Small limit for testing
                google_api_key="TEST_KEY_TO_TRIGGER_MOCK" # Trigger the mock geocoder
            )

            # Check if results is valid
            if results is None:
                results = []

            if isinstance(results, dict) and "error" in results:
                print(f"\n❌ API Error: {results['error']}")
                continue

            print(f"\n✅ SUCCESS!")
            print(f"   Found: {len(results)} businesses")
            # The python function returns a list of dicts, it doesn't return metadata about query used in the return value
            # unless we modified it to do so. But we can see the results.

            if len(results) > 0:
                print('\n📋 Top 3 Results:')
                for i, s in enumerate(results[:3]):
                    dist = s.get('Distance', 'N/A')
                    print(f"   {i + 1}. {s['Business Name']} ({dist} mi)")
            else:
                print("   (No results returned)")

        except Exception as e:
            print(f"\n❌ FAILED: {str(e)}")
            import traceback
            traceback.print_exc()

        # Wait
        time.sleep(2)

    print('\n' + '█'*70)
    print('   TESTING COMPLETE')
    print('█'*70 + '\n')

if __name__ == "__main__":
    if not API_KEY:
        print("Skipping test run because no API KEY was found.")
    else:
        run_tests()
