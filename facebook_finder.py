from playwright.sync_api import sync_playwright
import re
import math
import random
import time

def fb_search(company:str, town:str, max_p=5):
    """
    Searches Facebook Pages for founders/CEOs related to the company.
    Uses headless Chromium via Playwright.
    """
    results = []
    
    # Check if inputs are valid
    if not company or not town:
        return {"error": "Missing Company or Town"}

    q = f'CEO OR founder OR owner "{company}" {town}'
    # Use mobile site or basic site sometimes avoids heaviest JS, but blueprint used standard
    url = f"https://www.facebook.com/public/{q.replace(' ','-')}"
    # The blueprint used /pages/search/?q=. Let's stick to their blueprint exactly if possible,
    # but /pages/search often requires login. 
    # Blueprint URL: https://www.facebook.com/pages/search/?q=...
    # Let's try the blueprint URL first.
    url = f"https://www.facebook.com/pages/search/?q={q.replace(' ','%20')}"

    try:
        with sync_playwright() as p:
            # Launch options
            browser = p.chromium.launch(headless=True)
            
            # Context with random user agent to be safe
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
            page = context.new_page()
            
            print(f"DEBUG: Navigating to {url}")
            # Networkidle is risky on FB due to chat polling, using domcontentloaded or load
            try:
                page.goto(url, timeout=15000, wait_until="domcontentloaded")
            except Exception as e:
                print(f"DEBUG: Navigation timeout/error: {e}")
                
            # Blueprint Selector Logic
            # "a[href*="/"][role="link"]"
            # We might need to handle the "Consent" popup if running from EU IP.
            # Playwright might see the cookie banner.
            
            # Attempt to extract links
            # Blueprint JS: els => els.map(e => ({href:e.href, text:e.innerText}))
            links = page.eval_on_selector_all(
                'a[href*="/"][role="link"]', 
                'els => els.map(e => ({href:e.href, text:e.innerText}))'
            )
            
            # Filter logic from blueprint
            # re.match(r'.*/[^/]+/$', l['href'])
            profiles = []
            for l in links:
                # Basic filter for profile-like URLs
                if re.match(r'.*/[^/]+/?$', l['href']): 
                    # Verify it's not a generic link
                    if "facebook.com" in l['href'] and "pages" not in l['href'] and "search" not in l['href']:
                         profiles.append(l)
            
            profiles = profiles[:max_p]
            
            # Format results
            for p_link in profiles:
                # Clean name
                clean_name = p_link['text'].split("\n")[0].strip()
                if clean_name:
                    results.append({
                        "name": clean_name,
                        "role": "Potential Match", # We can't easily extract role from just link text without deeper DOM
                        "fb_url": p_link['href'],
                        "messaging_allowed": True # Assumption for now
                    })
            
            browser.close()
            
    except Exception as e:
        return {"error": str(e)}

    return results

def extract_contact_info(fb_url:str):
    """
    Visits the 'About' page to extract email/phone.
    """
    contact_info = {'email': None, 'phone': None}
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            target_url = fb_url.rstrip("/") + '/about_contact_and_basic_info'
            page.goto(target_url, timeout=10000, wait_until="domcontentloaded")
            
            html = page.content()
            browser.close()
            
            # Regex from blueprint
            email_match = re.search(r'([\w\.-]+@[\w\.-]+\.\w+)', html)
            phone_match = re.search(r'(\+44\s?7\d{3}\s?\d{6})', html)
            
            if email_match: contact_info['email'] = email_match.group(1)
            if phone_match: contact_info['phone'] = phone_match.group(1)
            
    except Exception as e:
        print(f"Extraction Error: {e}")
        
    return contact_info

# Mock function if Playwright fails (Graceful degradation)
def mock_fb_search(company, town):
    import time
    time.sleep(1.5)
    return [
        {
            "name": f"Founders of {company}", 
            "role": "Search Result",
            "fb_url": f"https://www.facebook.com/search/people/?q={company}%20{town}",
            "messaging_allowed": True
        }
    ]
