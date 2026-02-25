import requests

def search_apollo_people(api_key, domain):
    """
    Search Apollo for C-Suite, Founder, or Director level people for a specific domain.
    """
    url = "https://api.apollo.io/v1/mixed_people/search"
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache"
    }
    
    # We want to find top decision makers: Owner, Founder, CEO, Managing Director
    payload = {
        "api_key": api_key,
        "q_organization_domains": domain,
        "person_titles": ["Managing Director", "Founder", "Owner", "Chief Executive Officer", "CEO", "President", "Director"],
        "page": 1,
        "per_page": 5 # We only need the top match
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            people = data.get("people", [])
            
            if not people:
                return {"error": "No matching decision makers found."}
                
            # Grab the best match
            person = people[0]
            
            return {
                "First Name": person.get("first_name", ""),
                "Last Name": person.get("last_name", ""),
                "Title": person.get("title", ""),
                "LinkedIn": person.get("linkedin_url", ""),
                "Email": person.get("email", ""),
                "Headline": person.get("headline", "")
            }
        else:
            return {"error": f"API Error: {response.text}"}
    except Exception as e:
        return {"error": str(e)}

def find_linkedin_company_page(outscraper_key, business_name, location_hint=""):
    """
    Uses Outscraper Google Search to find a LinkedIn company page for a business.
    Returns the LinkedIn URL or empty string if not found.
    Costs ~1 Outscraper credit per lookup.
    """
    if not outscraper_key or not business_name:
        return ""

    try:
        from outscraper import OutscraperClient
        client = OutscraperClient(api_key=outscraper_key)

        # Search Google for the LinkedIn company page
        query = f'site:linkedin.com/company "{business_name}"'
        if location_hint:
            # Extract just the town/city from address for disambiguation
            parts = [p.strip() for p in location_hint.split(",") if p.strip()]
            # Use 2nd or 3rd part (usually town) — skip street number
            town = parts[1] if len(parts) > 1 else parts[0]
            query += f" {town}"

        response = client._request('GET', '/google-search-v3', params={
            "query": query,
            "pages_per_query": 1
        })
        data = response.json() if hasattr(response, 'json') else response

        # Parse results — Outscraper returns [[{organic results}]]
        results = []
        if isinstance(data, list) and len(data) > 0:
            first = data[0]
            if isinstance(first, dict):
                results = first.get("organic_results", [])
            elif isinstance(first, list) and len(first) > 0 and isinstance(first[0], dict):
                results = first[0].get("organic_results", [])

        # Find best LinkedIn company match
        name_lower = business_name.lower()
        for item in results:
            link = item.get("link", "")
            title = (item.get("title") or "").lower()

            if "linkedin.com/company/" in link.lower():
                # Relevance check: business name words should appear in title
                name_words = [w for w in name_lower.split() if len(w) > 2]
                if name_words:
                    matches = sum(1 for w in name_words if w in title)
                    if matches >= len(name_words) * 0.4:  # At least 40% of words match
                        return link
                else:
                    return link

        # Fallback: return first linkedin company URL if any
        for item in results:
            link = item.get("link", "")
            if "linkedin.com/company/" in link.lower():
                return link

        return ""
    except Exception:
        return ""


def extract_domain(url):
    """Extract domain from website URL."""
    if not url:
        return ""
    
    # Simple parsing to extract just the domain
    domain = url.lower()
    if "://" in domain:
        domain = domain.split("://")[1]
    domain = domain.split("/")[0]
    domain = domain.replace("www.", "")
    return domain
