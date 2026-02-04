
import diskcache as dc
import os

# Initialize DiskCache
# Stores cache in a .cache directory
cache = dc.Cache(".cache")

def get_cached_search(query, location, radius, limit=100, skip=0):
    """
    Retrieve cached search results if available.
    Key is composed of query, location, radius, limit, and skip.
    """
    # Normalize inputs for consistent key generation
    norm_query = query.lower().strip()
    norm_loc = location.lower().strip()
    key = f"search_v3:{norm_query}:{norm_loc}:{radius}:{limit}:{skip}"
    
    result = cache.get(key)
    if result:
        return result
    return None

def set_cached_search(query, location, radius, limit, skip, data, expire=604800):
    """
    Cache search results for 7 days (604800 seconds).
    """
    norm_query = query.lower().strip()
    norm_loc = location.lower().strip()
    key = f"search_v3:{norm_query}:{norm_loc}:{radius}:{limit}:{skip}"
    
    cache.set(key, data, expire=expire)

def clear_cache():
    cache.clear()
