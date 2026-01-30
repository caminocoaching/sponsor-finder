import streamlit as st
import pandas as pd
import time
import random
from datetime import datetime, timedelta
import urllib.parse
import db_manager as db
import json
from search_service import mock_search_places, search_google_places
from sheets_manager import sheet_manager
from airtable_manager import airtable_manager
from streamlit_calendar import calendar

# --- CONFIGURATION ---
# Last System Update: Force Reload
st.set_page_config(page_title="Sponsor Finder V2.5", page_icon="🏍️", layout="wide")

# Initialize DB
db.init_db()

# --- DATA & CONSTANTS ---
SECTORS = [
    "in your industry sector",
    "Engineering & manufacturing",
    "Transport & haulage",
    "Motorcycle dealers",
    "Motorcycle parts & accessories",
    "Accident management & vehicle services",
    "Building supplies",
    "Food & beverage brands",
    "Tech & telecoms (optional)",
    "Insurance",
    "Financial services",
    "App developers",
    "Logistics",
    "Printers",
    "High Net Worth companies",
    "Other (type your own)"
]

SECTOR_HOOKS = {
    "Construction": "building a legacy and solid foundations",
    "Engineering": "precision, performance, and technical excellence",
    "Transport": "logistics, speed, and moving forward",
    "Motorcycle": "passion for the sport and the machine",
    "Accident": "safety, recovery, and getting back on track",
    "Food": "fueling performance and great taste",
    "Financial": "calculated risk and high rewards",
    "Logistics": "delivering results on time, every time",
    "Insurance": "protection and peace of mind at high speed",
    "Tech": "innovation and data-driven performance",
    "Other": "excellence and high performance"
}

DISCOVERY_QUESTIONS = [
    "1. Have you been involved in sponsorship before and how did it go for you?",
    "2. What would be the ideal outcome for you, from us working together this season?",
    "3. What would you consider to the most important elements of a sponsorship package?",
    "4. Do you feel that your staff and team could benefit from our partnership this season?",
    "5. Do you feel your customers could benefit from our partnership this season?",
    "6. I think it sounds like we have a fit here, would you agree? Is this a good time for me to put together a draft proposal for your feedback?"
]

OBJECTION_SCRIPTS = {
    "send email": """That’s absolutely fine, I can certainly send over some details. 

However, sponsorship is really about fitting your specific needs, not a one-size-fits-all package. 

Would you be open to a purely fact-finding 10-minute chat first? If there's no fit, I won't chase you properly.""",
    
    "budget": """I completely understand. Most of my partners didn't have a "racing budget" initially either.

We actually work with marketing, hospitality, or even staff incentive budgets.

I'm not asking for a commitment right now, just a brief conversation to see if our audience overlaps with yours. Is that fair?""",
    
    "not interested": """I appreciate your candor. 

Out of curiosity, is it motorsport specifically that doesn't fit, or is it that you have enough local brand visibility already?

Many [Sector] companies find we offer a unique way to stand out compared to standard advertising.""",
    
    "call me later": """Sure thing. To make sure I don't catch you at a bad time again, when is typically the quietest moment in your week? Tuesday mornings?""",
    
    "how much": """That’s great to hear! It really depends on what you want to achieve, could we arrange a quick call to see what your company needs?"""
}

def handle_objection(reply_text):
    reply_lower = reply_text.lower()
    
    # 1. Check for Positive Interest (Price/Cost questions)
    if "how much" in reply_lower or "price" in reply_lower or ("cost" in reply_lower and "expensive" not in reply_lower):
        return "how much"
        
    # 2. Standard Objections
    elif "email" in reply_lower or "send info" in reply_lower:
        return "send email"
    elif "budget" in reply_lower or "expensive" in reply_lower or "cost" in reply_lower:
        return "budget"
    elif "not interested" in reply_lower or "no thanks" in reply_lower:
        return "not interested"
    elif "call" in reply_lower or "busy" in reply_lower or "later" in reply_lower:
        return "call me later"
    else:
        return "fallback"

@st.dialog("Are You Sure?")
def delete_confirmation_dialog(lid, business_name):
    st.write(f"You are about to delete **{business_name}**.")
    st.warning("This action cannot be undone.")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Yes, Delete Forever", type="primary"):
            db.delete_lead(lid)
            st.rerun()
            
    with col2:
        if st.button("Cancel"):
            st.rerun()

TEMPLATES = {
    "Email: Cold Opener": """Good morning [Contact Name],

I wanted to introduce myself. My name is [Rider Name] and I am based in [Town] close to your head office.

I am racing this season in the [Championship Name] and I wondered if you have ever considered motorsport to promote your brand?

There are a number of companies in the [Sector] sector that have successfully promoted themselves in motorsport over the past season (usually focusing on [Sector Hook]), and I want to offer you an opportunity to get involved.

Is this something you have considered or would be open to discussing?

I look forward to hearing from you soon,

Best regards,
[Rider Name]""",

    "LI Msg 1: Connect": """Hi [Contact Name],

I hope you’re doing well! Thank you for connecting with me here—it’s great to expand my network with forward-thinking professionals like yourself.

I’m reaching out as I’m passionate about partnering with businesses that see the unique value of promoting their brand through motorsport—a fast-paced, technologically advanced sport that embodies precision, performance, and innovation.

I’m currently competing in [Championship Name], and I believe we could be a fantastic fit because [Sector Hook] companies often need to stand out locally.

I’d love the opportunity to explore how we can work together to help [Business Name] stand out from the competition in a way that’s both impactful and exciting. Could we arrange a time to speak and discuss the possibilities?

Looking forward to hearing your thoughts!

Warm regards,
[Rider Name]""",

    "LI Msg 2: Reminder (Day 2)": """Hi [Contact Name],

I just wanted to follow up and learn more about [Business Name]. Have you worked with sponsorships before, or is this something you’ve considered exploring?

Motorsport partnerships offer unique benefits, from brand visibility at [Audience Size] events to tailored engagement opportunities. I’d love to hear if this could align with your goals.

Looking forward to your thoughts!

Best regards,
[Rider Name]""",

    "LI Msg 3: Opportunities (Day 7)": """Good morning [Contact Name],

I hope you’re doing well!

I wanted to update you on my plans for the [Current Year] season. This year, I’m focusing solely on [Championship Name], allowing me to concentrate fully on achieving [Season Goal].

Last season in [Previous Champ] was a fantastic step forward, with highlights like [Achievements]. This year, I’ve secured exciting opportunities for my business partners, including:

1. Sales Team Incentives – Competition for a VIP race weekend experience.
2. Meet & Greet – Bringing the race bike to your office for a motivational session with your team.
3. Exclusive Trackside Advertising – High-visibility placements at events with [Audience Size] attendees, streamed on YouTube or televised to [TV Viewers] viewers.

If these align with your goals, I’d love to discuss further. Let me know if you’d like more details!

Best regards,
[Rider Name]""",

    "LI Msg 4: Value (Day 14)": """Hi [Contact Name],

I hope this message finds you well!

I’ve been thinking about how [Business Name] could benefit from motorsport sponsorship. It’s a unique way to connect with audiences and enhance your brand, offering:

• Direct Engagement – Through events and digital platforms.
• Brand Alignment – With high-performance and innovation.
• Memorable Experiences – For your team or clients.

Have sponsorships been part of your strategy before? If not, I’d be happy to share insights on how this could work for you.

Looking forward to hearing your thoughts when you have a moment!

Best regards,
[Rider Name]""",

    "LI Msg 5: Unique Offer (Day 21)": """Hi [Contact Name],

As I finalise preparations for the [Championship Name] season, I wanted to let you know about an exciting opportunity to get involved.

I’ve recently launched my [Team Name], where members can join the journey and enjoy exclusive benefits:

• £35 Membership: Includes race weekend reports, hand-picked high-res photos, team stickers, and discounts on clothing.
• £350 VIP Membership: Add your signature to my race helmet, plus a chance to win it at the end of the season!

If this sounds interesting, or if you’d like to discuss tailored sponsorship options, let me know. I’d love to include [Business Name] in this season’s journey.

Best regards,
[Rider Name]""",

    "LI Msg 6: Final Nudge (Day 28)": """Hi [Contact Name],

I know how busy things can get, so I wanted to check in one last time. If sponsorship or collaboration isn’t the right fit, no problem at all—but I’d love to hear your thoughts on what works best for [Business Name] in partnerships.

If motorsport isn’t on your radar yet, I’d be happy to share why it’s a growing opportunity for forward-thinking businesses.

Even a quick “yes” or “not for us” would help me plan. Thanks so much for considering, and I hope to hear from you soon!

Best regards,
[Rider Name]""",

    "Initial Contact": """(See Email: Cold Opener above)""",
    "Follow Up": """(See LI Msg 2 or others)""",
    "Proposal": """Hi [Contact Name],

Great speaking with you earlier. Based on what you shared about your focus on [Goal Answer], I've put together this proposal.

**Strategy for [Business Name]**:
- Target Audience: [Audience Answer]
- Activation: Logo placement + Social Media Campaign

**Benefit**:
This directly addresses your need for [Success Answer].

Attached is the full deck. Let's get you on the grid!

Best,
[Rider Name]"""
}

# --- FUNCTIONS ---

def get_sector_hook(sector_name):
    for key, hook in SECTOR_HOOKS.items():
        if key in sector_name:
            return hook
    return SECTOR_HOOKS["Other"]



def extract_audit_stats(df):
    """
    Parses the Social Media Audit CSV.
    Returns total followers and platform breakdown string.
    """
    try:
        # Columns like "What is your current number of followers on Facebook?"
        # We'll just look for 'followers' in column name and sum the values
        total = 0
        breakdown = []
        
        # Simple heuristic: find columns with 'number of followers'
        cols = [c for c in df.columns if "number of followers" in c.lower()]
        
        row = df.iloc[0] # Assuming single user response per file or taking first row
        
        for c in cols:
            val_str = str(row[c]).replace(",", "").replace("nan", "0")
            if val_str.isdigit():
                val = int(val_str)
                total += val
                platform = c.split("on")[-1].replace("?", "").strip()
                breakdown.append(f"{platform}: {val}")
        
        return total, ", ".join(breakdown)
    except Exception as e:
        return 0, f"Error parsing: {str(e)}"

def extract_product_offers(df):
    """
    Parses "I'm a Product" CSV.
    Extracts the key offer points.
    """
    try:
        # Columns: "List 10 things you can offer..."
        offer_cols = [c for c in df.columns if "List 10 things" in c]
        row = df.iloc[0]
        
        all_offers = []
        for c in offer_cols:
            text = str(row[c])
            # Just take the first 3 lines/points from each section to avoid huge prompts
            lines = text.split(".")[:3] 
            all_offers.extend([l.strip() for l in lines if len(l) > 5])
            
        return "; ".join(all_offers[:5]) # Return top 5 offers as a string
        
    except Exception as e:
        return ""

def mock_search_places(location, radius, sector, mode="sector"):
    time.sleep(1.0)
    mock_data = []
    num_results = random.randint(5, 15)
    
    if mode == "previous":
        # Simulating "Previous Sponsors" in the area
        pkgs = ["Logistics", "Construction", "Engineering", "Tools", "Racing"]
        prefixes = ["Red", "Blue", "Apex", "Moto", "Grid", "Podium"]
        suffixes = ["Racing", "Partners", "Supporters", "Group"]
        for _ in range(num_results):
            name = f"{random.choice(prefixes)} {random.choice(pkgs)} {random.choice(suffixes)}"
            mock_data.append({
                "Business Name": name,
                "Address": f"{random.randint(1,99)} Racing Lane, {location}",
                "Rating": 5.0,
                "Website": f"https://www.{name.lower().replace(' ','')}.com",
                "Phone": "N/A",
                "Sector": "Motorsport Related"
            })
    else:
        prefixes = ["Elite", "Fast", "Primary", "Apex", "Local", "Global", "Premier", "Trusted"]
        suffixes = ["Ltd", "Inc", "Partners", "Group", "Solutions", "Services"]
        sector_term = sector.split(" ")[0] if sector != "Other (type your own)" else "Business"

        for _ in range(num_results):
            name = f"{random.choice(prefixes)} {sector_term} {random.choice(suffixes)}"
            address = f"{random.randint(1, 999)} {random.choice(['Main St', 'High St', 'Industrial Park', 'Speedway Blvd'])}, {location}"
            mock_data.append({
                "Business Name": name,
                "Address": address,
                "Rating": round(random.uniform(3.5, 5.0), 1),
                "Website": f"https://www.{name.lower().replace(' ', '')}.com",
                "Phone": f"+1 555-{random.randint(100, 999)}-{random.randint(1000, 9999)}",
                "Sector": sector
            })
    return pd.DataFrame(mock_data)

def generate_message(template_type, business_name, rider_name, sector, context_answers=None, town="MyTown", championship="Championship", extra_context={}):
    template = TEMPLATES.get(template_type, "")
    hook = get_sector_hook(sector)
    
    msg = template.replace("[Business Name]", business_name)\
                  .replace("[Rider Name]", rider_name)\
                  .replace("[Sector]", sector)\
                  .replace("[Town]", town)\
                  .replace("[Championship Name]", championship)\
                  .replace("[Sector Hook]", hook)\
                  .replace("[Contact Name/Business Name]", "Mr/Ms [Name]")\
                  .replace("[Contact Name]", "Mr/Ms [Name]")\
                  .replace("[Current Year]", "2026")
                  
    msg = msg.replace("[Season Goal]", extra_context.get("goal", ""))\
             .replace("[Previous Champ]", extra_context.get("prev_champ", ""))\
             .replace("[Achievements]", extra_context.get("achievements", ""))\
             .replace("[Audience Size]", extra_context.get("audience", ""))\
             .replace("[TV Viewers]", extra_context.get("tv", ""))\
             .replace("[Team Name]", extra_context.get("team", ""))
    
    if template_type == "Proposal" and context_answers:
        msg = msg.replace("[Goal Answer]", context_answers.get("Q1", "growth"))\
                 .replace("[Audience Answer]", context_answers.get("Q2", "locals"))\
                 .replace("[Success Answer]", context_answers.get("Q5", "brand awareness"))
                 
    return msg

# --- UI LAYOUT ---

st.image("logo.png", width=250)

# --- AUTHENTICATION & STARTUP ---
if 'user_id' not in st.session_state:
    st.session_state.user_id = None

def login_screen():
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        st.subheader("Login to Sponsor Finder")
        st.info("Enter your Name and Email to access.")
        
        name_input = st.text_input("Full Name")
        email_input = st.text_input("Email Address")
        
        # --- ACCESS CODE PROTECTION (DISABLED FOR TESTING) ---
        # access_code = st.text_input("Access Code (from your Course)", type="password")
        
        if st.button("Sign In / Sign Up", type="primary"):
            # Simple hardcoded check - in production could be env var
            # VALID_CODES = ["SPEED2026", "WINNER", "SPONSOR"]
            
            # if access_code not in VALID_CODES:
            #      st.error("❌ Invalid Access Code. Please check the 'Start Here' module in your course.")
            if email_input and "@" in email_input and name_input:
                user = db.get_user_by_email(email_input)
                if user:
                    # User exists - Log in
                    st.session_state.user_id = user['id']
                    # [NEW] Set Query Param for persistence
                    st.query_params["user"] = user['email']
                    st.success(f"Welcome back, {user['name']}!")
                    st.rerun()
                else:
                    # Create new user with provided Name
                    uid = db.save_user_profile(email_input, name_input, {"email": email_input, "onboarding_complete": False})
                    st.session_state.user_id = uid
                    st.query_params["user"] = email_input
                    st.success(f"Account created for {name_input}!")
                    st.rerun()
            else:
                st.error("Please enter both your Name and a valid Email.")

def onboarding_screen(user_data):
    st.title("🏁 Welcome! Let's set up your profile.")
    st.markdown("To help us find the right sponsors, tell us about your racing.")
    
    # Removed st.form to allow interactive conditionals
    st.subheader("1. About You")
    
    # Pre-fill from Login Name
    raw_name = user_data.get('name', '')
    pre_fname = ""
    pre_lname = ""
    if " " in raw_name:
        parts = raw_name.split(" ", 1)
        pre_fname = parts[0]
        pre_lname = parts[1]
    else:
        pre_fname = raw_name
        
    c1, c2 = st.columns(2)
    fname = c1.text_input("First Name", value=pre_fname)
    lname = c2.text_input("Last Name", value=pre_lname)
    
    c_loc1, c_loc2 = st.columns(2)
    user_town = c_loc1.text_input("Your Town / City (for local search)")
    user_country = c_loc2.text_input("Your Country")
    
    c_loc3, c_loc4 = st.columns(2)
    user_state = c_loc3.text_input("State / Province")
    user_zip = c_loc4.text_input("Zip / Postal Code")
    
    vehicle = st.selectbox("What do you race?", ["Motorcycle", "Car", "Kart"])
    
    st.subheader("2. Your Championship")
    champ_name = st.text_input("Championship Full Name")
    
    c3, c4 = st.columns(2)
    competitors = c3.number_input("Number of Competitors in the paddock", min_value=1, value=20)
    spectators = c4.text_input("Avg. Spectators per Event", value="5000")
    
    st.subheader("3. Media Exposure")
    c5, c6 = st.columns(2)
    # Use radio for immediate visibility vs selectbox (either works without form)
    is_tv = c5.selectbox("Is it Televised?", ["No", "Yes"])
    is_stream = c6.selectbox("Is it Streamed?", ["No", "Yes"])
    
    # Conditional Input
    tv_reach = ""
    if is_tv == "Yes" or is_stream == "Yes":
        st.info("Great! TV/Streaming is a huge selling point.")
        tv_reach = st.text_input("Do you have viewing figures from the organizer? (e.g. 50k per round)", placeholder="Enter number or 'Unknown'")
    
    st.divider()
    
    st.subheader("4. Database Setup")
    if airtable_manager.is_configured():
         st.success("✅ Central Database Connected")
    else:
         st.warning("⚠️ System is running in Local Mode (Sqlite). Ask Admin to configure Airtable.")
    
    st.divider()
    
    st.divider()
    
    if st.button("Complete Setup", type="primary"):
        missing = []
        if not fname: missing.append("First Name")
        if not champ_name: missing.append("Championship Name")
        if not user_town: missing.append("Town/City")
        if not user_country: missing.append("Country")
        


        if not missing:
            full_name = f"{fname} {lname}"
            
            profile_update = user_data['profile']
            profile_update.update({
                "first_name": fname, "last_name": lname,
                "vehicle": vehicle,
                "championship": champ_name, "country": user_country,
                "competitors": competitors, "audience": spectators, 
                "televised": is_tv, "streamed": is_stream,
                "tv_reach": tv_reach, 
                "tv": tv_reach, 
                "location": f"{user_town}, {user_state}, {user_country}, {user_zip}".strip(", "),
                "town": user_town, 
                "state": user_state,
                "zip_code": user_zip,
                "country": user_country, 
                "onboarding_complete": True
            })
            
            db.save_user_profile(user_data['email'], full_name, profile_update)
            st.success("Profile Saved! Loading Dashboard...")
            st.rerun()
        else:
            st.error(f"Please fill in the following: {', '.join(missing)}")

# LOGIC FLOW
# [NEW] Auto-Login Check
if not st.session_state.user_id:
    # Check query params
    qp = st.query_params.get("user")
    if qp:
         user = db.get_user_by_email(qp)
         if user:
             st.session_state.user_id = user['id']
             st.toast(f"Restored session for {user['name']}")
    
if not st.session_state.user_id:
    login_screen()
    st.stop()

# Load User
user_data = db.get_user_profile(st.session_state.user_id)
user_profile = user_data['profile']

# Initialize Session Globals for easy access
st.session_state.user_profile = user_profile
st.session_state.user_email = user_data['email']
st.session_state.user_name = user_data['name']

# Check Onboarding
if not user_profile.get("onboarding_complete"):
    onboarding_screen(user_data)
    st.stop() # Stop rendering the rest of the app

# AUTO-CONNECT GOOGLE SHEETS
if "google_cloud_key" in user_profile and "google_sheet_url" in user_profile:
    if not st.session_state.get("use_sheets"): # Only connect if not already done
        try:
            ok, msg = sheet_manager.connect(user_profile["google_cloud_key"], user_profile["google_sheet_url"])
            if ok:
                st.session_state["use_sheets"] = True
                st.session_state["sheet_url"] = user_profile["google_sheet_url"]
                # Optional: st.toast("Connected to Google Sheets Database")
        except Exception as e:
            st.error(f"Failed to auto-connect to Sheets: {e}")

# --- MAIN APP (LOGGED IN & ONBOARDED) ---
with st.sidebar:
    st.caption(f"Logged in as: {user_data['email']}")
    if st.button("Logout"):
        st.session_state.user_id = None
        st.session_state.leads = pd.DataFrame()
        st.rerun()
        
    st.header("👤 Rider Profile")
   
    # Load params
    rider_name = user_data['name']
    
    # Split Location
    saved_town = user_profile.get('town', '')
    saved_state = user_profile.get('state', '')
    saved_country = user_profile.get('country', '')
    saved_zip = user_profile.get('zip_code', '')
    
    location_parts = [saved_town, saved_state, saved_country, saved_zip]
    location_display = ", ".join([p for p in location_parts if p])
    
    championship = user_profile.get('championship', 'Unknown')
    
    # Simple display
    st.write(f"**Name:** {rider_name}")
    st.write(f"**Racing:** {user_profile.get('vehicle', 'Racer')}")
    st.write(f"**Series:** {championship}")
    
    with st.expander("Edit / Upload Data", expanded=False):
        with st.form("profile_form"):
            p_name = st.text_input("Name", value=rider_name)
            
            c1, c2 = st.columns(2)
            with c1:
                p_town = st.text_input("Town", value=saved_town)
            with c2:
                p_country = st.text_input("Country", value=saved_country)
                
            c3, c4 = st.columns(2)
            with c3:
                p_state = st.text_input("State", value=saved_state)
            with c4:
                p_zip = st.text_input("Zip Code", value=saved_zip)
            
            # [NEW] File Uploaders
            f_audit = st.file_uploader("Social Media Audit (CSV)", type="csv")
            f_prod = st.file_uploader("Product Worksheet (CSV)", type="csv")
            
            # Update additional stats
            p_goal = st.text_input("Season Goal", value=user_profile.get('goal', 'Top 5'))
            
            if st.form_submit_button("Save Updates"):
                # Handle CSVs logic here (simplified for brevity, assume similar to before)
                if f_audit:
                    try:
                        df = pd.read_csv(f_audit)
                        tot, _ = extract_audit_stats(df)
                        user_profile['followers_count'] = tot
                        user_profile['audience'] = f"{tot} (Social)"
                    except Exception as e:
                        st.error(f"Error reading Social Audit CSV: {e}")
                        st.stop()
                
                user_profile['town'] = p_town
                user_profile['country'] = p_country
                user_profile['state'] = p_state
                user_profile['zip_code'] = p_zip
                user_profile['goal'] = p_goal
                
                db.save_user_profile(user_data['email'], p_name, user_profile)
                st.rerun()

    # Load generator context vars
    season_goal = user_profile.get('goal', '')
    prev_champ = user_profile.get('prev_champ', '')
    achievements = user_profile.get('achievements', '')
    audience_size = user_profile.get('audience', '')
    tv_viewers = user_profile.get('tv', '') if user_profile.get('televised') == "Yes" else "N/A"
    team_name = user_profile.get('team', '')
    
    st.divider()
    st.header("Search Config")
    search_radius = st.slider("Radius (Miles)", 10, 500, 50)
    search_mode = st.radio("Mode", ["Sector Search", "Company Scout"])
    
    location_search_ctx = ", ".join([p for p in [saved_town, saved_state, saved_country, saved_zip] if p])
    if not location_search_ctx:
        location_search_ctx = "Silverstone, UK" # Fallback
    
    scout_company = ""
    scout_location = ""
    
    if search_mode == "Sector Search":
        selected_sector = st.selectbox("Target Sector", SECTORS, index=0, key="target_sector_select")
        if selected_sector == "Other (type your own)":
            search_query = st.text_input("Enter key words")
        else:
            search_query = selected_sector
    else:
        # COMPANY SCOUT MODE
        st.info("🎯 Enter specific details to analyze a target.")
        scout_company = st.text_input("Company Name")
        scout_location = st.text_input("City / Location", value=saved_town)
        search_query = f"{scout_company} in {scout_location}" if scout_company else ""

    st.markdown("---")
    st.markdown("---")
    with st.expander("⚙️ Settings (Premium Features)"):
        # Load saved key
        # Check st.secrets first (System Managed)
        system_key = st.secrets.get("google_api_key", "")
        
        if system_key:
             st.success("✅ Google API Key is managed by the system (Shared Key active).")
             google_api_key = system_key
        else:
             saved_key = st.session_state.user_profile.get("google_api_key", "")
             google_api_key = st.text_input("Google Places API Key", value=saved_key, type="password", help="Needed for real map results.")
        
             if google_api_key != saved_key:
                 # Save to Profile logic
                 st.session_state.user_profile["google_api_key"] = google_api_key
                 # Persist
                 db.save_user_profile(st.session_state.user_email, st.session_state.user_name, st.session_state.user_profile)
                 st.toast("API Key Saved! It is now locked in.")
            
             st.caption("Enter your key once to unlock Real Search for all future sessions.")
    
    if airtable_manager.is_configured():
        st.success("✅ Connected to Central Database (Airtable)")
    else:
        with st.expander("📊 Data Source (Legacy Google Sheets)"):
            st.info("Connect a Google Sheet to share leads across devices.")
            
            # 1. Service Account Key
            st.subheader("1. Setup Credentials")
            key_file = st.file_uploader("Upload 'service_account.json'", type="json", help="Get this from Google Cloud Console")
            
            # 2. Sheet Link
            st.subheader("2. Link Sheet")
            sheet_url = st.text_input("Google Sheet Share Link", placeholder="https://docs.google.com/spreadsheets/d/...")
            
            if st.button("Connect to Sheets"):
                if key_file and sheet_url:
                    try:
                        # Load JSON from file
                        key_data = json.load(key_file)
                        
                        # Connect
                        success, msg = sheet_manager.connect(key_data, sheet_url)
                        if success:
                            st.session_state["use_sheets"] = True
                            st.session_state["sheet_url"] = sheet_url
                            st.success(f"Connected! Using Google Sheets as Database. {msg}")
                            st.rerun()
                        else:
                            st.error(f"Connection Failed: {msg}")
                    except Exception as e:
                        st.error(f"Error loading key: {e}")
                else:
                    st.warning("Please upload the JSON key and provide a URL.")
                    
            if st.session_state.get("use_sheets"):
                st.success("✅ Currently Using Google Sheets")
                if st.button("Disconnect (Revert to Local DB)"):
                    st.session_state["use_sheets"] = False
                    st.rerun()


# Main Content - TABS
# Main Content - TABS
# Workflow: 1. Search -> 2. Outreach -> 3. Manage
# Main Content - TABS
# Workflow: 1. Search -> 2. Outreach -> 3. Manage

# [FIX] Use Radio for Navigation so we can switch programmatically
TABS = [" Search & Add", "✉️ Outreach Assistant", "📊 Active Campaign"]
if "current_tab" not in st.session_state:
    st.session_state.current_tab = TABS[0]

# [FIX] Handle deferred tab switching to prevent StreamlitAPIException
if "requested_tab" in st.session_state:
    tgt = st.session_state.requested_tab
    st.session_state.current_tab = tgt
    st.session_state.nav_radio = tgt # Sync widget key
    del st.session_state.requested_tab

# Navigation Bar
st.session_state.current_tab = st.radio(
    "", 
    TABS, 
    index=TABS.index(st.session_state.current_tab) if st.session_state.current_tab in TABS else 0,
    horizontal=True, 
    label_visibility="collapsed",
    key="nav_radio"
)

# Helper to sync radio
if st.session_state.nav_radio != st.session_state.current_tab:
    st.session_state.current_tab = st.session_state.nav_radio
    st.rerun()

current_tab = st.session_state.current_tab

# STATE MANAGEMENT
if 'leads' not in st.session_state:
    st.session_state.leads = pd.DataFrame() # Temporary search results
if 'selected_lead_id' not in st.session_state:
    st.session_state.selected_lead_id = None

# TAB 3: DASHBOARD (Active Campaign) - Moved to end
# TAB 3: DASHBOARD (Active Campaign)
# TAB 3: DASHBOARD (Active Campaign)
if current_tab == "📊 Active Campaign":
    st.subheader("Your Active Campaign")
    
    # Load Leads from DB for THIS user
    my_leads = db.get_leads(st.session_state.user_id)
    
    if not my_leads:
        st.info("No leads yet. Go to 'Search & Add' to find sponsors.")
        if st.button("➕ Find Sponsors Now"):
             st.info("Click the 'Search & Add' tab on the left!")
    else:
        # --- SMART DASHBOARD LOGIC ---
        df_leads = pd.DataFrame(my_leads)
        
        # Date Handling
        today_str = datetime.now().strftime("%Y-%m-%d")
        df_leads['Next Action'] = pd.to_datetime(df_leads['Next Action'], errors='coerce')
        
        # 1. Calculate Stats
        # Due Today or Overdue
        due_mask = (df_leads['Next Action'] <= pd.Timestamp.now()) & (df_leads['Status'] != 'Secured') & (df_leads['Status'] != 'Lost')
        due_leads = df_leads[due_mask]
        num_due = len(due_leads)
        
        num_active = len(df_leads[df_leads['Status'] == 'Active'])
        num_secured = len(df_leads[df_leads['Status'] == 'Secured'])
        
        # 2. QUICK FILTERS
        # Initialize filter state
        if 'dashboard_filter' not in st.session_state:
            st.session_state.dashboard_filter = "All"
        
        f1, f2, f3 = st.columns(3)
        
        # Filter 1: Action Required (Overdue or Due Today)
        label_1 = f"⚠️ Action Required ({num_due})"
        if f1.button(label_1, type="primary" if st.session_state.dashboard_filter == "Action" else "secondary", use_container_width=True):
             st.session_state.dashboard_filter = "Action"
        
        # Filter 2: Active Pipeline (Anything NOT Secured or Lost)
        # Using the standard statuses: ["Pipeline", "Active", "Secured", "Lost"]
        active_mask = ~df_leads['Status'].isin(['Secured', 'Lost'])
        count_active = len(df_leads[active_mask])
        label_2 = f"🔥 Active Pipeline ({count_active})"
        if f2.button(label_2, type="primary" if st.session_state.dashboard_filter == "Pipeline" else "secondary", use_container_width=True):
             st.session_state.dashboard_filter = "Pipeline"
             
        # Filter 3: Secured
        label_3 = f"🏆 Secured Deals ({num_secured})"
        if f3.button(label_3, type="primary" if st.session_state.dashboard_filter == "Secured" else "secondary", use_container_width=True):
             st.session_state.dashboard_filter = "Secured"
             
        # Reset
        if st.session_state.dashboard_filter != "All":
            if st.button("❌ Reset Filter"):
                st.session_state.dashboard_filter = "All"
                st.rerun()
        
        st.divider()
        
        # APPLY FILTER
        df_view = df_leads.copy()
        if st.session_state.dashboard_filter == "Action":
             df_view = df_view[due_mask]
        elif st.session_state.dashboard_filter == "Pipeline":
             df_view = df_view[active_mask]
        elif st.session_state.dashboard_filter == "Secured":
             df_view = df_view[df_leads['Status'] == 'Secured']
        
        # Sort by Next Action
        df_view = df_view.sort_values(by="Next Action")
        
        # VIEW TOGGLE
        v_col1, v_col2 = st.columns([1, 4])
        with v_col1:
            view_mode = st.radio("View Mode", ["Cards", "Calendar", "List Table"], horizontal=True)
            
        # FORMATTING HELPERS
        def get_status_color(status):
            if status == "Secured" or status == "Sponsor": return "green"
            if status == "Lost" or status == "Dead" or status == "Rejection": return "red"
            if status == "Active" or status == "Meeting": return "orange"
            return "blue" # Pipeline
        
        # --- MODE: CONTACT CARDS ---
        if view_mode == "Cards":
            st.caption("👇 Click 'Manage' to open the Outreach Assistant.")
            
            # Use filtered df
            # Grid Layout
            
            # Grid Layout
            cols = st.columns(3)
            for idx, row in df_view.iterrows():
                with cols[idx % 3]:
                    with st.container(border=True):
                        # Header
                        st.markdown(f"**{row['Business Name']}**")
                        st.caption(f"_{row['Sector']}_")
                        
                        # Status Badge
                        color = get_status_color(row['Status'])
                        st.markdown(f":{color}[●] **{row['Status']}**")
                        
                        # Dates
                        d_str = row['Next Action'].strftime('%Y-%m-%d') if pd.notnull(row['Next Action']) else "No Date"
                        st.write(f"📅 Next: **{d_str}**")
                        
                        # [NEW] Notes Display
                        notes_data = row.get("Notes", {})
                        if notes_data:
                            with st.expander("📝 Notes"):
                                if isinstance(notes_data, dict):
                                    st.write(notes_data.get("initial_note", ""))
                                    # Show other keys?
                                    for k, v in notes_data.items():
                                        if k != "initial_note" and not k.startswith("Q"):
                                             st.caption(f"**{k}:** {v}")
                                else:
                                    st.write(str(notes_data))
                        
                        # Actions
                        if st.button("➡️ Manage", key=f"btn_{row['id']}"):
                            st.session_state.selected_lead_id = row['id']
                            # Switch to Outreach Tab (Deferred)
                            st.session_state.requested_tab = "✉️ Outreach Assistant"
                            st.rerun()
                            # Switching tabs in Streamlit is tricky without extra component. 
                            # We will rely on user clicking the tab, but set the state.
                            st.toast(f"Selected {row['Business Name']}! Switch to 'Outreach Assistant' tab.")
        
        # --- MODE: CALENDAR ---
        elif view_mode == "Calendar":
            st.caption("📅 Drag and drop isn't supported yet, but here is your schedule.")
            
            events = []
            for _, row in df_leads.iterrows():
                if pd.notnull(row['Next Action']):
                    events.append({
                        "title": f"{row['Business Name']} ({row['Status']})",
                        "start": row['Next Action'].strftime("%Y-%m-%d"),
                        "backgroundColor": get_status_color(row['Status']),
                        "borderColor": get_status_color(row['Status']),
                        "extendedProps": {"id": row['id']}
                    })
            
            calendar_options = {
                "headerToolbar": {
                    "left": "today prev,next",
                    "center": "title",
                    "right": "dayGridMonth,timeGridWeek,timeGridDay"
                },
                "initialView": "dayGridMonth",
            }
            
            cal_data = calendar(events=events, options=calendar_options)
            
            if cal_data.get("eventClick"):
                 event = cal_data["eventClick"]["event"]
                 lead_id = event["extendedProps"]["id"]
                 st.session_state.selected_lead_id = lead_id
                 st.session_state.requested_tab = "✉️ Outreach Assistant"
                 st.rerun()
            
        # --- MODE: LIST TABLE (Legacy) ---
        else:
            # Filter by Status (Optional)
            status_filter = st.multiselect("Filter by Status", df_leads['Status'].unique(), default=df_leads['Status'].unique())
            if status_filter:
                df_view = df_leads[df_leads['Status'].isin(status_filter)]
            else:
                df_view = df_leads
                
            # Format date for display
            df_view['Next Action'] = df_view['Next Action'].dt.strftime('%Y-%m-%d')
            
            # Sort by Next Action so urgent stuff is top
            df_view = df_view.sort_values(by="Next Action")
                
            st.dataframe(df_view[["Business Name", "Sector", "Status", "Contact Name", "Next Action"]], use_container_width=True)
            
            # Legacy Actions below table
            lead_choice = st.selectbox("Select Lead to Manage", df_leads["Business Name"].tolist(), key="dash_picker")
            lid = df_leads[df_leads["Business Name"] == lead_choice].iloc[0]["id"]
            
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                if st.button("➡️ Message / Manage", type="primary"):
                    st.session_state.selected_lead_id = lid
                    st.session_state.requested_tab = "✉️ Outreach Assistant"
                    st.rerun()
            with c2:
                if st.button("🔄 Set Active"):
                    db.update_lead_status(lid, "Active")
                    st.rerun()
            with c3:
                if st.button("✅ Set Secured"):
                    db.update_lead_status(lid, "Secured")
                    st.rerun()
            with c4:
                if st.button("❌ Delete"):
                    delete_confirmation_dialog(lid, lead_choice)


# TAB 1: SEARCH (DISCOVERY)
# TAB 1: SEARCH (DISCOVERY)
if current_tab == " Search & Add":
    
    # --- SECTION A: ADD EXISTING LEADS ---
    with st.expander("➕ Import Existing Leads (Manual or CSV)", expanded=False):
        tab_man, tab_csv = st.tabs(["Manual Entry", "Bulk CSV Upload"])
        
        with tab_man:
            with st.form("manual_add_form"):
                c1, c2 = st.columns(2)
                m_name = c1.text_input("Business Name *")
                m_contact = c2.text_input("Contact Person")
                
                c3, c4 = st.columns(2)
                m_sector = c3.selectbox("Sector", SECTORS)
                m_status = c4.selectbox("Status", ["Pipeline", "Active", "Secured", "Lost"])
                
                m_notes = st.text_area("Initial Notes / Context")
                
                if st.form_submit_button("Add Single Lead"):
                    if m_name:
                        # Add via DB
                        # Note: We need to handle GSheets or SQLite routing. 
                        # Ideally db_manager abstracts this, but we modified sheets_manager directly for bulk.
                        # For single add, db_manager.add_lead works fine for both.
                        
                        if db.add_lead(
                            st.session_state.user_id, 
                            m_name, 
                            m_sector, 
                            "Manual Entry", 
                            status=m_status, 
                            contact_name=m_contact,
                            notes_json={"initial_note": m_notes}
                        ):
                            st.success(f"Added {m_name}!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"Failed to add '{m_name}'. It may be a duplicate or a connection error.")
                    else:
                        st.error("Business Name is required.")
        
        with tab_csv:
            st.info("Upload a CSV with columns: 'Business Name', 'Sector', 'Contact Name', 'Email', 'Website'")
            up_file = st.file_uploader("Upload CSV", type="csv")
            
            if up_file:
                if st.button("Process Import"):
                    try:
                        import_df = pd.read_csv(up_file)
                        # Normalize cols
                        # Expect users to have random col names, try to map standard ones
                        # Simple mapping strategy:
                        leads_batch = []
                        for _, row in import_df.iterrows():
                            # Flexible get
                            b_name = row.get("Business Name") or row.get("Company") or row.get("Name")
                            if b_name:
                                leads_batch.append({
                                    "Business Name": str(b_name),
                                    "Sector": str(row.get("Sector", "Imported")),
                                    "Address": str(row.get("Address", "Unknown")),
                                    "Website": str(row.get("Website", "")),
                                    "Contact Name": str(row.get("Contact Name") or row.get("Contact") or ""),
                                    "Notes": {"source": "csv_import"}
                                })
                        
                        if leads_batch:
                            # Use Sheets Manager directly if in sheets mode, else loop db
                            if st.session_state.get("use_sheets"):
                                ok, msg = sheet_manager.add_leads_bulk(leads_batch)
                                if ok: st.success(msg)
                                else: st.error(msg)
                            else:
                                count = 0
                                for l in leads_batch:
                                    db.add_lead(st.session_state.user_id, l["Business Name"], l["Sector"], l["Address"], website=l["Website"], contact_name=l["Contact Name"])
                                    count += 1
                                st.success(f"Imported {count} leads to Local DB.")
                        else:
                            st.warning("Could not find a 'Business Name', 'Company', or 'Name' column in your CSV.")
                            
                    except Exception as e:
                        st.error(f"Error reading CSV: {e}")

    st.divider()

    st.subheader(f"Find {search_query} within {search_radius} miles of {location_search_ctx}")
    
    # NEW SEARCH (Reset)
    if st.button("Run Search (Scout)", type="primary"):
        st.session_state.leads = pd.DataFrame() # Clear old
        st.session_state.next_page_token = None
        
        if search_mode == "Company Scout" and not scout_company:
             st.error("Please enter a Company Name to scout.")
        else:
            with st.spinner("Scanning Page 1..."):
                if google_api_key:
                    # REAL SEARCH - Page 1
                    results, next_token = search_google_places(google_api_key, search_query, location_search_ctx, search_radius)
                    
                    if isinstance(results, dict) and "error" in results:
                        st.error(f"Google API Error: {results['error']}")
                    else:
                        st.session_state.leads = pd.DataFrame(results)
                        st.session_state.next_page_token = next_token
                        
                        if not results:
                             st.warning("No results found.")
                        else:
                             st.success(f"Found {len(results)} targets on Page 1.")
                             
                else:
                    # MOCK SEARCH (unchanged)
                    mode_arg = "previous" if search_mode == "Company Scout" else "sector"
                    results = mock_search_places(location_search_ctx, search_radius, search_query, mode=mode_arg)
                    st.session_state.leads = pd.DataFrame(results)
                    st.session_state.next_page_token = None
                    st.info("ℹ️ Demo Mode.")

    # LOAD MORE BUTTON
    if st.session_state.get("next_page_token"):
        if st.button("⬇️ Load Next 20 Results"):
             with st.spinner("Fetching next page..."):
                 token = st.session_state.next_page_token
                 new_results, new_token = search_google_places(google_api_key, search_query, location_search_ctx, search_radius, pagetoken=token)
                 
                 if new_results:
                     # Append to existing DataFrame
                     new_df = pd.DataFrame(new_results)
                     st.session_state.leads = pd.concat([st.session_state.leads, new_df], ignore_index=True)
                     st.success(f"Added {len(new_results)} more! Total: {len(st.session_state.leads)}")
                 
                 st.session_state.next_page_token = new_token # Update token (or None if done)
                 if not new_token:
                     st.info("✅ All pages loaded.")
                 st.rerun()

    # Post-Processing: Check for Duplicates (Run always if leads exist)
    if not st.session_state.leads.empty:
        # 1. Fetch current user leads
        my_leads = db.get_leads(st.session_state.user_id)
        existing_names = {l["Business Name"].lower() for l in my_leads}
        
        # 2. Add "In List" column
        df_results = st.session_state.leads.copy()
        df_results["In List"] = df_results["Business Name"].apply(lambda x: "✅" if str(x).lower() in existing_names else "")
        
        # MAP DISPLAY (If lat/lon ok)
        if "lat" in df_results.columns:
                st.map(df_results)
                
        # Show Website in table
        disp_cols = ["In List", "Business Name", "Address", "Sector", "Rating"]
        if "Website" in df_results.columns:
            disp_cols.insert(3, "Website")
            
        st.dataframe(
                df_results[disp_cols],
                use_container_width=True
        )
    
        
        # Add to DB Logic
        col_s1, col_s2 = st.columns([3, 1])
        with col_s1:
            # Filter out already added ones for the dropdown preference, or just show all
            add_choice = st.selectbox("Select result to track", df_results["Business Name"].unique())
        with col_s2:
            # Check status
            is_in_list = add_choice.lower() in existing_names
            
            if st.button("➕ Add to My Leads", disabled=is_in_list):
                if is_in_list:
                    st.error("Already in your list!")
                else:
                    # Get full row
                    row = df_results[df_results["Business Name"] == add_choice].iloc[0]
                    
                    # Extract fields safely
                    b_name = row["Business Name"]
                    b_sect = row["Sector"]
                    b_loc = row["Address"]
                    b_web = row.get("Website", "") # Safe get
                    
                    # Pass explicit args to match db_manager signature
                    try:
                        new_lead_id = db.add_lead(st.session_state.user_id, b_name, b_sect, b_loc, website=b_web)
                    except Exception as e:
                        st.error(f"Critical Error in add_lead: {e}")
                        new_lead_id = None
                        
                    if new_lead_id:
                        st.toast(f"Added {add_choice} to Dashboard!")
                        
                        # [NEW] Auto-Switch for SCOUT MODE
                        if search_mode == "Company Scout":
                            st.session_state.selected_lead_id = new_lead_id
                            st.session_state.requested_tab = "✉️ Outreach Assistant"
                            st.rerun()
                            
                        # Force rerun to update duplicate list
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.warning("Could not add lead. See error message above.")
                if is_in_list:
                    st.caption("Detailed marked as added.")

# TAB 2: OUTREACH
# TAB 2: OUTREACH
# TAB 2: OUTREACH
if current_tab == "✉️ Outreach Assistant":
    st.subheader("✉️ Outreach Assistant")
    
    # 1. LOAD ALL LEADS FOR SELECTOR
    all_leads = db.get_leads(st.session_state.user_id)
    if not all_leads:
        st.info("No leads found. Go to 'Search & Add' to build your list.")
    else:
        # Prepare lists
        lead_names = [l["Business Name"] for l in all_leads]
        lead_ids = [l["id"] for l in all_leads]
        
        # Determine current index
        current_idx = 0
        if st.session_state.selected_lead_id in lead_ids:
            current_idx = lead_ids.index(st.session_state.selected_lead_id)
            
        # UI: Dropdown to switch
        col_sel1, col_sel2 = st.columns([3, 1])
        with col_sel1:
            selected_name = st.selectbox(
                "Select Company to Manage:", 
                lead_names, 
                index=current_idx,
                key="outreach_lead_picker"
            )
        
        # Update State based on selection
        # (This logic is implicit because selectbox returns the selected name)
        # We just need to synchronize the ID
        selected_lead_row = next((l for l in all_leads if l["Business Name"] == selected_name), None)
        if selected_lead_row and selected_lead_row['id'] != st.session_state.selected_lead_id:
             st.session_state.selected_lead_id = selected_lead_row["id"]
             st.rerun()

        # 2. MAIN OUTREACH UI
        if st.session_state.selected_lead_id:
            lead = next((l for l in all_leads if l['id'] == st.session_state.selected_lead_id), None)
            
            if lead:
                st.divider() 
                # Header Stats
                h1, h2, h3 = st.columns(3)
                h1.metric("Status", lead['Status'])
                # Handle missing or string values
                last_c = lead.get('Last Contact', 'Never')
                next_a = lead.get('Next Action', 'ASAP')
                h2.metric("Last Contact", str(last_c))
                h3.metric("Next Action", str(next_a))
                h3.metric("Next Action", str(next_a))

        else:
             st.warning("You have no leads saved! Go to 'Search & Add' first.")

    if st.session_state.selected_lead_id:
        # Get fresh lead data
        all_leads = db.get_leads(st.session_state.user_id)
        # simplistic filter
        lead = next((l for l in all_leads if l['id'] == st.session_state.selected_lead_id), None)
        
        if lead:
            st.header(f"Strategy: {lead['Business Name']} ({lead['Status']})")

            
            # Sub-Stages
            stage = st.radio("Stage", ["1. Connect", "2. Discovery Call", "3. Proposal"], horizontal=True)
            st.divider()

            col1, col2 = st.columns([1, 1.5], gap="large")

            # --- STAGE 1: CONNECT ---
            if stage == "1. Connect":
                with col1:
                    st.subheader("Decision Makers & Research")
                    
                    # PREP: Get Domain for advanced operators
                    website_url = lead.get('Website', '')
                    domain = ""
                    if website_url:
                        # Simple strip to get domain.com
                        domain = website_url.replace("https://", "").replace("http://", "").replace("www.", "").strip("/")
                        domain = domain.split("/")[0] # Just the root domain
                    
                    st.info(f"Targeting: **{lead['Business Name']}**" + (f" (`{domain}`)" if domain else ""))
                    
                    # PILLAR 1: THE WEB DOCTRINE
                    with st.expander("1️⃣ The Web (Deep Dive)", expanded=True):
                        if domain:
                            # --- OPERATOR BUILDER HELPER ---
                            def google_link(query, label):
                                url = f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}"
                                st.markdown(f"• [{label}]({url})")

                            st.markdown("##### 🎯 1. Decision Makers")
                            google_link(f'site:linkedin.com/in "managing director" OR "CEO" OR "owner" OR "founder" "{lead["Business Name"]}"', "LinkedIn: Senior Leadership")
                            google_link(f'site:twitter.com "{lead["Business Name"]}" AND ("sponsorship" OR "marketing" OR "partnerships")', "Twitter: Marketing Team")
                            google_link(f'("{lead["Business Name"]}") AND ("managing director" OR "CEO" OR "marketing director") AND ("email" OR "phone" OR "LinkedIn")', "General: Identify Key People")

                            st.markdown("##### 📞 2. Contact Information")
                            google_link(f'"{lead["Business Name"]}" AND ("phone" OR "mobile" OR "email" OR "contact")', "Find Phones & Emails")
                            google_link(f'"contact" OR "directory" OR "team" site:{domain}', "Internal Team Directory")
                            google_link(f'site:linkedin.com/in "first_name last_name" "{lead["Business Name"]}"', "Verify Name on LinkedIn")

                            st.markdown("##### 💰 3. Financials & Size")
                            google_link(f'site:companieshouse.gov.uk "{lead["Business Name"]}" "directors" OR "officers"', "Companies House (UK) Directors")
                            google_link(f'"{lead["Business Name"]}" AND ("annual revenue" OR "turnover" OR "sales" OR "net worth")', "Revenue & Net Worth")
                            google_link(f'site:plimsoll.co.uk OR site:endole.co.uk "{lead["Business Name"]}"', "Financial Health Check")

                            st.markdown("##### 🤝 4. Sponsorship History")
                            google_link(f'"{lead["Business Name"]}" AND ("sponsored" OR "sponsorship" OR "supporting" OR "partnering")', "Past Sponsorship Activity")
                            google_link(f'site:{domain} "sponsorship" OR "partners" OR "community" OR "charity"', "Company Policy: Giving Back")
                            google_link(f'"{lead["Business Name"]}" AND ("marketing budget" OR "advertising spend")', "Marketing Spend Indicators")

                            st.markdown("##### 📰 5. News & Strategy")
                            google_link(f'site:prnewswire.com OR site:businesswire.com "{lead["Business Name"]}"', "Press Releases")
                            google_link(f'site:{domain} filetype:pdf OR filetype:ppt "strategy" OR "report"', "Internal Strategy Documents (PDF/PPT)")
                            google_link(f'related:{domain}', "Competitor Analysis")
                        else:
                            st.warning("No website URL found. Run a Google Search to find their domain first.")
                            q_gen = f'{lead["Business Name"]} official site'
                            u_gen = f"https://www.google.com/search?q={urllib.parse.quote_plus(q_gen)}"
                            st.markdown(f"• [**Find Website**]({u_gen})")

                    # PILLAR 2: NEWS & TRENDS
                    with st.expander("2️⃣ News & Trends"):
                        # Intitle Search
                        q_news = f'intitle:"{lead["Business Name"]}" "merger" OR "launch" OR "lawsuit"'
                        u_news = f"https://www.google.com/search?q={urllib.parse.quote_plus(q_news)}"
                        st.markdown(f"• [**High Impact Headlines**]({u_news})")
                        
                        # Recent (After 2024 - Dynamic could be better but hardcoding roughly for now)
                        q_rec = f'"{lead["Business Name"]}" after:2024-01-01'
                        u_rec = f"https://www.google.com/search?q={urllib.parse.quote_plus(q_rec)}"
                        st.markdown(f"• [**Latest News (Last 12mo)**]({u_rec})")
                        
                        # Exclude self-PR
                        if domain:
                            q_no_pr = f'"{lead["Business Name"]}" -site:{domain}'
                            u_no_pr = f"https://www.google.com/search?q={urllib.parse.quote_plus(q_no_pr)}"
                            st.markdown(f"• [**External Press Only**]({u_no_pr})")

                    # PILLAR 3: SPONSORSHIP HISTORY
                    with st.expander("3️⃣ Sponsorship History"):
                        # Sponsored By
                        q_spon = f'"sponsored by" AND "{lead["Business Name"]}"'
                        u_spon = f"https://www.google.com/search?q={urllib.parse.quote_plus(q_spon)}"
                        st.markdown(f"• [**'Sponsored By' Search**]({u_spon})")
                        
                        # Partnership Announcements
                        q_part = f'"{lead["Business Name"]}" (partnership OR "proud sponsor" OR "official partner")'
                        u_part = f"https://www.google.com/search?q={urllib.parse.quote_plus(q_part)}"
                        st.markdown(f"• [**Partnership Announcements**]({u_part})")
                        
                        # Charity/Grants
                        q_org = f'site:.org "{lead["Business Name"]}" (donation OR sponsor)'
                        u_org = f"https://www.google.com/search?q={urllib.parse.quote_plus(q_org)}"
                        st.markdown(f"• [**Charity & Grants (.org)**]({u_org})")

                    # PILLAR 4: LINKEDIN X-RAY
                    with st.expander("4️⃣ LinkedIn Intel"):
                        # X-Ray People
                        q_xray = f'site:linkedin.com/in "{lead["Business Name"]}"'
                        u_xray = f"https://www.google.com/search?q={urllib.parse.quote_plus(q_xray)}"
                        st.markdown(f"• [**All Employees (X-Ray)**]({u_xray})")
                        
                        # Specific Roles
                        q_role = f'site:linkedin.com/in "{lead["Business Name"]}" "Marketing" OR "Sponsorship" OR "Brand"'
                        u_role = f"https://www.google.com/search?q={urllib.parse.quote_plus(q_role)}"
                        st.markdown(f"• [**Find Decision Makers**]({u_role})")
                        
                        # Company Page
                        q_co = f'site:linkedin.com/company "{lead["Business Name"]}"'
                        u_co = f"https://www.google.com/search?q={urllib.parse.quote_plus(q_co)}"
                        st.markdown(f"• [**Official Company Page**]({u_co})")
                    
                    st.divider()
                    
                    # 4. AI Deep Research Prompt
                    with st.expander("🤖 AI Deep Research Prompt (for ChatGPT/Perplexity)", expanded=False):
                        st.caption("Copy this prompt and paste it into ChatGPT, Claude, or Perplexity for a full dossier.")
                        
                        ai_prompt = f"""Act as an elite motorsport-sponsorship acquisition analyst.  
Produce a 2-minute brief for “{lead['Business Name']}” ({lead.get('Sector', 'Unknown')} sector) with:
1. Corporate overview & revenue band
2. Any motorsport / automotive sponsorship history (last 5 yrs)
3. News & financial milestones (last 12 months)
4. Three verified decision-makers (Name – Role – LinkedIn URL)
5. Verified email pattern + main phone number
6. 3-sentence sponsorship angle tailored to {rider_name} ({championship}).

Supply a source URL for every data point. Do not guess emails."""
                        
                        st.code(ai_prompt, language=None)


                    
                    st.divider()
                    

                    
                    # Manual Entry to DB
                    new_name = st.text_input("Found Contact Name", value=lead['Contact Name'])
                    if st.button("Update Contact"):
                        # We would need a db update function for contact name specific fields, 
                        # for now simplistic mock
                        st.toast("Contact Saved (simulated)")

                with col2:
                    c_mode = st.radio("Action Mode", ["Draft Opener", "Handle Reply"], horizontal=True)
                    
                    if c_mode == "Draft Opener":
                        st.subheader("Outreach Message")
                        target_name = new_name if new_name else "Mr/Ms [Name]"
                        
                        # Use saved town from profile
                        town = saved_town 
                        
                        seq_options = [
                            "Email: Cold Opener",
                            "LI Msg 1: Connect",
                            "LI Msg 2: Reminder (Day 2)",
                            "LI Msg 3: Opportunities (Day 7)",
                            "LI Msg 4: Value (Day 14)",
                            "LI Msg 5: Unique Offer (Day 21)",
                            "LI Msg 6: Final Nudge (Day 28)"
                        ]
                        
                        tpl = st.selectbox("Template", seq_options)
                        
                        # Context from Sidebar/DB
                        ctx = {
                            "goal": season_goal,
                            "prev_champ": prev_champ,
                            "achievements": achievements,
                            "audience": audience_size,
                            "tv": tv_viewers,
                            "team": team_name
                        }
                        
                        # Town extraction
                        draft = generate_message(tpl, lead['Business Name'], rider_name, lead['Sector'], town=town, championship=championship, extra_context=ctx).replace("Mr/Ms [Name]", target_name).replace("[Contact Name]", target_name)
                        
                        final_msg = st.text_area("Edit Message:", value=draft, height=250)
                        
                        st.caption("👇 Click the Copy icon in the top right of the box below")
                        st.code(final_msg, language=None)
                        
                        # MANUAL DATE OVERRIDE
                        col_d1, col_d2 = st.columns([2, 1])
                        with col_d1:
                            # 1. Calculate Standard Timing (Training Doc)
                            def_days = 2
                            if "Msg 2" in tpl: def_days = 5
                            elif "Msg 3" in tpl: def_days = 7
                            elif "Msg 4" in tpl: def_days = 7
                            elif "Msg 5" in tpl: def_days = 7
                            elif "Msg 6" in tpl: def_days = 30
                            
                            auto_date = datetime.now() + timedelta(days=def_days)
                            auto_str = auto_date.strftime("%Y-%m-%d")
                            
                            # UI: Show Auto, allow Manual
                            use_manual = st.checkbox("Change Date (Manual)?", value=False)
                            
                            if use_manual:
                                final_date_obj = st.date_input("Select Custom Date", value=auto_date)
                                final_date = final_date_obj.strftime("%Y-%m-%d")
                            else:
                                st.info(f"📅 Auto-Schedule: **{auto_str}** (+{def_days} days)")
                                final_date = auto_str
                        
                        with col_d2:
                            st.write("") # Spacer
                            st.write("") 
                            if st.button("Mark as Sent & Schedule"):
                                # 2. Update DB using decided date
                                db.update_lead_status(lead['id'], "Active", final_date)
                            
                                st.balloons()
                                st.success(f"Message Logged! 📅 Moved lead to {next_date} on the Calendar.")
                                time.sleep(2)
                                st.rerun()
                    
                    else:
                        st.subheader("Coach Mode")
                        reply = st.text_input("Paste Reply:")
                        
                        # Default keys
                        detected_key = "fallback"
                        
                        if reply:
                            detected_key = handle_objection(reply)
                            st.caption(f"Detected Intent: {detected_key.title()}")
                            
                        # Manual Override
                        options = list(OBJECTION_SCRIPTS.keys()) + ["fallback"]
                        
                        # Handle fallback text logic
                        fallback_text = "I see. Could you clarify if the hesitation is around timing or the concept itself? (Generic fallback)"
                        
                        # Try to find index of detected key
                        try:
                            idx = options.index(detected_key)
                        except:
                            idx = len(options) - 1
                            
                        selected_type = st.selectbox("Response Strategy", options, index=idx)
                        
                        # Get content
                        if selected_type == "fallback":
                            final_script = fallback_text
                        else:
                            final_script = OBJECTION_SCRIPTS.get(selected_type, fallback_text)
                            
                        st.info("Suggested Reply:")
                        st.code(final_script, language=None)
                        
                        st.divider()
                        st.subheader("📅 Manual Reschedule")
                        st.caption("If they are busy, on holiday, or ask for a specific date:")
                        
                        col_r1, col_r2 = st.columns([2, 1])
                        manual_date = col_r1.date_input("Select Next Action Date", value=datetime.now() + timedelta(days=7))
                        
                        if col_r2.button("Update Schedule"):
                             m_date_str = manual_date.strftime("%Y-%m-%d")
                             db.update_lead_status(lead['id'], "Active", m_date_str)
                             st.success(f"Rescheduled for {m_date_str}!")
                             time.sleep(1)
                             st.rerun()

            # --- STAGE 2: DISCOVERY CALL ---
            elif stage == "2. Discovery Call":
                st.subheader("📞 Call Script & Notes")
                
                with st.expander("1️⃣ The Intro (Loose Script)", expanded=True):
                    st.markdown(f"""
                    *"Hi [Name], thanks for taking the time to speak."*
                    
                    *"As I mentioned, I’m not calling to ask for money today. I’m currently finalizing my partners for the [Championship Name] season, and I’m looking for a {lead['Sector']} partner to align with."*
                    
                    *"Before I send any proposals, I want to make sure I’m not wasting your time. I’d love to ask a few quick questions to see if there's actually a fit with what we do. Is that okay?"*
                    """)
                
                st.divider()
                st.subheader("2️⃣ The Discovery Questions")
                
                # Load existing notes
                existing_notes = lead.get('Notes', {})
                
                with st.form("discovery_form"):
                    answers = {}
                    for q in DISCOVERY_QUESTIONS:
                        qid = q.split(".")[0] # "1", "2" etc
                        q_text = q.split(".", 1)[1].strip()
                        # Pre-fill
                        val = existing_notes.get(f"Q{qid}", "")
                        answers[f"Q{qid}"] = st.text_area(f"{q_text}", value=val, height=70)
                    
                    st.divider()
                    st.markdown("**3️⃣ Closing the Call**")
                    st.markdown("""
                    *"That’s really helpful, thanks. Based on what you’ve said about [Goal], I actually think we could do something quite interesting around [Idea]."*
                    
                    *"I’m going to put together a specific 1-page proposal for you. I’ll send it over on Tuesday. When would be the best time to run through it for 10 minutes?"*
                    """)
                    
                    if st.form_submit_button("💾 Save Call Notes"):
                        # Save to DB
                        existing_notes.update(answers) # Merge
                        db.update_lead_notes(lead['id'], existing_notes)
                        st.success("Notes saved to database!")

                        
                if st.button("Mark Call Complete"):
                     # Move to Proposal Stage logically
                     st.info("Call Logged. Move to 'Proposal' stage to generate your deck.")

                
            elif stage == "3. Proposal":
                st.subheader("📝 Generate 'Manus.im' Proposal Prompt")
                st.info("Fill in the specific gaps below. The app will combine this with your Profile & Research to write a full slide-deck prompt.")
                
                # 1. GATHER GAPS
                with st.form("proposal_gaps"):
                    col_p1, col_p2 = st.columns(2)
                    
                    with col_p1:
                        prop_hook = st.text_area("The 'Hook' (Why them?)", 
                                               value=f"Given {lead['Business Name']}'s work in {lead.get('Sector', 'their sector')}, our audience matches their target market of...",
                                               help="Specific reason why this partnership makes sense.", height=100)
                        
                        prop_ask = st.text_input("Proposed Investment / Level", value="Title Sponsor (£5,000)", help="Rough ballpark or package name")
                        
                    with col_p2:
                        prop_ideas = st.text_area("3 Activation Ideas (What will we do?)", 
                                                value="1. Branding on bike fairing.\n2. Social media product showcase video.\n3. VIP tickets for their clients.",
                                                height=100)
                        
                        prop_tone = st.selectbox("Tone", ["Professional & Corporate", "Exciting & High Energy", "Personal & Story-Driven"])

                    if st.form_submit_button("✨ Generate Manus Prompt"):
                        # 2. CONSTRUCT PROMPT ("Winning Formula" - JK66 Style)
                        
                        # Data Mapping
                        r_name = st.session_state.user_name
                        r_series = championship
                        r_bio = st.session_state.user_profile.get('bio', f"A competitive racer in {r_series}")
                        r_audience = f"{st.session_state.user_profile.get('social_following', 'Growing')} Followers"
                        
                        l_name = lead['Business Name']
                        l_notes = lead.get('Notes', {})
                        
                        # Discovery Context (Formatted)
                        disc_context = "**Deep Discovery Findings (Client Voice):**\n"
                        has_answers = False
                        
                        # Map Q1..Q6 to text
                        for i, question_text in enumerate(DISCOVERY_QUESTIONS):
                            key = f"Q{i+1}"
                            answer = l_notes.get(key, "").strip()
                            if answer:
                                has_answers = True
                                disc_context += f"- **Issue/Goal ({key}):** {question_text}\n  - **Client Said:** \"{answer}\"\n"
                        
                        if not has_answers:
                            disc_context += "(⚠️ NO DISCOVERY DATA LOGGED. This proposal will be generic. Go back to 'Discovery Call' to log answers.)"
                            st.warning("⚠️ You haven't logged any Discovery Call answers. The proposal might lack specific client details.")
                        
                        manus_prompt = f"""
Create a high-impact 10-slide sponsorship deck for '{r_name}' (Motorsport Athlete) pitching to '{l_name}'.
**Style Ref:** MODELED ON JOEL KELSO 'JK66' PRESENTATION. Professional, Data-Heavy, ROI-Focused.

**Context:**
- **Rider:** {r_name} ({r_series}). Values: Speed, Precision, Trust.
- **Audience:** {r_audience}, High disposable income, petrolheads.
- **Prospect:** {l_name} (Sector: {lead.get('Sector')}). Context: {disc_context}
- **Tone:** {prop_tone}.

---
**Structure (Slide by Slide):**

**Slide 1: Title**
- **Text:** {r_name} x {l_name} | Partnership Proposal {datetime.now().year}
- **Visual:** [IMAGE: Cinematic headshot of {r_name} in full race gear, helmet off, looking impactful.]

**Slide 2: The Athlete (Who is {r_name}?)**
- **Content:** {r_bio}
- **Highlights:** List key recent race results (Podiums, Wins) as bullet points.
- **Visual:** [IMAGE: Action shot on track, knee down, blurring background for speed.]

**Slide 3: Brand Ambassador Credibility**
- **Headline:** Trusted by Global Brands
- **Content:** "Representing excellence. Professional, approachable, and media-savvy."
- **Visual:** [IMAGE: {r_name} giving a TV interview or shaking hands with a VIP/Team Manager. Logos of current partners if known.]

**Slide 4: The Audience & Reach**
- **Headline:** Engaging a Passionate Fanbase
- **Data:** {r_audience}. Demographics: 70% Male, 25-45 age group (Estimate). 
- **Visual:** [CHART: Minimalist bar chart showing growth. IMAGE: Crowds at the track.]

**Slide 5: Broadcast Power (The Platform)**
- **Headline:** Global Visibility
- **Content:** "TV Coverage on Eurosport/TNT/Local Channel. Live Streaming. Social Media Clips."
- **Visual:** [IMAGE: Screenshot of a TV broadcast overlay or a 'Live' camera icon over a track shot.]

**Slide 6: Why {l_name}? (The Alignment)**
- **Headline:** shared Vision
- **Content:** {prop_hook}
- **Visual:** [IMAGE: Split screen - {r_name} Action Left | {l_name} Logo/Storefront Right.]

**Slide 7: Activation Strategy (ROI)**
- **Headline:** Driving Return on Investment
- **Bullet Points:**
{prop_ideas}
- **Visual:** [IMAGE: Lifestyle photo of {r_name} using a product or interacting with fans.]

**Slide 8: Brand Visibility (The Assets)**
- **Headline:** Your Brand on the Grid
- **List:** Bike Branding, Leathers, Helmet, Garage Walls, Transporter.
- **Visual:** [IMAGE: A clear mockup of the bike/car with '{l_name}' logo placed on the main side panel.]

**Slide 9: The Investment Package**
- **Headline:** {prop_ask}
- **Content:** Full Title Rights, VIP Hospitality Passes, Content Days, Social Media Access.
- **Visual:** [IMAGE: Premium paddock pass or hospitality view.]

**Slide 10: Next Steps**
- **Headline:** Let's Race Together
- **Call to Action:** Meeting to finalize.
- **Contact:** {st.session_state.user_email}
- **Visual:** [IMAGE: 'Thank You' text over a high-contrast image of the finish line flag.]
"""
                        st.success("✨ 'Winning Formula' Prompt Generated! (JK66 Style)")
                        st.code(manus_prompt, language=None)
                        
                        st.divider()
                        st.markdown("### 📧 Send to Team")
                        st.caption("1. Click the 'Copy' icon on the code block above.")
                        st.caption("2. Click the button below to open your email.")
                        st.caption("3. Paste the prompt into the email body.")
                        
                        subject = urllib.parse.quote(f"Manus Proposal Framework: {r_name} x {l_name}")
                        mailto = f"mailto:team@caminocoaching.co.uk?subject={subject}&body=(Paste%20Manus%20Prompt%20Here)"
                        st.link_button("📤 Open Email to team@caminocoaching.co.uk", mailto)
                        
                        st.caption("🚀 Or go to https://manus.im/app and paste directly.")

    else:
        st.info("👈 Go to Dashboard or Search to select a lead.")
