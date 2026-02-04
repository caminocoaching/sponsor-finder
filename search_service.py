import requests
import math
import time
import random
import json
from outscraper import OutscraperClient 
import streamlit as st
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# [FILTER] Generic filters to clean up noisy results
BLACKLIST_TERMS = [
    "taxi", "cab", "chauffeur", "limousine", "shuttle", "ambulance", 
    "courier", "delivery service", "uber", "lyft", 
    "przeprowadzki", "moving company", "removals", "house clearance",
    "post office", "service point", "parcel", "inpost", "collection point", "pickup", "dropoff",
    "cleaner", "cleaning", "car wash", "valeting", "laundry", "dry cleaner",
    "food", "pizza", "takeaway", "restaurant", "catering", "burger", "chicken", "cafe", "coffee",
    "storage", "self storage", "lock up", "garage", "repair", "mechanic", "tyre", "tires", "breakdown"
]

def get_robust_session():
    """
    Creates a requests session with retry logic for network resilience.
    """
    session = requests.Session()
    # Retry on: 500, 502, 503, 504 and connection errors
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

def search_outscraper(api_key, query, location_str, radius=50, limit=20, google_api_key=None):
    """
    ROBUST UNIVERSAL SEARCH:
    1. Geocode location
    2. Try Outscraper SDK (Google Maps Search)
    3. Fallback to Direct V3 API if SDK fails (DNS/Network issues)
    4. Strict Filtering (Radius & Blacklist)
    """
    st.toast(f"Outscraper: Universal Search ({query})...", icon="🌍")

    # 1. Get Coordinates (Critical for strict search)
    start_lat, start_lon = None, None
    if google_api_key:
         start_lat, start_lon = get_lat_long(google_api_key, location_str)
    
    if not start_lat or not start_lon:
         st.error("Could not determine coordinates. Aborting search to protect budget.")
         return [], None

    radius_meters = int(radius * 1609.34)
    zoom_level = 12 # Default City Zoom
    
    # Attempt 1: SDK (Preferred)
    try:
        # Construct Query with Viewport Intent
        # "Category @Lat,Lon,Zoom"
        # This tells Google we are looking at this specific map area
        sdk_query = f"{query} @{start_lat},{start_lon},{zoom_level}z"
        
        # st.caption(f"Trying SDK: {sdk_query}")
        
        client = OutscraperClient(api_key=api_key)
        
        # We assume SDK might accept kwargs for 'dropoff', but if not, we filter later anyway.
        # We pass dropoff just in case it is supported (it often is passed through)
        results = client.google_maps_search(
            [sdk_query],
            limit=limit,
            language='en',
            region='UK',
            dropoff=radius_meters 
        )
        
        # Flatten structure
        raw_businesses = []
        if results and len(results) > 0:
             raw_businesses = results[0]
             
        return process_and_filter_results(raw_businesses, start_lat, start_lon, radius, "Outscraper SDK")

    except Exception as e:
        st.warning(f"SDK Failed ({str(e)}). Switching to Direct API Fallback...")
        # If SDK fails, fall through to Direct API
        pass

    # Attempt 2: Direct V3 API (Fallback)
    try:
        session = get_robust_session()
        endpoint = "https://api.outscraper.com/maps/search-v3"
        
        params = {
            "query": query,
            "coordinates": f"{start_lat},{start_lon}",
            "dropoff": radius_meters,
            "limit": limit,
            "language": "en",
            "region": "UK",
            "async": "false"
        }
        
        headers = {"X-API-KEY": api_key}
        
        resp = session.get(endpoint, params=params, headers=headers, timeout=20)
        
        if resp.status_code != 200:
             return {"error": f"Outscraper API Error {resp.status_code}: {resp.text}"}, None
             
        data = resp.json()
        raw_businesses = []
        if "data" in data and len(data["data"]) > 0:
             raw_businesses = data["data"][0]
             
        return process_and_filter_results(raw_businesses, start_lat, start_lon, radius, "Outscraper V3 API")
        
    except Exception as e:
        return {"error": f"All Search Methods Failed: {str(e)}"}, None

def process_and_filter_results(businesses, start_lat, start_lon, radius_miles, source_label):
    """
    Common filtering logic for both SDK and API results.
    """
    mapped_results = []
    skipped_dist = 0
    skipped_black = 0
    
    for item in businesses:
        name = item.get("name", "Unknown")
        category = item.get("category", item.get("type", ""))
        
        # 1. Blacklist Check
        text_to_check = (name + " " + str(category)).lower()
        if any(term in text_to_check for term in BLACKLIST_TERMS):
            skipped_black += 1
            continue

        # 2. Distance Check
        lat = item.get("latitude")
        lon = item.get("longitude")
        
        dist_val = None
        if lat and lon:
             dist_val = haversine_distance(start_lat, start_lon, lat, lon)
             # Strict Filter: Must be within radius (allow 10% margin)
             if dist_val > (radius_miles * 1.1):
                  skipped_dist += 1
                  continue
             dist_val = round(dist_val, 1)

        mapped_results.append({
            "Business Name": name,
            "Address": item.get("full_address", item.get("address", "")),
            "Rating": item.get("rating", 0.0),
            "Sector": category if category else "Search Result",
            "Website": item.get("site", ""),
            "Phone": item.get("phone", ""),
            "lat": lat,
            "lon": lon,
            "Source": source_label,
            "Distance": dist_val
        })
    
    # st.toast(f"Filtered: {skipped_dist} too far, {skipped_black} blacklisted.", icon="🧹")
    return mapped_results, None


def get_new_coords(lat, lon, miles, bearing_degrees):
    """
    Calculates new Lat/Lon given a starting point, distance (miles), and bearing.
    """
    R = 3958.8 # Earth radius in miles
    lat1 = math.radians(lat)
    lon1 = math.radians(lon)
    brng = math.radians(bearing_degrees)
    d = miles
    lat2 = math.asin( math.sin(lat1)*math.cos(d/R) + math.cos(lat1)*math.sin(d/R)*math.cos(brng))
    lon2 = lon1 + math.atan2(math.sin(brng)*math.sin(d/R)*math.cos(lat1), math.cos(d/R)-math.sin(lat1)*math.sin(lat2))
    return (math.degrees(lat2), math.degrees(lon2), "Offset")

def search_google_legacy_nearby(api_key, keyword, lat, lon, radius_miles):
    """
    Uses the Legacy Nearby Search API which often returns more results 
    using 'keyword' matching rather than 'text' intent matching.
    """
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    radius_meters = int(radius_miles * 1609.34)
    params = {
        "location": f"{lat},{lon}",
        "radius": radius_meters,
        "keyword": keyword,
        "key": api_key
    }
    
    try:
        # Use robust session here too
        session = get_robust_session()
        resp = session.get(url, params=params)
        data = resp.json()
        
        if data.get("status") not in ["OK", "ZERO_RESULTS"]:
             return {"error": data.get("error_message", data.get("status"))}, None
             
        results = []
        for place in data.get("results", []):
             results.append({
                "Business Name": place.get("name"),
                "Address": place.get("vicinity"),
                "Rating": place.get("rating", 0.0),
                "Sector": keyword,
                "Distance": round(haversine_distance(lat, lon, place["geometry"]["location"]["lat"], place["geometry"]["location"]["lng"]), 1),
                "Website": "", 
                "lat": place["geometry"]["location"]["lat"],
                "lon": place["geometry"]["location"]["lng"],
                "Source": "Google Nearby"
            })
            
        return results, data.get("next_page_token")
        
    except Exception as e:
        return {"error": str(e)}, None

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance in miles between two points 
    """
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a)) 
    r = 3959 # Radius of earth
    return c * r

def mock_search_places(location, radius, sector, mode="sector"):
    """
    Generates simulated results for demo/testing without API costs.
    """
    time.sleep(1.0)
    mock_data = []
    num_results = random.randint(5, 15)
    base_lat = 52.0733
    base_lon = -1.0146
    
    if mode == "previous":
        pkgs = ["Logistics", "Construction", "Engineering", "Tools", "Racing"]
        prefixes = ["Red", "Blue", "Apex", "Moto", "Grid", "Podium"]
        suffixes = ["Racing", "Partners", "Supporters", "Group"]
        for _ in range(num_results):
            name = f"{random.choice(prefixes)} {random.choice(pkgs)} {random.choice(suffixes)}"
            mock_data.append({
                "Business Name": name,
                "Address": f"{random.randint(1,99)} Racing Lane, {location}",
                "Rating": 5.0,
                "Sector": "Motorsport Related",
                "Distance": round(random.uniform(0.5, radius), 1),
                "lat": base_lat + random.uniform(-0.05, 0.05),
                "lon": base_lon + random.uniform(-0.05, 0.05)
            })
    else:
        prefixes = ["Elite", "Fast", "Primary", "Apex", "Local", "Global", "Premier", "Trusted"]
        suffixes = ["Ltd", "Inc", "Partners", "Group", "Solutions", "Services"]
        sector_term = sector.split(" ")[0] if sector != "Other (type your own)" else "Business"

        for _ in range(num_results):
            name = f"{random.choice(prefixes)} {sector_term} {random.choice(suffixes)}"
            mock_data.append({
                "Business Name": name,
                "Address": f"{random.randint(1, 999)} High St, {location}",
                "Rating": round(random.uniform(3.5, 5.0), 1),
                "Sector": sector,
                "Distance": round(random.uniform(0.5, radius), 1),
                "lat": base_lat + random.uniform(-0.05, 0.05),
                "lon": base_lon + random.uniform(-0.05, 0.05)
            })
            
    return mock_data


def get_lat_long(api_key, location_name):
    """
    Helper to resolve a location string (e.g. "Silverstone, UK") to Lat/Lon.
    """
    if "Middleton Cheney" in location_name:
         return 52.073, -1.274

    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.location"
    }
    payload = {"textQuery": location_name}
    
    try:
        session = get_robust_session()
        resp = session.post(url, json=payload, headers=headers)
        data = resp.json()
        if "places" in data and len(data["places"]) > 0:
            loc = data["places"][0]["location"]
            return loc["latitude"], loc["longitude"]
    except:
        pass
    return None, None

def search_google_places(api_key, query, location_ctx, radius_miles, sector_name=None, pagetoken=None):
    """
    Searches Google Places API (New Text Search).
    """
    url = "https://places.googleapis.com/v1/places:searchText"
    
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.rating,places.location,places.businessStatus,places.websiteUri,nextPageToken"
    }
    
    start_lat, start_lon = get_lat_long(api_key, location_ctx)

    if pagetoken:
        payload = {"pageToken": pagetoken}
    else:
        lat, lon = start_lat, start_lon
        
        payload = {
            "textQuery": query,
            "maxResultCount": 20
        }
        
        if lat and lon:
            radius_meters = min(int(radius_miles * 1609.34), 50000)
            payload["locationBias"] = {
                "circle": {
                    "center": {"latitude": lat, "longitude": lon},
                    "radius": radius_meters
                }
            }
            payload["textQuery"] = f"{query} within {radius_miles} miles of {location_ctx}"
        else:
             payload["textQuery"] = f"{query} within {radius_miles} miles of {location_ctx}"
    
    current_results = []
    next_token = None

    try:
        # Log feedback
        if pagetoken:
            st.toast("Fetching next page...", icon="🔄")
        else:
            st.toast(f"Starting search for '{query}'...", icon="🔎")
            
        session = get_robust_session()
        response = session.post(url, json=payload, headers=headers)
        
        if response.status_code != 200:
             return {"error": f"API Error {response.status_code}: {response.text}"}, None
             
        data = response.json()
        places = data.get("places", [])
        
        batch_results = []
        
        for place in places:
            name = place.get("displayName", {}).get("text", "Unknown")
            addr = place.get("formattedAddress", "Unknown")
            rating = place.get("rating", 0.0)
            status = place.get("businessStatus", "UNKNOWN")
            website = place.get("websiteUri", "")
            
            loc = place.get("location", {})
            lat = loc.get("latitude")
            lon = loc.get("longitude")
            
            dist_val = None
            if lat and lon and start_lat and start_lon:
                 dist_val = round(haversine_distance(start_lat, start_lon, lat, lon), 1)

            res_obj = {
                "Business Name": name,
                "Address": addr,
                "Rating": rating,
                "Sector": sector_name if sector_name else "Search Result",
                "Distance": dist_val,
                "Website": website,
                "lat": lat,
                "lon": lon
            }
            batch_results.append(res_obj)
        
        current_results = batch_results
        next_token = data.get("nextPageToken")
        
        return current_results, next_token

    except Exception as e:
        print(f"Search Error: {e}")
        return [], None
