import requests
import math
import time
import random
import streamlit as st # Added for debug feedback

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

def search_google_places(api_key, query, location, radius_miles):
    """
    Real Google Places Search (New API v1).
    Endpoint: https://places.googleapis.com/v1/places:searchText
    """
    url = "https://places.googleapis.com/v1/places:searchText"
    
    # Headers required for New API
    # Added places.websiteUri as per previous plan
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.rating,places.location,places.businessStatus,places.websiteUri"
    }
    
    # 1. Geocode the Center Point
    lat, lon = get_lat_long(api_key, location)
    
    payload = {
        "textQuery": query 
    }

    # 2. Decide Strategy based on Radius
    # Google Places API "circle" bias maxes out at 50,000 meters (~31 miles).
    # If radius is larger, we must rely on text-based "near {location}" search logic.
    radius_meters = radius_miles * 1609.34
    
    if lat is not None and lon is not None and radius_meters <= 50000:
        # Use precise Circular Bias
        payload["locationBias"] = {
            "circle": {
                "center": {
                    "latitude": lat,
                    "longitude": lon
                },
                "radius": radius_meters
            }
        }
    else:
        # Fallback if geocoding fails OR radius is too large for circle bias.
        # We rely on the natural language engine (e.g. "Engineering near London")
        payload["textQuery"] = f"{query} near {location}"
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()
        
        # Check for error object in response
        if "error" in data:
            return {"error": data["error"].get("message", "Unknown API Error")}
            
        results = []
        
        def process_places(places_list):
            for item in places_list:
                # Check business status
                if item.get("businessStatus") in ["CLOSED_TEMPORARILY", "CLOSED_PERMANENTLY"]:
                    continue

                loc = item.get("location", {})
                r_lat = loc.get("latitude")
                r_lon = loc.get("longitude")
                
                # Distance Filter
                if lat and lon and r_lat and r_lon:
                    dist = haversine_distance(lat, lon, r_lat, r_lon)
                    if dist > radius_miles:
                        continue # Skip if outside radius

                name = item.get("displayName", {}).get("text", "Unknown Business")
                website = item.get("websiteUri", "") 
                
                results.append({
                    "Business Name": name,
                    "Address": item.get("formattedAddress", "N/A"),
                    "Rating": item.get("rating", 0.0),
                    "Sector": query,
                    "Website": website,
                    "lat": r_lat,
                    "lon": r_lon
                })

        # Process first page
        process_places(data.get("places", []))
        
        # Pagination Logic (Fetch up to ~100 results to balance cost/coverage)
        MAX_PAGES = 4 
        next_token = data.get("nextPageToken")
        
        current_page = 0
        while next_token and current_page < MAX_PAGES:
            time.sleep(2) # Be nice to API / avoid rate limits
            
            # Prepare next page payload
            # NOTE: v1 searchText pagination typically just requires the same payload + pageToken
            # However, some docs suggest strict consistency. We reuse payload.
            next_payload = payload.copy()
            next_payload["pageToken"] = next_token
            # Remove bias/location restrictions if they conflict (usually fine to keep)
            
            try:
                resp_next = requests.post(url, json=next_payload, headers=headers)
                data_next = resp_next.json()
                
                places = data_next.get("places", [])
                st.toast(f"Fetching Page {current_page + 2}... ({len(places)} results)") # Feedback
                process_places(places)
                
                next_token = data_next.get("nextPageToken")
                current_page += 1
            except Exception as e:
                print(f"Pagination Error: {e}")
                st.error(f"Search Page {current_page+2} failed: {e}")
                break
        
        # DEBUG:
        st.info(f"Search Complete: Processed {current_page+1} pages. Filtered {len(results)} matches.")
             
        return results
        
    except Exception as e:
        return {"error": str(e)}

