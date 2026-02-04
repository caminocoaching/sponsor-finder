import requests
import math
import time
import random
import json
import urllib.parse
import streamlit as st # Added for debug feedback
from outscraper import OutscraperClient # Keeping import, though we use requests for V3 control

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

def search_outscraper(api_key, query, location_str, radius=50, limit=20, google_api_key=None):
    """
    COST-OPTIMIZED SEARCH (V3):
    Uses Outscraper V3 API with strict coordinate + dropoff filtering.
    - Prevents "national" searches (saving money)
    - Enforces strict radius (improving accuracy)
    - Returns ~20 highly relevant results instead of 1000+ junk ones.
    """
    try:
        st.toast(f"Outscraper Optimization: Targeting '{query}' within {radius} miles...", icon="🎯")
        
        # 1. Get Coordinates (Critical)
        start_lat, start_lon = None, None
        if google_api_key:
             start_lat, start_lon = get_lat_long(google_api_key, location_str)
        
        if not start_lat or not start_lon:
             # Fallback if geocoding fails
             st.error("Could not determine coordinates for strict search. Aborting to save cost.")
             return [], None

        # 2. Calculate Strict Radius
        # 1 mile = 1609.34 meters
        radius_meters = int(radius * 1609.34)
        
        # 3. Construct V3 Request (Low Cost Mode)
        # We use the REST API directly to ensure we use the 'dropoff' parameter correctly
        endpoint = "https://api.outscraper.com/maps/search-v3"
        
        params = {
            "query": query,             # Just the sector, NO location string
            "coordinates": f"{start_lat},{start_lon}",
            "dropoff": radius_meters,   # STRICT LIMIT
            "limit": limit,             # Cap results to save money
            "language": "en",
            "region": "UK",
            "async": "false"            # Synch mode for immediate results
        }
        
        headers = {"X-API-KEY": api_key}
        
        # st.caption(f"Connecting to Outscraper: {query} @ {start_lat},{start_lon} (Radius: {radius_meters}m)")
        
        resp = requests.get(endpoint, params=params, headers=headers)
        
        if resp.status_code != 200:
             return {"error": f"Outscraper API Error {resp.status_code}: {resp.text}"}, None
             
        data = resp.json()
        
        # Parse V3 Response Structure: data['data'][0] is the list of results
        businesses = []
        if "data" in data and len(data["data"]) > 0:
             businesses = data["data"][0]
             
        # 4. Process & Strict Filter
        mapped_results = []
        
        for item in businesses:
            name = item.get("name", "Unknown")
            category = item.get("category", item.get("type", ""))
            
            # [FILTER] Blacklist Check (Safety Net)
            text_to_check = (name + " " + str(category)).lower()
            if any(term in text_to_check for term in BLACKLIST_TERMS):
                continue

            # [FILTER] Distance Check (Double Safety)
            lat = item.get("latitude")
            lon = item.get("longitude")
            
            dist_val = None
            if lat and lon:
                 dist_val = haversine_distance(start_lat, start_lon, lat, lon)
                 # Hard Reject if outside 1.1x radius (allow margin for road vs flight)
                 if dist_val > (radius * 1.1):
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
                "Source": "Outscraper V3",
                "Distance": dist_val
            })
            
        return mapped_results, None

    except Exception as e:
        return {"error": f"Search Error: {str(e)}"}, None

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
        resp = requests.get(url, params=params)
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
                "Website": "", # Legacy search doesn't return website in list view usually, needs detail fetch. Ignored for speed.
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
    on the earth (specified in decimal degrees)
    """
    # Convert decimal degrees to radians 
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
    
    # Haversine formula 
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a)) 
    r = 3959 # Radius of earth in miles
    return c * r

def mock_search_places(location, radius, sector, mode="sector"):
    """
    Generates simulated results for demo/testing without API costs.
    """
    time.sleep(1.0)
    mock_data = []
    num_results = random.randint(5, 15)
    
    # Lat/Lon for Silverstone approx (just for map demo purposes)
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
    Uses the same Places API Text Search but looks for the location itself.
    """
    # [OPTIMIZATION] Known locations cache to redundant API calls
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
        resp = requests.post(url, json=payload, headers=headers)
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
    Returns (results_list, next_page_token).
    """
    url = "https://places.googleapis.com/v1/places:searchText"
    
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.rating,places.location,places.businessStatus,places.websiteUri,nextPageToken"
    }
    
    # 1. Prepare Payload
    start_lat, start_lon = get_lat_long(api_key, location_ctx)

    if pagetoken:
        payload = {"pageToken": pagetoken}
    else:
        # Geocode center only for first request
        lat, lon = start_lat, start_lon
        
        payload = {
            "textQuery": query,
            "maxResultCount": 20
        }
        
        if lat and lon:
            # Convert miles to meters (Google Limit is 50,000 meters ~31 miles)
            radius_meters = min(int(radius_miles * 1609.34), 50000)
            payload["locationBias"] = {
                "circle": {
                    "center": {"latitude": lat, "longitude": lon},
                    "radius": radius_meters
                }
            }
            # Also append location to query for good measure if bias is weak
            # [OPTIMIZED] Use natural language phrasing that matches Google Maps Web behavior
            # "Transport & haulage within 50 miles of Middleton Cheney" works better than "near"
            payload["textQuery"] = f"{query} within {radius_miles} miles of {location_ctx}"
        else:
             # Fallback if geocode fails
             payload["textQuery"] = f"{query} within {radius_miles} miles of {location_ctx}"
             
        # openNow: False - Removed to see all businesses (even closed ones)
        
    
    current_results = []
    next_token = None

    try:
        # Log feedback
        if pagetoken:
            st.toast("Fetching next page...", icon="🔄")
        else:
            st.toast(f"Starting search for '{query}'...", icon="🔎")
            
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code != 200:
             return {"error": f"API Error {response.status_code}: {response.text}"}, None
             
        data = response.json()
        places = data.get("places", [])
        
        # Process this batch
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
            
            # Calc Distance
            dist_val = None
            if lat and lon and start_lat and start_lon:
                 dist_val = round(haversine_distance(start_lat, start_lon, lat, lon), 1)

            # Simple result object
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
