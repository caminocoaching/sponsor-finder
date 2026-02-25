import requests
import math
import time
import random
import json
import urllib.parse
import streamlit as st # Added for debug feedback
from outscraper import OutscraperClient # [NEW] Use official SDK
from cache_manager import get_cached_search, set_cached_search # [NEW] Caching

def search_outscraper(api_key, query, location_str, radius=50, limit=100, skip=0, google_api_key=None):
    """
    HIGH-PRECISION SEARCH (V3 Strict Mode)
    Optimized for cost efficiency and relevance.
    """
    
    # --- 0. CHECK CACHE FIRST ---
    # We check cache before even geocoding to save time if exact query repeated
    cached_res = get_cached_search(query, location_str, radius, limit, skip)
    if cached_res is not None:
        # st.toast(f"Loaded '{query}' from Cache (valid 7 days)", icon="💾") # Silenced per request
        return cached_res, None

    if not google_api_key:
         st.error("Google API Key is required for strict radius search (to determine center coordinates).")
         return [], None

    # --- 1. Get Center Coordinates (Anchor) & Detect Region ---
    start_lat, start_lon, detected_region = get_lat_long(google_api_key, location_str)
    
    if not start_lat or not start_lon:
         st.error(f"Could not find coordinates for: {location_str}")
         return [], None
         
    # 2. Strict Search Parameters
    radius_meters = int(radius * 1609.34)
    
    # Determine Region Code (Outscraper requires ISO 2 codes)
    region_code = detected_region or "US" # Use Google's detection or default to US
    loc_upper = (location_str or "").upper()
    
    # Manual Override Mapping (Highest Priority)
    if "UK" in loc_upper or "UNITED KINGDOM" in loc_upper or "ENGLAND" in loc_upper or "SCOTLAND" in loc_upper or "WALES" in loc_upper or region_code == "GB":
        region_code = "GB"
    elif "USA" in loc_upper or "UNITED STATES" in loc_upper:
        region_code = "US"
    elif "AUSTRALIA" in loc_upper:
        region_code = "AU"
    elif "CANADA" in loc_upper:
        region_code = "CA"
    elif "NEW ZEALAND" in loc_upper or " NZ" in loc_upper: # Space before NZ to avoid matching random words
        region_code = "NZ"
    elif "HUNGARY" in loc_upper:
        region_code = "HU"
    elif "IRELAND" in loc_upper:
        region_code = "IE"
    elif "GERMANY" in loc_upper or "DEUTSCHLAND" in loc_upper:
        region_code = "DE"
    elif "FRANCE" in loc_upper:
        region_code = "FR"
    elif "SPAIN" in loc_upper:
        region_code = "ES"
    elif "ITALY" in loc_upper:
        region_code = "IT"
    elif "NETHERLANDS" in loc_upper or "HOLLAND" in loc_upper:
        region_code = "NL"
    elif "BELGIUM" in loc_upper:
        region_code = "BE"
    elif "AUSTRIA" in loc_upper:
        region_code = "AT"
    elif "SWEDEN" in loc_upper:
        region_code = "SE"
    elif "SWITZERLAND" in loc_upper:
        region_code = "CH"
    elif "POLAND" in loc_upper:
        region_code = "PL"
    elif "SOUTH AFRICA" in loc_upper:
        region_code = "ZA"

    st.toast(f"Strict Search: '{query}' within {radius} miles...", icon="🎯")
    
    try:
        from outscraper import OutscraperClient
        client = OutscraperClient(api_key=api_key)
        
        # V3 Direct Parameters for Strict Radius
        # --- STRATEGY 1: STRICT DROPOFF (Preferred) ---
        params = {
            "query": query,
            "coordinates": f"{start_lat},{start_lon}",
            "dropoff": radius_meters,
            "limit": limit,
            "skip": skip,
            "language": "en",
            "region": region_code,
            "async": "false",
            "domains_service": "true"  # Enrichment: scrapes websites for emails & social media links
        }
        
        response = client._request('GET', '/maps/search-v3', params=params)
        # Handle Response (Client usually returns JSON or Response object)
        # SDK _request UNWRAPS the 'data' key automatically! 
        # So 'data' here is likely [[...]] NOT {"data": [[...]]}
        data = response.json() if hasattr(response, 'json') else response
        
        raw_businesses = []
        
        if isinstance(data, list):
             # SDK behavior: returns the content of 'data'
             if len(data) > 0 and isinstance(data[0], list):
                 raw_businesses = data[0]
             elif len(data) > 0 and isinstance(data[0], dict):
                 # Single result wrapped in list
                 raw_businesses = data
        elif isinstance(data, dict) and "data" in data:
             # Raw API behavior fallback
             if len(data["data"]) > 0:
                 raw_businesses = data["data"][0]
        
        # --- STRATEGY 2: PROXIMITY FALLBACK (If strict returned 0) ---
        if not raw_businesses:
            st.toast("Strict filter empty. Trying proximity search...", icon="📡")
            # Remove dropoff, rely on coordinates + manual filter
            params_fallback = params.copy()
            del params_fallback["dropoff"]
            # Limit fallback to avoid massive scraping
            params_fallback["limit"] = min(limit, 60) 
            # skip is already in params copy, but explicitly ensuring it's kept or adjusting if needed
            params_fallback["skip"] = skip
            
            response = client._request('GET', '/maps/search-v3', params=params_fallback)
            data = response.json() if hasattr(response, 'json') else response
            
            if isinstance(data, list):
                 if len(data) > 0 and isinstance(data[0], list):
                     raw_businesses = data[0]
                 elif len(data) > 0 and isinstance(data[0], dict):
                     raw_businesses = data
            elif isinstance(data, dict) and "data" in data:
                 if len(data["data"]) > 0:
                     raw_businesses = data["data"][0]

        mapped_results = []
        skipped_dist = 0
        skipped_chain = 0
        
        # Known national/international chains to filter out
        CHAIN_EXCLUSIONS = [
            "DHL", "FEDEX", "UPS", "ROYAL MAIL", "HERMES", "TNT", "TESCO",
            "SAINSBURY", "ASDA", "ALDI", "LIDL", "MORRISONS", "WAITROSE",
            "MCDONALD", "BURGER KING", "KFC", "SUBWAY", "COSTA COFFEE",
            "STARBUCKS", "GREGGS", "DOMINO", "PIZZA HUT", "PREMIER INN",
            "TRAVELODGE", "HILTON", "MARRIOTT", "HSBC", "BARCLAYS",
            "LLOYDS", "NATWEST", "SANTANDER", "NATIONWIDE", "POST OFFICE",
            "AUTOTRADER", "HALFORDS", "KWIK FIT", "VODAFONE", "O2", "EE",
            "THREE", "BT", "SKY", "VIRGIN MEDIA", "AMAZON"
        ]
        
        for item in raw_businesses:
            # Skip None/non-dict items from API response
            if not item or not isinstance(item, dict):
                continue
                
            name = item.get("name")
            if not name:
                # Fallback: try displayName structure (Google Places format)
                display_name = item.get("displayName")
                if isinstance(display_name, dict):
                    name = display_name.get("text")
            if not name:
                name = "Unknown"
            if not name or name == "Unknown":
                continue
            
            # Post-Verification Filter (CRITICAL)
            lat = item.get("latitude")
            lon = item.get("longitude")
            dist_val = 0.0
            
            if lat and lon:
                dist_val = round(haversine_distance(start_lat, start_lon, lat, lon), 1)
                
            # ABSOLUTE FILTER: If result is outside radius, discard it.
            if dist_val > radius:
                skipped_dist += 1
                continue
                
            # [UPGRADED] Cleaning Filters
            cat_upper = (item.get("category") or "").upper()
            name_upper = (name or "").upper()
            
            # Junk category filter
            excluded_terms = ["TAXI", "AIRPORT SHUTTLE", "AMBULANCE", "CHAUFFEUR", 
                            "CAB ", "MINICAB", "UBER", "CHURCH", "CEMETERY",
                            "GOVERNMENT OFFICE", "PUBLIC SCHOOL"]
            if any(term in cat_upper for term in excluded_terms) or any(term in name_upper for term in excluded_terms):
                continue
            
            # Chain/National filter — skip large corporations with no local decision-maker
            is_chain = any(chain in name_upper for chain in CHAIN_EXCLUSIONS)
            if is_chain:
                skipped_chain += 1
                continue

            # --- EXTRACT ENRICHED DATA FROM OUTSCRAPER ---
            reviews_count = item.get("reviews", item.get("reviews_count", 0))
            try:
                reviews_count = int(reviews_count) if reviews_count else 0
            except:
                reviews_count = 0
            
            website = item.get("site", "")
            phone = item.get("phone", "")
            description = item.get("description", item.get("about", ""))
            owner = item.get("owner_title", item.get("owner", ""))
            
            # Social media links (enriched via domains_service)
            social_links = {}
            for social_key in ["facebook", "instagram", "twitter", "linkedin", "youtube"]:
                val = item.get(social_key, "")
                if val:
                    social_links[social_key] = val

            # Email addresses (enriched via domains_service)
            emails = []
            for email_key in ["email_1", "email_2", "email_3", "email"]:
                val = item.get(email_key, "")
                if val and val not in emails:
                    emails.append(val)
            
            # --- COMPANY SIZE ESTIMATION (from review count) ---
            if reviews_count > 500:
                size_estimate = "Large"
            elif reviews_count > 100:
                size_estimate = "Medium"
            elif reviews_count > 20:
                size_estimate = "Small"
            else:
                size_estimate = "Micro/Local"
            
            # --- LEAD QUALITY SCORE (1-6 stars) ---
            quality_score = 0
            if website:
                quality_score += 1  # Has a website
            if social_links:
                quality_score += 1  # Has social media presence
            if emails:
                quality_score += 1  # Has contact email
            if dist_val <= 25:
                quality_score += 1  # Very local (within 25 miles)
            if 5 <= reviews_count <= 500:
                quality_score += 1  # Right size (not too small, not a chain)
            if item.get("rating", 0) >= 4.0:
                quality_score += 1  # Well-rated business
            
            mapped_results.append({
                "Business Name": name,
                "Address": item.get("full_address", item.get("address", "")),
                "Rating": item.get("rating", 0.0),
                "Sector": item.get("category", item.get("type", "Search Result")),
                "Website": website,
                "Phone": phone,
                "lat": lat,
                "lon": lon,
                "place_id": item.get("place_id", item.get("google_id")),
                "Source": "Outscraper V3",
                "Distance": dist_val,
                # --- NEW ENRICHED FIELDS ---
                "Reviews": reviews_count,
                "Size": size_estimate,
                "Description": description or "",
                "Owner": owner or "",
                "Social": social_links,
                "Email": emails[0] if emails else "",
                "Emails": emails,
                "Quality": quality_score,
                "Is Chain": False
            })
            
        # Sort by Quality (highest first), then Distance (closest first)
        mapped_results.sort(key=lambda x: (-x.get("Quality", 0), x.get("Distance", 999.0)))
            
        if skipped_dist > 0:
            print(f"Skipped {skipped_dist} results outside {radius} mile radius.")
        if skipped_chain > 0:
            print(f"Filtered out {skipped_chain} national/international chain results.")
            
        # --- CACHE SAVE ---
        set_cached_search(query, location_str, radius, limit, skip, mapped_results)
            
        return mapped_results, None

    except Exception as e:
        import traceback
        print(f"Outscraper Search Error: {traceback.format_exc()}")
        return {"error": f"Search Failed: {str(e)}"}, None

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
    Returns (lat, lon, country_code).
    """
    # [OPTIMIZATION] Known locations cache to redundant API calls
    if "Middleton Cheney" in location_name:
         return 52.073, -1.274, "GB"

    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.location,places.formattedAddress"
    }
    
    # [ROBUSTNESS] Fallback loop for specific addresses
    # If "Specific House, Street, Town, UK" fails, try "Street, Town, UK", then "Town, UK"
    parts = [p.strip() for p in location_name.split(",") if p.strip()]
    
    for i in range(len(parts)):
        current_query = ", ".join(parts[i:])
        payload = {"textQuery": current_query}
        
        try:
            resp = requests.post(url, json=payload, headers=headers)
            data = resp.json()
            if "places" in data and len(data["places"]) > 0:
                place = data["places"][0]
                loc = place["location"]
                addr = (place.get("formattedAddress") or "").upper()
                
                # Detect country code from formatted address
                country_code = "US"
                if "UK" in addr or "UNITED KINGDOM" in addr: country_code = "GB"
                elif "AUSTRALIA" in addr: country_code = "AU"
                elif "CANADA" in addr: country_code = "CA"
                elif "NEW ZEALAND" in addr: country_code = "NZ"
                elif "HUNGARY" in addr: country_code = "HU"
                elif "IRELAND" in addr: country_code = "IE"
                
                return loc["latitude"], loc["longitude"], country_code
        except:
            continue # Try next broader part
            
    return None, None, None

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
    start_lat, start_lon, _ = get_lat_long(api_key, location_ctx)

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

