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
