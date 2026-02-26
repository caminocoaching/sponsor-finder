import requests
import re


def scrape_website_social_links(website_url):
    """
    Scrape a company's website to extract social media links from the HTML.
    Looks for LinkedIn, Facebook, Instagram, Twitter/X, YouTube, TikTok URLs.
    FREE — no API needed, just a simple HTTP GET.
    
    Returns dict: {"linkedin": "url", "facebook": "url", ...}
    """
    if not website_url:
        return {}
    
    # Ensure URL has protocol
    url = website_url.strip()
    if not url.startswith("http"):
        url = f"https://{url}"
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        if resp.status_code != 200:
            return {"error": f"Website returned {resp.status_code}"}
        
        html = resp.text
        
        # Extract all href values from the HTML
        hrefs = re.findall(r'href=["\']([^"\']+)["\']', html, re.IGNORECASE)
        
        social = {}
        
        for href in hrefs:
            href_lower = href.lower()
            
            # LinkedIn company page
            if "linkedin.com/company/" in href_lower and "linkedin" not in social:
                social["linkedin"] = href.split("?")[0]  # Strip tracking params
            elif "linkedin.com/in/" in href_lower and "linkedin_person" not in social:
                social["linkedin_person"] = href.split("?")[0]
            
            # Facebook
            if "facebook.com/" in href_lower and "linkedin" not in href_lower and "facebook" not in social:
                # Skip share/sharer links
                if "sharer" not in href_lower and "share.php" not in href_lower:
                    social["facebook"] = href.split("?")[0]
            
            # Instagram
            if "instagram.com/" in href_lower and "instagram" not in social:
                social["instagram"] = href.split("?")[0]
            
            # Twitter / X
            if ("twitter.com/" in href_lower or "x.com/" in href_lower) and "twitter" not in social:
                if "intent" not in href_lower and "share" not in href_lower:
                    social["twitter"] = href.split("?")[0]
            
            # YouTube
            if "youtube.com/" in href_lower and "youtube" not in social:
                social["youtube"] = href.split("?")[0]
            
            # TikTok
            if "tiktok.com/" in href_lower and "tiktok" not in social:
                social["tiktok"] = href.split("?")[0]
        
        return social
    
    except requests.exceptions.Timeout:
        return {"error": "Website took too long to respond"}
    except Exception as e:
        return {"error": str(e)}


def search_outscraper_contacts(outscraper_key, domain):
    """
    Use Outscraper Emails & Contacts API to find contact details for a domain.
    Returns emails, phones, social links, and site metadata.
    Costs ~$0.003 per lookup (pay-as-you-go, no monthly fee).
    """
    if not outscraper_key or not domain:
        return {"error": "Missing key or domain"}

    try:
        from outscraper import OutscraperClient
        client = OutscraperClient(api_key=outscraper_key)

        results = client.emails_and_contacts([domain])

        # Results come as a list of dicts, one per domain
        if not results or not isinstance(results, list) or len(results) == 0:
            return {"error": "No contact data found."}

        data = results[0] if isinstance(results[0], dict) else {}
        if not data:
            return {"error": "No contact data found."}

        # Extract emails
        emails = []
        for key in ["email_1", "email_2", "email_3"]:
            val = data.get(key, "")
            if val and val not in emails:
                emails.append(val)

        # Extract phones
        phones = []
        for key in ["phone_1", "phone_2", "phone_3"]:
            val = data.get(key, "")
            if val and val not in phones:
                phones.append(val)

        # Extract social links
        social = {}
        for key in ["facebook", "instagram", "twitter", "linkedin", "youtube"]:
            val = data.get(key, "")
            if val:
                social[key] = val

        # Site metadata
        site_title = data.get("title", "")
        site_description = data.get("description", "")

        return {
            "emails": emails,
            "phones": phones,
            "social": social,
            "linkedin": social.get("linkedin", ""),
            "site_title": site_title,
            "site_description": site_description,
        }

    except Exception as e:
        return {"error": str(e)}


def search_apollo_people(api_key, domain):
    """
    Two-step Apollo enrichment:
    Step 1: Search (FREE, no credits) — find decision-maker by domain
    Step 2: Enrich (1 credit) — get their email, phone, LinkedIn
    Returns decision-maker info + company firmographics.
    """
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "X-Api-Key": api_key
    }
    
    # --- STEP 1: SEARCH (free, no credits consumed) ---
    search_url = "https://api.apollo.io/api/v1/mixed_people/api_search"
    search_payload = {
        "q_organization_domains_list": [domain],
        "person_titles": ["Managing Director", "Founder", "Owner", "Chief Executive Officer", 
                          "CEO", "President", "Director", "General Manager", "Principal"],
        "person_seniorities": ["owner", "founder", "c_suite", "partner", "vp", "director"],
        "page": 1,
        "per_page": 5
    }
    
    try:
        response = requests.post(search_url, headers=headers, json=search_payload)
        
        if response.status_code != 200:
            return {"error": f"Search API Error ({response.status_code}): {response.text[:200]}"}
        
        data = response.json()
        people = data.get("people", [])
        
        # Fallback: if seniority filter returned 0, search without it
        # Small UK companies often don't have formal seniority tags
        if not people:
            fallback_payload = {
                "q_organization_domains_list": [domain],
                "page": 1,
                "per_page": 10
            }
            fallback_resp = requests.post(search_url, headers=headers, json=fallback_payload)
            if fallback_resp.status_code == 200:
                people = fallback_resp.json().get("people", [])
        
        if not people:
            return {"error": "No matching decision makers found."}
        
        # Sort people by title seniority (decision-makers first)
        def title_rank(person):
            title = (person.get("title") or "").lower()
            # Higher rank = more senior (we sort descending)
            if any(t in title for t in ["owner", "managing director", "ceo", "chief executive"]):
                return 100
            if any(t in title for t in ["founder", "co-founder"]):
                return 90
            if any(t in title for t in ["president", "principal"]):
                return 80
            if any(t in title for t in ["vice president", "vp", "chief"]):
                return 70
            if "director" in title:
                return 60
            if any(t in title for t in ["general manager", "head of"]):
                return 50
            if "manager" in title:
                return 40
            if "senior" in title:
                return 30
            # Low-value titles
            if any(t in title for t in ["intern", "student", "placement", "assistant", "driver", "operative"]):
                return 5
            return 20
        
        people = sorted(people, key=title_rank, reverse=True)
        
        # Grab the best match from search
        person = people[0]
        person_id = person.get("id", "")
        first_name = person.get("first_name", "")
        last_name = person.get("last_name", person.get("last_name_obfuscated", ""))
        title = person.get("title", "")
        
        # Extract company/org data from search result
        org = person.get("organization", {}) or {}
        
        result = {
            # Decision-maker data (from search — no email yet)
            "First Name": first_name,
            "Last Name": last_name,
            "Title": title,
            "LinkedIn": "",  # Not returned by search
            "Email": "",     # Not returned by search
            "Headline": person.get("headline", ""),
            # Company firmographic data
            "Company Name": org.get("name", ""),
            "Company LinkedIn": org.get("linkedin_url", ""),
            "Company Website": org.get("website_url", ""),
            "Employee Count": org.get("estimated_num_employees") or org.get("num_employees") or "",
            "Revenue": org.get("annual_revenue_printed", ""),
            "Revenue Raw": org.get("annual_revenue") or "",
            "Industry": org.get("industry", ""),
            "Company Phone": org.get("phone", ""),
            "Founded Year": org.get("founded_year", ""),
            "City": org.get("city", ""),
            "Country": org.get("country", ""),
            "Short Description": org.get("short_description", ""),
        }
        
        # Alternate contacts from search results
        if len(people) > 1:
            alternates = []
            for p in people[1:4]:
                alt_name = p.get("first_name", "")
                alt_last = p.get("last_name", p.get("last_name_obfuscated", ""))
                alternates.append({
                    "name": f"{alt_name} {alt_last}".strip(),
                    "title": p.get("title", ""),
                    "email": "",  # Will be enriched separately if needed
                    "linkedin": "",
                    "person_id": p.get("id", "")
                })
            result["Alternates"] = alternates
        
        # --- STEP 2: ENRICH (1 credit) — get email, phone, LinkedIn ---
        if person_id or (first_name and last_name):
            enrich_url = "https://api.apollo.io/v1/people/match"
            enrich_payload = {
                "api_key": api_key,
                "reveal_personal_emails": True,
            }
            
            # Use person_id if available, otherwise use name + domain
            if person_id:
                enrich_payload["id"] = person_id
            else:
                enrich_payload["first_name"] = first_name
                enrich_payload["last_name"] = last_name
                enrich_payload["organization_domain"] = domain
            
            try:
                enrich_response = requests.post(enrich_url, headers=headers, json=enrich_payload)
                
                if enrich_response.status_code == 200:
                    enrich_data = enrich_response.json()
                    enriched_person = enrich_data.get("person", {}) or {}
                    
                    # Update result with enriched data
                    if enriched_person.get("email"):
                        result["Email"] = enriched_person["email"]
                    if enriched_person.get("linkedin_url"):
                        result["LinkedIn"] = enriched_person["linkedin_url"]
                    if enriched_person.get("first_name"):
                        result["First Name"] = enriched_person["first_name"]
                    if enriched_person.get("last_name"):
                        result["Last Name"] = enriched_person["last_name"]
                    if enriched_person.get("title"):
                        result["Title"] = enriched_person["title"]
                    if enriched_person.get("headline"):
                        result["Headline"] = enriched_person["headline"]
                    
                    # Phone numbers
                    phone_numbers = enriched_person.get("phone_numbers", [])
                    if phone_numbers:
                        result["Direct Phone"] = phone_numbers[0].get("sanitized_number", "")
                    
                    # Organization data (enriched version may have more detail)
                    enrich_org = enriched_person.get("organization", {}) or {}
                    if enrich_org:
                        if enrich_org.get("name") and not result.get("Company Name"):
                            result["Company Name"] = enrich_org["name"]
                        if enrich_org.get("linkedin_url") and not result.get("Company LinkedIn"):
                            result["Company LinkedIn"] = enrich_org["linkedin_url"]
                        if enrich_org.get("estimated_num_employees") and not result.get("Employee Count"):
                            result["Employee Count"] = enrich_org["estimated_num_employees"]
                        if enrich_org.get("annual_revenue_printed") and not result.get("Revenue"):
                            result["Revenue"] = enrich_org["annual_revenue_printed"]
                        if enrich_org.get("industry") and not result.get("Industry"):
                            result["Industry"] = enrich_org["industry"]
                        if enrich_org.get("phone") and not result.get("Company Phone"):
                            result["Company Phone"] = enrich_org["phone"]
                        if enrich_org.get("founded_year") and not result.get("Founded Year"):
                            result["Founded Year"] = enrich_org["founded_year"]
                        if enrich_org.get("short_description") and not result.get("Short Description"):
                            result["Short Description"] = enrich_org["short_description"]
                else:
                    print(f"Apollo Enrich Error ({enrich_response.status_code}): {enrich_response.text[:200]}")
            except Exception as enrich_err:
                print(f"Apollo enrichment step failed: {enrich_err}")
        
        return result
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


def search_companies_house(api_key, business_name):
    """
    Search UK Companies House for a business and return its directors/PSCs.
    
    Completely FREE API — no credits, no cost.
    
    Returns:
        dict with keys:
        - company_name: Official registered name
        - company_number: Companies House number
        - company_status: active/dissolved
        - sic_codes: List of SIC industry codes
        - registered_address: Official address
        - directors: List of {name, role, appointed_on}
        - pscs: List of {name, kind} (persons with significant control = owners)
        - best_contact: The most senior person found (PSC first, then director)
    """
    if not api_key or not business_name:
        return {"error": "Missing API key or business name"}
    
    base_url = "https://api.company-information.service.gov.uk"
    
    # Auth: API key as username, no password
    auth = (api_key, "")
    
    try:
        # Step 1: Search for the company
        search_resp = requests.get(
            f"{base_url}/search/companies",
            params={"q": business_name, "items_per_page": 5},
            auth=auth,
            timeout=10
        )
        
        if search_resp.status_code == 401:
            return {"error": "Invalid Companies House API key"}
        if search_resp.status_code != 200:
            return {"error": f"Search failed: {search_resp.status_code}"}
        
        search_data = search_resp.json()
        items = search_data.get("items", [])
        
        if not items:
            return {"error": f"No company found for '{business_name}'"}
        
        # Find the best match — prefer active companies
        company = None
        for item in items:
            if item.get("company_status") == "active":
                company = item
                break
        if not company:
            company = items[0]
        
        company_number = company.get("company_number", "")
        company_name = company.get("title", "")
        company_status = company.get("company_status", "")
        
        result = {
            "company_name": company_name,
            "company_number": company_number,
            "company_status": company_status,
            "sic_codes": [],
            "registered_address": "",
            "directors": [],
            "pscs": [],
            "best_contact": ""
        }
        
        # Step 2: Get company profile (SIC codes, address)
        try:
            profile_resp = requests.get(
                f"{base_url}/company/{company_number}",
                auth=auth, timeout=10
            )
            if profile_resp.status_code == 200:
                profile = profile_resp.json()
                result["sic_codes"] = profile.get("sic_codes", [])
                
                addr = profile.get("registered_office_address", {})
                addr_parts = [
                    addr.get("address_line_1", ""),
                    addr.get("address_line_2", ""),
                    addr.get("locality", ""),
                    addr.get("postal_code", "")
                ]
                result["registered_address"] = ", ".join([p for p in addr_parts if p])
        except:
            pass
        
        # Step 3: Get officers (directors, secretaries)
        try:
            officers_resp = requests.get(
                f"{base_url}/company/{company_number}/officers",
                auth=auth, timeout=10
            )
            if officers_resp.status_code == 200:
                officers = officers_resp.json().get("items", [])
                for officer in officers:
                    # Only active officers (not resigned)
                    if officer.get("resigned_on"):
                        continue
                    
                    name = officer.get("name", "")
                    role = officer.get("officer_role", "")
                    appointed = officer.get("appointed_on", "")
                    
                    # Companies House format: "SMITH, John David" → "John Smith"
                    clean_name = _clean_ch_name(name)
                    
                    result["directors"].append({
                        "name": clean_name,
                        "raw_name": name,
                        "role": role,
                        "appointed_on": appointed
                    })
        except:
            pass
        
        # Step 4: Get Persons with Significant Control (actual owners)
        try:
            psc_resp = requests.get(
                f"{base_url}/company/{company_number}/persons-with-significant-control",
                auth=auth, timeout=10
            )
            if psc_resp.status_code == 200:
                pscs = psc_resp.json().get("items", [])
                for psc in pscs:
                    name = psc.get("name", "")
                    kind = psc.get("kind", "")
                    natures = psc.get("natures_of_control", [])
                    
                    clean_name = _clean_ch_name(name)
                    
                    result["pscs"].append({
                        "name": clean_name,
                        "raw_name": name,
                        "kind": kind,
                        "control": natures
                    })
        except:
            pass
        
        # Determine best contact: PSCs first (owners), then directors
        if result["pscs"]:
            result["best_contact"] = result["pscs"][0]["name"]
        elif result["directors"]:
            # Prefer directors over secretaries
            directors_only = [d for d in result["directors"] if "director" in d.get("role", "").lower()]
            if directors_only:
                result["best_contact"] = directors_only[0]["name"]
            else:
                result["best_contact"] = result["directors"][0]["name"]
        
        return result
        
    except requests.exceptions.Timeout:
        return {"error": "Companies House API timeout"}
    except Exception as e:
        return {"error": f"Companies House error: {str(e)}"}


def _clean_ch_name(raw_name):
    """
    Clean Companies House name format.
    'SMITH, John David' → 'John Smith'
    'John David SMITH' → 'John Smith'
    """
    if not raw_name:
        return ""
    
    # Handle "SURNAME, Forename" format
    if "," in raw_name:
        parts = raw_name.split(",", 1)
        surname = parts[0].strip().title()
        forenames = parts[1].strip().split()
        first_name = forenames[0].title() if forenames else ""
        return f"{first_name} {surname}".strip()
    
    # Handle "Forename SURNAME" format (all-caps surname)
    parts = raw_name.split()
    if len(parts) >= 2:
        # Find the all-caps part (surname)
        caps_parts = [p for p in parts if p.isupper() and len(p) > 1]
        if caps_parts:
            surname = caps_parts[-1].title()
            first_name = parts[0].title()
            return f"{first_name} {surname}"
    
    return raw_name.title()
