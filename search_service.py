import requests
import math
import time
import random
import json
import urllib.parse
import streamlit as st # Added for debug feedback
from outscraper import OutscraperClient # [NEW] Use official SDK

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

def search_outscraper(api_key, query, location_str, radius=50, limit=100, google_api_key=None):
    """
    Uses Outscraper SDK to find businesses. Best for comprehensive lists.
    """
    try:
        st.toast(f"Outscraper SDK: Contacting ({query})...", icon="📡")
        
        client = OutscraperClient(api_key=api_key)
        
        # 1. Try to resolve coordinates if Google Key is present
        coords_param = None
        zoom_level = 10 # Default for ~50 miles
        start_lat = None
        start_lon = None
        
        if google_api_key:
             start_lat, start_lon = get_lat_long(google_api_key, location_str)
             if start_lat and start_lon:
                 # Calculate Zoom based on Radius (Approximate)
                 # 14 = street, 10 = city, 7 = region
                 if radius <= 5: zoom_level = 13
                 elif radius <= 10: zoom_level = 12
                 elif radius <= 25: zoom_level = 11
                 elif radius <= 50: zoom_level = 10
                 elif radius <= 100: zoom_level = 9
                 elif radius <= 200: zoom_level = 8
                 else: zoom_level = 7
                 
                 # Outscraper supports implied zoom in coordinates sometimes, or we try the comma format
                 # But standard Google Maps URL param is @lat,lon,zoomz
                 # Let's try the specific format that defines viewport:
                 coords_param = f"@{start_lat},{start_lon},{zoom_level}z"
        
        # 2. Construct Query List (Scatter Strategy for Large Value)
        # Detailed "Viewport" searches often fail to return ALL results (Google cap).
        # We split the search into 5 overlapping sub-queries if radius is large (>50 miles).
        
        search_query_list = []
        
        # [CRITICAL] Enable Scatter for anything > 20 miles to ensure accuracy via Distance Filtering
        if radius > 20 and google_api_key:
            # [CRITICAL UPDATE] Explicit Coordinate Scatter
            # Text queries ("North of...") are often ignored by Google Maps if the viewport is sticky.
            # We must calculate precise Lat/Lon for each region and fire separate API calls.
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            # Get Center Coords
            start_lat, start_lon = get_lat_long(google_api_key, location_str)
            
            if start_lat and start_lon:
                mapped_results = []
                
                # Push out 70% of radius
                dist_miles = float(radius) * 0.7
                
                # Force "Local Detail" zoom (Level 11 ~ City View) regardless of total area size
                # This prevents Google from just showing "National Highlights"
                scatter_zoom = 11
                
                # Calculate Base 5 points: Center, N, S, E, W
                points = [
                    (start_lat, start_lon, "Center"),
                    get_new_coords(start_lat, start_lon, dist_miles, 0),   # North
                    get_new_coords(start_lat, start_lon, dist_miles, 180), # South
                    get_new_coords(start_lat, start_lon, dist_miles, 90),  # East
                    get_new_coords(start_lat, start_lon, dist_miles, 270)  # West
                ]
                
                # [Optimization] For MASSIVE areas (>100 miles), add diagonals to fill gaps
                if radius > 100:
                    st.toast(f"Massive Search: Scanning 9 sub-regions ({radius} miles)...", icon="🌌")
                    points.append(get_new_coords(start_lat, start_lon, dist_miles, 45))  # NE
                    points.append(get_new_coords(start_lat, start_lon, dist_miles, 135)) # SE
                    points.append(get_new_coords(start_lat, start_lon, dist_miles, 225)) # SW
                    points.append(get_new_coords(start_lat, start_lon, dist_miles, 315)) # NW
                else:
                    st.toast(f"Wide Search: Scanning 5 sub-regions ({radius} miles)...", icon="🛰️")
                
                # [PERFORMANCE] Use Threads to fire all 5-9 requests in parallel
                # This reduces wait time from ~45s to ~5s
                
                def fetch_region(pt):
                     lat, lon, label = pt
                     coords_str = f"{lat},{lon},{scatter_zoom}z"
                     try:
                         return client.google_maps_search(
                            [query], 
                            limit=limit,
                            drop_duplicates=False,
                            language='en',
                            coordinates=coords_str
                        )
                     except Exception as e:
                         print(f"Region {label} failed: {e}")
                         return []

                with ThreadPoolExecutor(max_workers=10) as executor:
                    futures = [executor.submit(fetch_region, pt) for pt in points]
                    
                    for future in as_completed(futures):
                        sub_res = future.result()
                        
                        # Process sub-results
                        if sub_res and len(sub_res) > 0:
                            # Handling structure
                            batch = sub_res[0] if isinstance(sub_res[0], list) else sub_res
                            
                            for item in batch:
                                name = item.get("name", "Unknown")
                                category = item.get("category", item.get("type", ""))
                                
                                # [FILTER] Blacklist Check
                                text_to_check = (name + " " + str(category)).lower()
                                if any(term in text_to_check for term in BLACKLIST_TERMS):
                                    continue

                                mapped_results.append({
                                    "Business Name": name,
                                    "Address": item.get("full_address", item.get("address", "")),
                                    "Rating": item.get("rating", 0.0),
                                    "Sector": category if category else "Search Result",
                                    "Website": item.get("site", ""),
                                    "Phone": item.get("phone", ""),
                                    "lat": item.get("latitude"),
                                    "lon": item.get("longitude"),
                                    "place_id": item.get("place_id", item.get("google_id")),
                                    "Source": "Outscraper SDK"
                                })

                # [FILTER] Remove results outside the actual radius (since scatter boxes are square/loose)
                filtered_results = []
                seen_places = set()

                for res in mapped_results:
                    # Deduplication Key: Place ID if available, else Name + Lat/Lon
                    dedup_key = res.get("place_id") or f"{res.get('Business Name')}_{res.get('lat')}_{res.get('lon')}"
                    
                    if dedup_key in seen_places:
                        continue
                    seen_places.add(dedup_key)

                    if res.get("lat") and res.get("lon"):
                        dist = haversine_distance(start_lat, start_lon, res["lat"], res["lon"])
                        if dist <= radius * 1.2: # Allow 20% margin for driving distance vs straight line
                             res["Distance"] = round(dist, 1)
                             filtered_results.append(res)
                
                return filtered_results, None
                
        # [FALLBACK] Standard single search if small radius OR no Google Key for maths
        search_query_list = []
        
        # If no coords available for logic above but strict radius needed:
        if radius > 50 and not google_api_key:
             # Try the text-based scatter (less reliable but better than nothing)
             offset = int(radius * 0.7)
             search_query_list.append(f"{query} near {location_str}")
             search_query_list.append(f"{query} {offset} miles North of {location_str}")
             search_query_list.append(f"{query} {offset} miles South of {location_str}")
             search_query_list.append(f"{query} {offset} miles East of {location_str}")
             search_query_list.append(f"{query} {offset} miles West of {location_str}")
             coords_param = None
        else:
             search_query_list.append(f"{query} near {location_str}")

        
        # 3. SDK Call (Standard Mode)
        results = client.google_maps_search(
            search_query_list,
            limit=limit,
            drop_duplicates=False,
            language='en',
            coordinates=coords_param
        )
        
        # Results is a list of lists (one per query)
        mapped_results = []
        
        if results:
            # Normalize structure: Ensure we have a list of lists
            batches = results
            if len(results) > 0 and isinstance(results[0], dict):
                batches = [results]
                
            for batch in batches:
                if isinstance(batch, list):
                    for item in batch:
                        name = item.get("name", "Unknown")
                        category = item.get("category", item.get("type", ""))
                        
                        # [FILTER] Blacklist Check
                        text_to_check = (name + " " + str(category)).lower()
                        if any(term in text_to_check for term in BLACKLIST_TERMS):
                            continue

                        mapped_results.append({
                            "Business Name": name,
                            "Address": item.get("full_address", item.get("address", "")),
                            "Rating": item.get("rating", 0.0),
                            "Sector": category if category else "Search Result",
                            "Website": item.get("site", ""),
                            "Phone": item.get("phone", ""),
                            "lat": item.get("latitude"),
                            "lon": item.get("longitude"),
                            "Source": "Outscraper SDK",
                            "Distance": round(haversine_distance(start_lat, start_lon, item.get("latitude"), item.get("longitude")), 1) if (start_lat and start_lon and item.get("latitude") and item.get("longitude")) else None
                        })
                
        return mapped_results, None

    except Exception as e:
        return {"error": f"Outscraper SDK Error: {str(e)}"}, None

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

