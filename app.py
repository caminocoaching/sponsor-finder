import streamlit as st
import pandas as pd
import time
import random
from datetime import datetime, timedelta
import urllib.parse
import db_manager as db
from search_service import mock_search_places, search_google_places

# --- CONFIGURATION ---
st.set_page_config(page_title="Sponsor Finder", page_icon="🏍️", layout="wide")

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
    "1. What are your main marketing goals for this year?",
    "2. Who is your ideal customer profile?",
    "3. What geographical areas do you need more visibility in?",
    "4. Have you sponsored sports or events before? How did it go?",
    "5. What does 'success' look like for a partnership like this?",
    "6. What is your typical budget range for local brand activation?"
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
        
        if st.button("Sign In / Sign Up", type="primary"):
            if email_input and "@" in email_input and name_input:
                user = db.get_user_by_email(email_input)
                if user:
                    # User exists - Log in
                    st.session_state.user_id = user['id']
                    st.success(f"Welcome back, {user['name']}!")
                    st.rerun()
                else:
                    # Create new user with provided Name
                    uid = db.save_user_profile(email_input, name_input, {"email": email_input, "onboarding_complete": False})
                    st.session_state.user_id = uid
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
                "tv_reach": tv_reach, # Save the new field
                "tv": tv_reach, # Legacy mapping for templates
                "location": f"{user_town}, {user_state}, {user_country}, {user_zip}".strip(", "),
                "town": user_town, 
                "state": user_state,
                "zip_code": user_zip,
                "country": user_country, # Ensure country is explicitly saved if strictly needed by other logic, though it's in location
                "onboarding_complete": True
            })
            
            db.save_user_profile(user_data['email'], full_name, profile_update)
            st.success("Profile Saved! Loading Dashboard...")
            st.rerun()
        else:
            st.error(f"Please fill in the following: {', '.join(missing)}")

# LOGIC FLOW
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
                    df = pd.read_csv(f_audit)
                    tot, _ = extract_audit_stats(df)
                    user_profile['followers_count'] = tot
                    user_profile['audience'] = f"{tot} (Social)"
                
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
    search_mode = st.radio("Mode", ["Sector Search", "Find Previous Sponsors"])
    
    location_search_ctx = ", ".join([p for p in [saved_town, saved_state, saved_country, saved_zip] if p])
    if not location_search_ctx:
        location_search_ctx = "Silverstone, UK" # Fallback
    
    if search_mode == "Sector Search":
        selected_sector = st.selectbox("Target Sector", SECTORS)
        if selected_sector == "Other (type your own)":
            search_query = st.text_input("Enter key words")
        else:
            search_query = selected_sector
    else:
        search_query = "Previous Motorsports Sponsors"

    st.markdown("---")
    st.markdown("---")
    with st.expander("⚙️ Settings (Premium Features)"):
        # Load saved key
        saved_key = st.session_state.user_profile.get("google_api_key", "")
        
        google_api_key = st.text_input("Google Places API Key", value=saved_key, type="password", help="Needed for real map results.")
        
        if google_api_key != saved_key:
            # Save to Profile logic
            st.session_state.user_profile["google_api_key"] = google_api_key
            # Persist
            db.save_user_profile(st.session_state.user_email, st.session_state.user_name, st.session_state.user_profile)
            st.toast("API Key Saved! It is now locked in.")
            
        st.caption("Enter your key once to unlock Real Search for all future sessions.")


# Main Content - TABS
# Main Content - TABS
# Workflow: 1. Search -> 2. Outreach -> 3. Manage
tab_search, tab_outreach, tab_dash = st.tabs([" Search & Add", "✉️ Outreach Assistant", "📊 Active Campaign"])

# STATE MANAGEMENT
if 'leads' not in st.session_state:
    st.session_state.leads = pd.DataFrame() # Temporary search results
if 'selected_lead_id' not in st.session_state:
    st.session_state.selected_lead_id = None

# TAB 3: DASHBOARD (Active Campaign) - Moved to end
with tab_dash:
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
        
        # 2. Metrics Row
        m1, m2, m3 = st.columns(3)
        m1.metric("⚠️ Action Required", f"{num_due} Leads", delta="Due Now" if num_due > 0 else "All Good", delta_color="inverse")
        m2.metric("🔥 Active Pipeline", f"{num_active} Leads")
        m3.metric("🏆 Secured Deals", f"{num_secured} Sponsors")
        
        st.divider()
        
        # 3. Priority List (If any due)
        if num_due > 0:
            st.warning(f"You have {num_due} leads that need attention today!")
            st.caption("👇 Prioritize these:")
            st.dataframe(due_leads[["Business Name", "Status", "Next Action"]], use_container_width=True, hide_index=True)
            st.divider()

        # 4. Main Table (Sortable)
        st.subheader("All Leads")
        
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
        
        # Lead Picker for Outreach
        lead_choice = st.selectbox("Select Lead to Manage", df_leads["Business Name"].tolist(), key="dash_picker")
        
        # Find ID
        lid = df_leads[df_leads["Business Name"] == lead_choice].iloc[0]["id"]
        
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            if st.button("➡️ Message / Manage", type="primary"):
                st.session_state.selected_lead_id = lid
                st.success(f"Loaded {lead_choice}. Click 'Outreach Assistant' tab.")

        
        with c2:
            if st.button("🔄 Set Active"):
                db.update_lead_status(lid, "Active")
                st.toast(f"{lead_choice} is now Active!")
                time.sleep(1)
                st.rerun()
                
        with c3:
            if st.button("✅ Set Secured"):
                db.update_lead_status(lid, "Secured")
                st.balloons()
                st.toast(f"Congrats on securing {lead_choice}!")
                time.sleep(1)
                st.rerun()
                
        with c4:
            if st.button("❌ Not a Fit (Delete)"):
                db.delete_lead(lid)
                st.toast(f"Removed {lead_choice}.")
                time.sleep(1)
                st.rerun()


# TAB 1: SEARCH (DISCOVERY)
with tab_search:
    st.subheader(f"Find {search_query} within {search_radius} miles of {location_search_ctx}")
    
    if st.button("Run Search", type="primary"):
        with st.spinner("Scanning Area..."):
            if google_api_key:
                # REAL SEARCH
                results = search_google_places(google_api_key, search_query, location_search_ctx, search_radius)
                if isinstance(results, dict) and "error" in results:
                    st.error(f"Google API Error: {results['error']}")
                    results = [] # Fallback or empty
                elif not results:
                    st.warning("No results found via Google. Try a wider radius.")
            else:
                # MOCK SEARCH
                mode_arg = "previous" if search_mode == "Find Previous Sponsors" else "sector"
                results = mock_search_places(location_search_ctx, search_radius, search_query, mode=mode_arg)
                st.info("ℹ️ Using Demo Mode (Random Results). Add an API Key in Sidebar settings for real data.")
                
        st.session_state.leads = pd.DataFrame(results)
        st.success(f"Found {len(results)} potential targets!")

    if not st.session_state.leads.empty:
        # MAP DISPLAY (If lat/lon ok)
        if "lat" in st.session_state.leads.columns:
             st.map(st.session_state.leads)
             
        # Show Website in table
        disp_cols = ["Business Name", "Address", "Sector", "Rating"]
        if "Website" in st.session_state.leads.columns:
            disp_cols.insert(2, "Website")
            
        st.dataframe(
             st.session_state.leads[disp_cols],
             use_container_width=True
        )

        
        # Add to DB Logic
        col_s1, col_s2 = st.columns([3, 1])
        with col_s1:
            add_choice = st.selectbox("Select result to track", st.session_state.leads["Business Name"].unique())
        with col_s2:
            if st.button("➕ Add to My Leads"):
                # Get full row
                row = st.session_state.leads[st.session_state.leads["Business Name"] == add_choice].iloc[0]
                
                # Extract fields safely
                b_name = row["Business Name"]
                b_sect = row["Sector"]
                b_loc = row["Address"]
                b_web = row.get("Website", "") # Safe get
                
                # Pass explicit args to match db_manager signature
                if db.add_lead(st.session_state.user_id, b_name, b_sect, b_loc, website=b_web):
                    st.toast(f"Added {add_choice} to Dashboard!")
                else:
                    st.warning("Already in your list.")

# TAB 2: OUTREACH
# TAB 2: OUTREACH
with tab_outreach:
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
                    website_url = lead.get('website', '')
                    domain = ""
                    if website_url:
                        # Simple strip to get domain.com
                        domain = website_url.replace("https://", "").replace("http://", "").replace("www.", "").strip("/")
                        domain = domain.split("/")[0] # Just the root domain
                    
                    st.info(f"Targeting: **{lead['Business Name']}**" + (f" (`{domain}`)" if domain else ""))
                    
                    # PILLAR 1: THE WEB DOCTRINE
                    with st.expander("1️⃣ The Web (Deep Dive)", expanded=True):
                        if domain:
                            # Site Search
                            q_site = f'site:{domain} "sponsorship" OR "partners"'
                            u_site = f"https://www.google.com/search?q={urllib.parse.quote_plus(q_site)}"
                            st.markdown(f"• [**Internal Site Search**]({u_site})")
                            
                            # Filetype PDF
                            q_pdf = f'site:{domain} filetype:pdf'
                            u_pdf = f"https://www.google.com/search?q={urllib.parse.quote_plus(q_pdf)}"
                            st.markdown(f"• [**Find Internal PDFs (Reports)**]({u_pdf})")
                            
                            # Competitors
                            q_rel = f'related:{domain}'
                            u_rel = f"https://www.google.com/search?q={urllib.parse.quote_plus(q_rel)}"
                            st.markdown(f"• [**Find Competitors**]({u_rel})")
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
                        
                        ai_prompt = f"""Act as a professional sponsorship acquisition agent. I need a deep-dive research briefing on the company "{lead['Business Name']}" (Sector: {lead.get('Sector', 'Unknown')}).

Please provide a structured report covering:
1. **Corporate Overview**: What are their primary products/services and current brand positioning?
2. **Sponsorship History**: Have they sponsored motorsports, athletes, or events before? If yes, list details.
3. **Recent News & Financials**: Any recent mergers, product launches, or financial milestones in the last 12 months?
4. **Key People (LinkedIn)**: Identify 3 key decision-makers likely responsible for partnerships (e.g., Marketing Director, Brand Manager, CEO). Format as: Name - Role - LinkedIn URL (if guessable).

Format the output as a clean briefing document I can read in 2 minutes."""
                        
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
                        
                        if st.button("Mark as Sent"):
                            # Logic to update Status -> Contacted
                            # Logic to set Next Action -> Today + 2 days
                            st.success("Lead updated! Check Dashboard for follow-up.")
                    
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
                st.info("Generate Proposal")

    else:
        st.info("👈 Go to Dashboard or Search to select a lead.")
