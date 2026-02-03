import requests
import math
import time
import random
import json
import urllib.parse
import streamlit as st # Added for debug feedback
from outscraper import OutscraperClient # [NEW] Use official SDK

def search_outscraper(api_key, query, location_str, radius=50, limit=100):
    """
    Uses Outscraper SDK to find businesses. Best for comprehensive lists.
    """
    try:
        st.toast(f"Outscraper SDK: Contacting ({query})...", icon="📡")
        
        client = OutscraperClient(api_key=api_key)
        
        # Outscraper SDK expects query as list or string
        # We combine query + location logic somewhat, but for maps search
        # the 'query' param in SDK is the main search term.
        # It handles "Transport near Banbury" well if we form it that way.
        
        # Construct query with location to be safe
        search_term = f"{query} near {location_str}"
        
        # SDK Call
        # limit per query
        results = client.google_maps_search(
            [search_term], 
            limit=limit,
            drop_duplicates=True,
            language='en'
        )
        
        # Results is a list of lists (one per query)
        # results = [[{...}, {...}]]
        
        mapped_results = []
        if results and len(results) > 0:
            batch = results[0] # Results for first query
            for item in batch:
                mapped_results.append({
                    "Business Name": item.get("name", "Unknown"),
                    "Address": item.get("full_address", item.get("address", "")),
                    "Rating": item.get("rating", 0.0),
                    "Sector": item.get("category", item.get("type", "Search Result")),
                    "Website": item.get("site", ""),
                    "Phone": item.get("phone", ""),
                    "lat": item.get("latitude"),
                    "lon": item.get("longitude"),
                    "Source": "Outscraper SDK"
                })
                
        return mapped_results, None

    except Exception as e:
        return {"error": f"Outscraper SDK Error: {str(e)}"}, None

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
                "lat": base_lat + random.uniform(-0.05, 0.05),
                "lon": base_lon + random.uniform(-0.05, 0.05)
            })
            
    return mock_data


def get_lat_long(api_key, location_name):
    """
    Helper to resolve a location string (e.g. "Silverstone, UK") to Lat/Lon.
    Uses the same Places API Text Search but looks for the location itself.
    """
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
    if pagetoken:
        payload = {"pageToken": pagetoken}
        # V1 Text Search requires the textQuery to be present even with pageToken? 
        # Documentation says "pageToken" is part of the request body.
        # It is safest to include the original textQuery too, but usually token implies context.
        # Let's try minimal first, but if it fails we might need to cache the query.
        # ACTUALLY: The standard pattern is just pageToken in body.
    else:
        # Geocode center only for first request
        lat, lon = get_lat_long(api_key, location_ctx)
        
        payload = {
            "textQuery": query,
            "maxResultCount": 20
        }
        
        if lat and lon:
            # Convert miles to meters
            radius_meters = int(radius_miles * 1609.34)
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
            
            # Simple result object
            batch_results.append({
                "Business Name": name,
                "Address": addr,
                "Rating": rating,
                "Sector": sector_name if sector_name else "Search Result",
                "Website": website,
                "lat": lat,
                "lon": lon
            })
        
        current_results = batch_results
        next_token = data.get("nextPageToken")
        
        return current_results, next_token

    except Exception as e:
        print(f"Search Error: {e}")
        return [], None

