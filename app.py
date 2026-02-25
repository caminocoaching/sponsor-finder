import streamlit as st
import pandas as pd
import time
import random
from datetime import datetime, timedelta
import urllib.parse
import db_manager as db
import facebook_finder as fb_finder
import json
from search_service import mock_search_places, search_google_places, search_google_legacy_nearby, search_outscraper
from sheets_manager import sheet_manager
from airtable_manager import airtable_manager
from enrichment_service import search_apollo_people, search_outscraper_contacts, extract_domain, find_linkedin_company_page, search_companies_house
from streamlit_calendar import calendar

# --- CONFIGURATION ---
# Last System Update: Force Reload
st.set_page_config(page_title="Sponsor Finder V2.5", page_icon="🏍️", layout="wide")

# Initialize DB
db.init_db()

# --- DATA & CONSTANTS ---
SECTORS = [
    "in your industry sector",
    # --- ENDEMIC (closest to motorsport) ---
    "Motorcycle dealers",
    "Motorcycle parts & accessories",
    "Automotive aftermarket",
    "Accident management & vehicle services",
    # --- ENGINEERING & INDUSTRIAL ---
    "Engineering & manufacturing",
    "Transport & haulage",
    "Logistics",
    "Building supplies & construction",
    # --- HIGH-VALUE NON-ENDEMIC (PDF sectors) ---
    "Enterprise AI & SaaS",
    "Online gaming & casinos",
    "Green tech & renewable energy",
    "Fintech & digital banking",
    "Luxury goods & lifestyle",
    # --- SERVICE / LOCAL ---
    "Food & beverage brands",
    "Craft brewery & distillery",
    "Insurance companies",
    "Financial services & wealth management",
    "Property & real estate",
    "Legal services",
    "Recruitment & staffing",
    "Fitness & wellness",
    "Printers & signage",
    # --- DISCOVERY ---
    "Companies already sponsoring motorsport",
    "Fast-growing local businesses",
    "Other (type your own)"
]

SECTOR_HOOKS = {
    "Construction": "building a legacy and solid foundations",
    "Building": "building a legacy and solid foundations",
    "Engineering": "precision, performance, and technical excellence",
    "Transport": "logistics, speed, and moving forward",
    "Motorcycle": "passion for the sport and the machine",
    "Automotive": "performance, engineering and the thrill of the track",
    "Accident": "safety, recovery, and getting back on track",
    "Food": "fueling performance and great taste",
    "Craft": "craftsmanship, quality and local pride",
    "Financial": "calculated risk and high rewards",
    "Fintech": "innovation, trust and global ambition",
    "Logistics": "delivering results on time, every time",
    "Insurance": "protection and peace of mind at high speed",
    "Tech": "innovation and data-driven performance",
    "Enterprise": "pushing the boundaries of what technology can do",
    "Gaming": "adrenaline, competition and the thrill of the win",
    "Green": "sustainable innovation and a cleaner future",
    "Luxury": "exclusivity, prestige and premium experiences",
    "Property": "building value and long-term investment",
    "Legal": "precision, strategy and winning results",
    "Recruitment": "finding the best talent and backing winners",
    "Fitness": "peak performance, discipline and pushing limits",
    "Printers": "visibility, branding and making an impact",
    "Fast-growing": "ambition, momentum and standing out from the crowd",
    "Companies already": "proven belief in motorsport as a marketing platform",
    "Other": "excellence and high performance"
}

# [NEW] Optimized Search Queries for Google Places API
# Maps the user-friendly dropdown name to a LIST of terms to search in parallel
SECTOR_SEARCH_OPTIMIZATIONS = {
    # --- ENDEMIC ---
    "Motorcycle dealers": ["Motorcycle Dealer", "Bike shop", "Motorcycle repair"],
    "Motorcycle parts & accessories": ["Motorcycle parts store", "Motorcycle accessories"],
    "Automotive aftermarket": ["Car parts supplier", "Auto accessories", "Performance parts", "Vehicle wrapping"],
    "Accident management & vehicle services": ["Vehicle repair", "Car body shop", "Accident management", "Garage services"],
    # --- INDUSTRIAL ---
    "Engineering & manufacturing": ["Engineering companies", "Manufacturing plant", "Precision engineering", "Fabrication"],
    "Transport & haulage": ["Haulage companies", "Logistics companies", "Freight forwarding service"],
    "Logistics": ["Logistics service", "Freight forwarding", "Warehousing"],
    "Building supplies & construction": ["Building materials supplier", "Builders merchant", "Timber merchant", "Construction company"],
    # --- HIGH-VALUE NON-ENDEMIC ---
    "Enterprise AI & SaaS": ["Software company", "IT services company", "Technology consulting", "SaaS company"],
    "Online gaming & casinos": ["Online casino", "Gaming company", "Betting company", "Esports"],
    "Green tech & renewable energy": ["Solar panel installer", "Renewable energy company", "Electric vehicle charging", "Environmental services"],
    "Fintech & digital banking": ["Fintech", "Payment processing", "Digital bank", "Cryptocurrency exchange"],
    "Luxury goods & lifestyle": ["Luxury watch retailer", "Premium car dealer", "Private members club", "Luxury brand"],
    # --- SERVICE / LOCAL ---
    "Food & beverage brands": ["Food manufacturer", "Drink manufacturer", "Wholesale food", "Energy drink"],
    "Craft brewery & distillery": ["Craft brewery", "Microbrewery", "Distillery", "Gin distillery"],
    "Insurance companies": ["Commercial Insurance", "Insurance Broker", "Business Insurance"],
    "Financial services & wealth management": ["Wealth management", "Corporate finance", "Investment service", "Financial advisor"],
    "Property & real estate": ["Estate agent", "Property developer", "Commercial property", "Property investment"],
    "Legal services": ["Law firm", "Solicitor", "Corporate lawyer", "Commercial law firm"],
    "Recruitment & staffing": ["Recruitment agency", "Staffing agency", "Executive recruitment", "HR consulting"],
    "Fitness & wellness": ["Gym", "Personal trainer", "Sports nutrition", "Fitness brand"],
    "Printers & signage": ["Commercial Printer", "Print shop", "Sign maker", "Vehicle graphics"],
    # --- DISCOVERY MODES ---
    "Companies already sponsoring motorsport": ["Motorsport sponsor", "Racing team sponsor", "Motorcycle racing sponsor"],
    "Fast-growing local businesses": ["Award winning business", "Business of the year", "Fast growing company"],
}

DISCOVERY_QUESTIONS = {
    "past_experience": "Have you been involved in sponsorship before — motorsport or otherwise?",
    "ideal_outcome": "If we worked together and it went really well, what would success look like for you?",
    "important_elements": "What would be the most important elements of a partnership for you?",
    "staff_angle": "Could your team or staff benefit from being part of something like this?",
    "customer_angle": "What about your customers — could they benefit from this partnership?",
    "local_activation": "We have a round at [nearest circuit] — anything you'd want to do around that?",
    "budget_signals": "Any budget or timing signals mentioned during the call?"
}

DISCOVERY_PROBES = {
    "past_experience": {
        "yes": "How did that go? What did you get out of it?",
        "no": "Is there a reason it's not been on your radar, or just never come up?"
    },
    "ideal_outcome": {
        "probe": "Is that more about new customers, brand visibility, staff engagement, entertaining clients — or a mix?"
    },
    "important_elements": {
        "examples": "Logo on the bike/kit, event hospitality, social media mentions, B2B paddock introductions, customer competitions, staff experiences"
    },
    "staff_angle": {
        "yes": "What kind of thing would they get most excited about?"
    },
    "customer_angle": {
        "yes": "Tell me more — what kind of customers are you thinking of?"
    }
}

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

@st.dialog("Contact Card", width="large")
def calendar_contact_card(lead_id):
    """Opens a contact card with the current message stage, reply handler, and profile URL."""
    # Load lead data
    leads = db.get_leads(st.session_state.user_id)
    lead = None
    for l in leads:
        if l['id'] == lead_id:
            lead = l
            break
    
    if not lead:
        st.error("Contact not found.")
        return
    
    # Load user profile context
    user_data_card = db.get_user_profile(st.session_state.user_id)
    user_profile_card = user_data_card.get('profile', {})
    rider_name_card = user_data_card['name']
    town_card = user_profile_card.get('town', '')
    championship_card = user_profile_card.get('championship', 'Unknown')
    
    ctx = {
        "goal": user_profile_card.get('goal', ''),
        "prev_champ": user_profile_card.get('prev_champ', ''),
        "achievements": user_profile_card.get('achievements', ''),
        "audience": user_profile_card.get('audience', ''),
        "tv": user_profile_card.get('tv', '') if user_profile_card.get('televised') == "Yes" else "N/A",
        "team": user_profile_card.get('team', ''),
        "rep_mode": user_profile_card.get("rep_mode", False),
        "rep_name": user_profile_card.get("rep_name", ""),
        "rep_role": user_profile_card.get("rep_role", "")
    }
    
    # Parse notes
    lead_notes = lead.get('Notes', {})
    if isinstance(lead_notes, str):
        try: lead_notes = json.loads(lead_notes)
        except: lead_notes = {}
    if not isinstance(lead_notes, dict): lead_notes = {}
    
    contact_name = lead.get('Contact Name', '') or ''
    contact_url = lead_notes.get('contact_url', '')
    salutation = lead_notes.get('salutation', 'Mr')
    
    # Determine current sequence step
    seq_options = [
        "LI Connect: Request",
        "Email: Cold Opener",
        "LI Msg 1: Intro (Day 2)",
        "LI Msg 2: Homework (Day 7)",
        "LI Msg 3: Momentum (Day 14)",
        "LI Msg 4: Scarcity (Day 21)",
        "LI Msg 5: Final (Day 28)"
    ]
    
    last_sent_step = lead_notes.get('outreach_step', -1)
    try: last_sent_step = int(last_sent_step)
    except: last_sent_step = -1
    current_step_idx = min(last_sent_step + 1, len(seq_options) - 1)
    if current_step_idx < 0: current_step_idx = 0
    
    is_sequence_done = last_sent_step >= len(seq_options) - 1
    
    # --- HEADER ---
    st.markdown(f"### {contact_name or lead['Business Name']}")
    head_c1, head_c2 = st.columns([2, 1])
    with head_c1:
        st.caption(f"🏢 {lead['Business Name']}  •  {lead.get('Sector', '')}")
        if is_sequence_done:
            st.success("✅ Full sequence complete")
        else:
            st.info(f"📍 Stage: **{seq_options[current_step_idx]}**")
    with head_c2:
        st.caption(f"Status: **{lead.get('Status', 'Pipeline')}**")
        if lead.get('Next Action'):
            st.caption(f"📅 Follow-up: {lead.get('Next Action', '')}")
    
    # --- PROFILE URL ---
    if contact_url:
        st.markdown(f"🔗 **[Open Profile → Message Now]({contact_url})**")
    else:
        st.caption("⚠️ No profile URL saved — add one in the Outreach Assistant")
    
    st.divider()
    
    # --- TAB: Message / Reply ---
    card_tab = st.radio("Mode", ["Draft Message", "Handle Reply"], horizontal=True, key=f"card_mode_{lead_id}")
    
    if card_tab == "Draft Message" and not is_sequence_done:
        current_template = seq_options[current_step_idx]
        
        # Generate the message
        draft = generate_message(
            current_template, lead['Business Name'], rider_name_card, lead.get('Sector', ''),
            town=town_card, championship=championship_card, extra_context=ctx,
            contact_name=contact_name, salutation=salutation
        )
        
        final_msg = st.text_area("Message:", value=draft, height=200, key=f"card_msg_{lead_id}")
        
        st.caption("👇 Click the Copy icon in the top right of the box below")
        st.code(final_msg, language=None)
        
        # Schedule next follow-up
        def_days = 2
        if "Connect" in current_template: def_days = 2
        elif "Msg 1" in current_template: def_days = 5
        elif "Msg 2" in current_template: def_days = 7
        elif "Msg 3" in current_template: def_days = 7
        elif "Msg 4" in current_template: def_days = 7
        elif "Msg 5" in current_template: def_days = 30
        
        auto_date = datetime.now() + timedelta(days=def_days)
        
        fc1, fc2 = st.columns([2, 1])
        with fc1:
            use_manual_cal = st.checkbox("Change follow-up date?", value=False, key=f"card_manual_{lead_id}")
            if use_manual_cal:
                final_date_obj = st.date_input("Follow-up date", value=auto_date, key=f"card_date_{lead_id}")
                final_date = final_date_obj.strftime("%Y-%m-%d")
            else:
                final_date = auto_date.strftime("%Y-%m-%d")
                st.caption(f"📅 Next follow-up: **{final_date}** (+{def_days} days)")
        
        with fc2:
            st.write("")
            if st.button("✅ Sent & Scheduled", type="primary", key=f"card_sent_{lead_id}"):
                st.balloons()
                
                # Update status
                db.update_lead_status(lead_id, "Active", final_date)
                
                # Update notes with step + salutation + URL
                lead_notes['outreach_step'] = current_step_idx
                lead_notes['last_template'] = current_template
                lead_notes['salutation'] = salutation
                if contact_url:
                    lead_notes['contact_url'] = contact_url
                db.update_lead_notes(lead_id, lead_notes)
                
                st.success(f"🎉 Done! Next follow-up: {final_date}")
                time.sleep(2)
                st.rerun()
    
    elif card_tab == "Draft Message" and is_sequence_done:
        st.info("🏁 You’ve completed the full 6-message sequence with this contact.")
        st.markdown("**Next steps:**")
        st.markdown("- Schedule a discovery call")
        st.markdown("- Move to Proposal stage")
        st.markdown("- Or mark as Not Interested")
        
        fc1, fc2, fc3, fc4 = st.columns(4)
        with fc1:
            if st.button("📅 Call Booked", key=f"card_call_{lead_id}"):
                db.update_lead_status(lead_id, "Call Booked")
                st.rerun()
        with fc2:
            if st.button("📞 Discovery Call", key=f"card_disc_{lead_id}"):
                db.update_lead_status(lead_id, "Discovery Call")
                st.rerun()
        with fc3:
            if st.button("📋 Proposal", key=f"card_prop_{lead_id}"):
                db.update_lead_status(lead_id, "Proposal")
                st.rerun()
        with fc4:
            if st.button("❌ Not Interested", key=f"card_ni_{lead_id}"):
                db.update_lead_status(lead_id, "Not Interested")
                st.rerun()
    
    else:
        # Handle Reply mode
        st.subheader("Coach Mode")
        reply = st.text_input("Paste their reply:", key=f"card_reply_{lead_id}")
        
        detected_key = "fallback"
        if reply:
            detected_key = handle_objection(reply)
            st.caption(f"Detected Intent: {detected_key.title()}")
        
        options = list(OBJECTION_SCRIPTS.keys()) + ["fallback"]
        try: idx = options.index(detected_key)
        except: idx = len(options) - 1
        
        selected_type = st.selectbox("Response Strategy", options, index=idx, key=f"card_strat_{lead_id}")
        
        fallback_text = "I see. Could you clarify if the hesitation is around timing or the concept itself?"
        if selected_type == "fallback":
            final_script = fallback_text
        else:
            final_script = OBJECTION_SCRIPTS.get(selected_type, fallback_text)
        
        st.info("✏️ Edit your reply below, then copy:")
        edited_reply = st.text_area("Edit reply:", value=final_script, height=150, key=f"card_edit_reply_{lead_id}")
        st.caption("👇 Copy from here:")
        st.code(edited_reply, language=None)

TEMPLATES = {
    "Email: Cold Opener": """Good morning [Contact Name],

My name is [Rider Name] and I am based in [Town], close to your area.

I am racing this season in the [Championship Name] and I am reaching out to a small number of local businesses in [Sector Hook] who could benefit from what we are building.

The reason I chose [Business Name] specifically: companies in your space are starting to use motorsport as a platform to stand out, build loyalty, and get in front of [Audience Size]+ engaged fans per event. Most of them started with a single conversation.

I am not sending a pitch. I would love to have a quick 10-minute discovery call to understand what [Business Name] is working toward this year and whether there is even a fit worth exploring.

No commitment. No pressure. Just a conversation between two local businesses.

Best regards,
[Rider Name]""",

    "LI Connect: Request": """Hi [Contact Name], great to connect with you on here. Being local to [Town], it would be great to connect and see if there is a mutual benefit for us both this year.""",

    "LI Msg 1: Intro (Day 2)": """[Contact Name], appreciate the connection.

Quick intro: I compete in the [Championship Name] this season. [Audience Size]+ fans per event, live coverage, and a strong local following.

I have been connecting with businesses in [Sector Hook] because there is a real opportunity for the right partner to own that space in the motorsport world before your competitors do.

Not pitching anything. Genuinely curious, has [Business Name] ever explored using sport as a marketing channel?

[Rider Name]""",

    "LI Msg 2: Homework (Day 7)": """Hi [Contact Name],

I have been doing some homework on [Business Name] and I can see you are doing impressive things in [Sector Hook].

The reason I am reaching out: I am racing in [Championship Name] this season, and our partners do not just get a logo on a car. They get:

- Their brand in front of [Audience Size]+ engaged fans per event
- VIP hospitality they can use as a client incentive or team reward
- Content and stories they can use across their own marketing

I noticed your competitors are not doing this yet. That is exactly why the timing is right.

Would 10 minutes be worth exploring whether there is a fit?

[Rider Name]""",

    "LI Msg 3: Momentum (Day 14)": """[Contact Name],

Quick update. I am deep into pre-season preparation for [Championship Name] and we are locking in the final partnership spots.

Last season in [Previous Champ]: [Achievements]. This year the goal is [Season Goal].

I keep coming back to [Business Name] because I genuinely think there is a strong alignment. Here is what forward-thinking [Sector] businesses are doing with motorsport:

1. Using race days as client hospitality, it beats a round of golf every time
2. Getting exclusive content for their marketing, behind-the-scenes, race day stories
3. Building staff engagement, team experiences and paddock access

I would rather have one great partner than ten average ones. Is that conversation still worth having?

[Rider Name]""",

    "LI Msg 4: Scarcity (Day 21)": """Hi [Contact Name],

Honest update: I have 2 partnership spots remaining for the [Championship Name] season.

Once they are filled, the opportunity is gone until next year.

I have launched [Team Name] with options from supporter-level all the way to title partnership. But the real value is in building something tailored around what [Business Name] actually needs, whether that is new customer acquisition, team engagement, or competitive differentiation.

Here is my question: if I could show you exactly how this works in 10 minutes, would that be worth your time?

No pressure either way.

[Rider Name]""",

    "LI Msg 5: Final (Day 28)": """[Contact Name],

This is my last follow-up.

I have reached out because I believe [Business Name] would be a strong fit. But I respect your time.

If the answer is "not right now", no problem at all. Just let me know and I will stop.

If it is "interested but have not had time", reply with "interested" and I will send a one-page overview. No call needed.

Either way, I would rather know than guess.

[Rider Name]""",

    "Initial Contact": """(See Email: Cold Opener above)""",
    "Follow Up": """(See LI Msg 1 or others)""",
    "Proposal": """[Contact Name],

Here is exactly what I am proposing based on our conversation.

**The Goal for [Business Name]:**
You told me you are focused on [Goal Answer]. Everything below is built around that.

**The Plan:**
- Audience: [Audience Answer], this is who sees your brand every race weekend
- Activation: Logo placement + social media campaign + hospitality access

**Why This Works:**
This directly solves your need for [Success Answer] and it does it in a way your competitors are not.

The proposal deck is attached. I have kept it simple on purpose.

Next step: you tell me what you would change. I will adjust and we lock it in.

[Rider Name]"""
}

# --- FUNCTIONS ---

def get_sector_hook(sector_name):
    for key, hook in SECTOR_HOOKS.items():
        if key in sector_name:
            return hook
    return SECTOR_HOOKS["Other"]

def _get_time_greeting():
    """Returns appropriate greeting based on current time of day."""
    hour = datetime.now().hour
    if hour < 12:
        return "Good morning"
    elif hour < 17:
        return "Good afternoon"
    else:
        return "Good evening"



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

def _format_contact_name(full_name, template_type, salutation="Mr"):
    """Format contact name based on message type.
    - Email opener: formal 'Mr/Mrs/Miss LastName'
    - LI Connect Request: first name only (casual connection note)
    - LI follow-up messages (Msg 1+): first name only
    - salutation: 'Mr', 'Mrs', 'Miss', 'Ms', 'Dr' (selected per contact)
    """
    if not full_name or full_name.strip() == "":
        return f"{salutation} [Name]"  # Placeholder if no name set
    
    # Strip Apollo-style title suffix: "Neil Wearing (Depot Manager)" → "Neil Wearing"
    clean_name = full_name.strip()
    if "(" in clean_name:
        clean_name = clean_name[:clean_name.index("(")].strip()
    
    name_parts = clean_name.split()
    first_name = name_parts[0] if name_parts else clean_name
    last_name = name_parts[-1] if len(name_parts) > 1 else ""
    
    # Email opener: formal addressing with title
    is_formal = template_type in ("Email: Cold Opener",)
    
    if is_formal:
        if last_name:
            return f"{salutation} {last_name}"
        else:
            return f"{salutation} {first_name}"
    else:
        # LinkedIn messages and follow-ups: first name only
        return first_name

def generate_message(template_type, business_name, rider_name, sector, context_answers=None, town="MyTown", championship="Championship", extra_context={}, contact_name="", salutation="Mr"):
    template = TEMPLATES.get(template_type, "")
    hook = get_sector_hook(sector)
    
    # Format contact name based on message type (formal vs first-name)
    formatted_name = _format_contact_name(contact_name, template_type, salutation)
    
    # Rider name: full name for intro, first name only after that
    rider_first = rider_name.split()[0] if rider_name else rider_name
    
    msg = template.replace("[Business Name]", business_name)\
                  .replace("[Sector]", sector)\
                  .replace("[Town]", town)\
                  .replace("[Championship Name]", championship)\
                  .replace("[Sector Hook]", hook)\
                  .replace("[Contact Name/Business Name]", formatted_name)\
                  .replace("[Contact Name]", formatted_name)\
                  .replace("[Current Year]", "2026")\
                  .replace("Good morning", _get_time_greeting())
    
    # Replace first [Rider Name] with full name, rest with first name only
    if "[Rider Name]" in msg:
        msg = msg.replace("[Rider Name]", rider_name, 1)  # First occurrence: full name
        msg = msg.replace("[Rider Name]", rider_first)     # All remaining: first name only
                  
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
                 
    
    # [NEW] Representation/Parent Mode Logic
    if extra_context.get("rep_mode"):
        rep_name = extra_context.get("rep_name", "Manager")
        rep_role = extra_context.get("rep_role", "Manager")
        
        # 1. Intro Override (Email)
        target_intro = f"My name is {rider_name} and I am based in"
        new_intro = f"My name is {rep_name} and I am the {rep_role} of {rider_name}. We are based in"
        msg = msg.replace(target_intro, new_intro)
        
        # Fallback for other intro patterns
        target_intro_2 = f"My name is {rider_name}"
        new_intro_2 = f"My name is {rep_name} and I am the {rep_role} of {rider_name}"
        msg = msg.replace(target_intro_2, new_intro_2)
        
        # 2. Activity Pronoun Overrides
        substitutions = [
            ("I am racing this season", f"{rider_name} is racing this season"),
            ("I am racing in", f"{rider_name} is racing in"),
            ("I am deep into pre-season", f"{rider_name} is deep into pre-season"),
            ("I compete in the", f"{rider_name} competes in the"),
            ("I am reaching out to", f"I am reaching out on behalf of {rider_name} to"),
            ("I have launched", f"{rider_name} has launched"),
            ("I have 2 partnership spots", f"{rider_name} has 2 partnership spots"),
            ("I have reached out because I believe", f"I have reached out because we believe"),
            ("I would rather have one great", f"{rider_name} would rather have one great"),
            ("my race helmet", f"{rider_name}'s race helmet"),
            ("expand my network", "expand our network"),
        ]
        
        for old_phrase, new_phrase in substitutions:
            msg = msg.replace(old_phrase, new_phrase)
            
        # 3. Signature Override
        if msg.strip().endswith(rider_name):
             msg = rep_name.join(msg.rsplit(rider_name, 1))

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

def onboarding_screen(user_data, is_edit_mode=False):
    if is_edit_mode:
        st.title("👤 Update Your Profile & Data")
        if st.button("← Back to Dashboard"):
            st.session_state.editing_profile = False
            st.rerun()
    else:
        st.title("🏁 Welcome! Let's set up your profile.")
        st.markdown("To help us find the right sponsors, tell us about your racing.")
    
    # Removed st.form to allow interactive conditionals
    st.subheader("1. About You")
    
    # Pre-fill
    profile = user_data.get('profile', {})
    raw_name = user_data.get('name', '')
    if is_edit_mode:
        default_fname = profile.get('first_name', raw_name.split(" ")[0] if " " in raw_name else raw_name)
        default_lname = profile.get('last_name', raw_name.split(" ")[1] if " " in raw_name else "")
        default_town = profile.get('town', '')
        default_country = profile.get('country', '')
        default_state = profile.get('state', '')
        default_zip = profile.get('zip_code', '')
        default_champ = profile.get('championship', '')
        default_comp = int(profile.get('competitors', 20))
        default_spec = profile.get('audience', '5000')
        default_tv = 1 if profile.get('televised') == "Yes" else 0
        default_stream = 1 if profile.get('streamed') == "Yes" else 0
        default_tv_reach = profile.get('tv_reach', '')
        default_goal = profile.get('goal', '')
        default_prev_champ = profile.get('prev_champ', '')
        default_achievements = profile.get('achievements', '')
        default_team = profile.get('team', '')
    else:
        # Defaults for fresh onboarding
        default_fname = raw_name.split(" ")[0] if " " in raw_name else raw_name
        default_lname = raw_name.split(" ")[1] if " " in raw_name else ""
        default_town = ""
        default_country = ""
        default_state = ""
        default_zip = ""
        default_champ = ""
        default_comp = 20
        default_spec = "5000"
        default_tv = 0
        default_stream = 0
        default_tv_reach = ""
        default_goal = ""
        default_prev_champ = ""
        default_achievements = ""
        default_team = ""
        
    c1, c2 = st.columns(2)
    fname = c1.text_input("First Name", value=default_fname)
    lname = c2.text_input("Last Name", value=default_lname)
    
    c_loc1, c_loc2 = st.columns(2)
    user_town = c_loc1.text_input("Your Town / City (for local search)", value=default_town)
    user_country = c_loc2.text_input("Your Country", value=default_country)
    
    c_loc3, c_loc4 = st.columns(2)
    user_state = c_loc3.text_input("State / Province", value=default_state)
    user_zip = c_loc4.text_input("Zip / Postal Code", value=default_zip)
    
    vehicle = st.selectbox("What do you race?", ["Motorcycle", "Car", "Kart"], index=0)
    
    st.subheader("2. Your Championship")
    champ_name = st.text_input("Championship Full Name", value=default_champ)
    
    c3, c4 = st.columns(2)
    competitors = c3.number_input("Number of Competitors in the paddock", min_value=1, value=default_comp)
    spectators = c4.text_input("Avg. Spectators per Event", value=default_spec)
    
    st.subheader("3. Season Details (used in your outreach messages)")
    st.caption("These details auto-fill your outreach templates so you don't have to type them every time.")
    
    c_s1, c_s2 = st.columns(2)
    season_goal_input = c_s1.text_input("Season Goal (e.g. 'Top 5 finish')", value=default_goal, placeholder="e.g. podium finish, championship title")
    prev_champ_input = c_s2.text_input("Previous Championship", value=default_prev_champ, placeholder="e.g. British Superbikes")
    
    c_s3, c_s4 = st.columns(2)
    achievements_input = c_s3.text_input("Key Achievements", value=default_achievements, placeholder="e.g. 3 wins, fastest lap at Brands Hatch")
    team_name_input = c_s4.text_input("Team Name", value=default_team, placeholder="e.g. Team Speed Racing")
    
    st.subheader("4. Media Exposure")
    c5, c6 = st.columns(2)
    is_tv = c5.selectbox("Is it Televised?", ["No", "Yes"], index=default_tv)
    is_stream = c6.selectbox("Is it Streamed?", ["No", "Yes"], index=default_stream)
    
    tv_reach = ""
    if is_tv == "Yes" or is_stream == "Yes":
        st.info("Great! TV/Streaming is a huge selling point.")
        tv_reach = st.text_input("Do you have viewing figures from the organizer? (e.g. 50k per round)", value=default_tv_reach, placeholder="Enter number or 'Unknown'")
    
    st.divider()

    st.subheader("5. Representation (Parent / Manager Mode)")
    st.caption("Enable this if you are a parent or manager managing this account for the rider.")
    
    # Defaults
    def_rep_mode = profile.get("rep_mode", False)
    def_rep_name = profile.get("rep_name", "")
    def_rep_role = profile.get("rep_role", "Mother")
    
    is_rep = st.checkbox("I am managing this for the rider (enable text adjustments)", value=def_rep_mode)
    
    rep_name = ""
    rep_role = "Mother"
    
    if is_rep:
        r1, r2 = st.columns(2)
        rep_name = r1.text_input("Your Name (The Sender)", value=def_rep_name, placeholder="e.g. Sally")
        rep_role = r2.selectbox("Relationship to Rider", ["Mother", "Father", "Manager", "Agent", "Sponsor"], index=["Mother", "Father", "Manager", "Agent", "Sponsor"].index(def_rep_role) if def_rep_role in ["Mother", "Father", "Manager", "Agent", "Sponsor"] else 0)
        st.info(f"Messages will read: 'My name is {rep_name} and I am the {rep_role} of {raw_name}...'")

    st.divider()
    
    st.subheader("6. Database Setup")
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
                "onboarding_complete": True,
                "goal": season_goal_input,
                "prev_champ": prev_champ_input,
                "achievements": achievements_input,
                "team": team_name_input,
                "rep_mode": is_rep,
                "rep_name": rep_name,
                "rep_role": rep_role
            })
            
            db.save_user_profile(user_data['email'], full_name, profile_update)
            st.success("Profile Saved! Loading Dashboard...")
            st.rerun()
        else:
            st.error(f"Please fill in the following: {', '.join(missing)}")

# LOGIC FLOW
# [UPGRADED] Auto-Login: check query params for session persistence
if not st.session_state.user_id:
    qp = st.query_params.get("user")
    if qp:
         user = db.get_user_by_email(qp)
         if user:
             st.session_state.user_id = user['id']
    
if not st.session_state.user_id:
    login_screen()
    st.stop()
else:
    # Ensure query param stays set so refresh doesn't lose session
    _persist_data = db.get_user_profile(st.session_state.user_id)
    _persist_email = _persist_data.get('email', '') if _persist_data else ''
    if _persist_email and st.query_params.get('user') != _persist_email:
        st.query_params['user'] = _persist_email

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

# [NEW] Check Edit Profile Mode
if st.session_state.get("editing_profile"):
    onboarding_screen(user_data, is_edit_mode=True)
    st.stop()

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
    st.caption("v2.5 (Search Upgrade)")
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
    
    if st.button("Access Profile", help="Update your profile and upload data sheets."):
        st.session_state.editing_profile = True
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
            # Use optimized query if available, else default to sector name
            search_query = SECTOR_SEARCH_OPTIMIZATIONS.get(selected_sector, selected_sector)
    else:
        # COMPANY SCOUT MODE
        st.info("🎯 Enter specific details to analyze a target.")
        scout_company = st.text_input("Company Name")
        scout_location = st.text_input("City / Location", value=saved_town)
        search_query = f"{scout_company} in {scout_location}" if scout_company else ""

    st.markdown("---")
    st.markdown("---")
    with st.expander("⚙️ Settings (Premium Features)"):
        # Provider Selection
        # Provider Selection
        search_provider = st.radio("Search Engine", ["Outscraper (Bulk Data)"], index=0, help="Outscraper = Best for comprehensive lists.")
        st.session_state.search_provider = search_provider
        
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
             
        # Outscraper Key Logic
        if "Outscraper" in search_provider:
            # Check st.secrets first (Root level or inside airtable section by mistake)
            system_os_key = st.secrets.get("outscraper_api_key", "")
            if not system_os_key and "airtable" in st.secrets:
                 system_os_key = st.secrets["airtable"].get("outscraper_api_key", "")
            
            # Use stored key if available
            current_key = st.session_state.user_profile.get("outscraper_key", "")
            
            # If system key exists and we don't have a user key yet (or it matches), use system key
            if system_os_key and (not current_key or current_key == system_os_key):
                 st.success("✅ Outscraper Key is managed by the system (Shared Key active).")
                 st.session_state.user_profile["outscraper_key"] = system_os_key 
                 # Still show value for confirmation but disabled? Or just hidden?
                 # User screenshot shows input. Let's make it consistent.
                 # If managed, don't show input to avoid confusion, just the success message.
            else:
                saved_os_key = st.session_state.user_profile.get("outscraper_key", "")
                outscraper_key = st.text_input("Outscraper API Key", value=saved_os_key, type="password", help="Get from outscraper.com for bulk data.")
                
                if outscraper_key:
                     st.session_state.user_profile["outscraper_key"] = outscraper_key
                     # Auto-save validation
                     if outscraper_key != saved_os_key:
                        db.save_user_profile(st.session_state.user_email, st.session_state.user_name, st.session_state.user_profile)
                        st.toast("Outscraper Key Saved!")
            
            st.warning("⚖️ Compliance Note: Use Outscraper to collect **Public Business Data** only (B2B). Avoid extracting private personal details to maintain GDPR/CCPA safety.", icon="🛡️")
             
            # Apollo Key Logic
            saved_apollo_key = st.session_state.user_profile.get("apollo_api_key", "")
            apollo_key = st.text_input("Apollo.io API Key (Optional)", value=saved_apollo_key, type="password", help="Used to automatically find the Managing Director / CEO on save.")
            if apollo_key:
                 st.session_state.user_profile["apollo_api_key"] = apollo_key
                 if apollo_key != saved_apollo_key:
                     db.save_user_profile(st.session_state.user_email, st.session_state.user_name, st.session_state.user_profile)
                     st.toast("Apollo Key Saved!")

    
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
TABS = [" Search & Add", "✉️ Outreach Assistant", "📊 Active Campaign", "📰 Bulk Mailer"]
if "current_tab" not in st.session_state:
    st.session_state.current_tab = TABS[0]

# [FIX] Handle deferred tab switching to prevent StreamlitAPIException
if "requested_tab" in st.session_state:
    tgt = st.session_state.requested_tab
    st.session_state.nav_radio = tgt # Sync widget key
    del st.session_state.requested_tab

# Navigation Bar
# Navigation Bar
# To fix "widget with key... value set via Session State API" warning:
# We must NOT pass 'index' if we are controlling it via key='nav_radio' which is already in session_state.
# The 'nav_radio' key in session_state acts as the source of truth.

selected_tab = st.radio(
    "Navigation", 
    TABS, 
    horizontal=True, 
    label_visibility="collapsed",
    key="nav_radio"
)
st.session_state.current_tab = selected_tab

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
        
        # Calculate Revenue
        # Ensure Value col is numeric
        df_leads['Value'] = pd.to_numeric(df_leads.get('Value', 0), errors='coerce').fillna(0)
        total_revenue = df_leads[df_leads['Status'] == 'Secured']['Value'].sum()
        
        # Display Revenue Top Level
        r1, r2 = st.columns([3, 1])
        r1.metric("💰 Total Secured Revenue", f"£{total_revenue:,.2f}")
        
        st.divider()

        # 2. QUICK FILTERS
        # Initialize filter state
        if 'dashboard_filter' not in st.session_state:
            st.session_state.dashboard_filter = "All"
        
        f1, f2 = st.columns(2)
        
        # Filter 1: Active Pipeline (Anything NOT Secured or Lost)
        active_mask = ~df_leads['Status'].isin(['Secured', 'Lost'])
        count_active = len(df_leads[active_mask])
        label_1 = f"🔥 Active Pipeline ({count_active})"
        if f1.button(label_1, type="primary" if st.session_state.dashboard_filter == "Pipeline" else "secondary", use_container_width=True):
             st.session_state.dashboard_filter = "Pipeline"
              
        # Filter 2: Secured
        label_2 = f"🏆 Secured Deals ({num_secured})"
        if f2.button(label_2, type="primary" if st.session_state.dashboard_filter == "Secured" else "secondary", use_container_width=True):
             st.session_state.dashboard_filter = "Secured"
             
        # Reset
        if st.session_state.dashboard_filter != "All":
            if st.button("❌ Reset Filter"):
                st.session_state.dashboard_filter = "All"
                st.rerun()
        
        st.divider()
        
        # APPLY FILTER
        df_view = df_leads.copy()
        if st.session_state.dashboard_filter == "Pipeline":
             df_view = df_view[active_mask]
        elif st.session_state.dashboard_filter == "Secured":
             df_view = df_view[df_leads['Status'] == 'Secured']
        
        # Sort by Next Action
        df_view = df_view.sort_values(by="Next Action")
        
        # VIEW TOGGLE
        v_col1, v_col2 = st.columns([1, 4])
        with v_col1:
            view_mode = st.radio("View Mode", ["Cards", "Calendar", "List Table"], index=1, horizontal=True)
            
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
            
            # Message sequence for calendar labels
            _MSG_SEQUENCE = [
                "LI Connect: Request",
                "Email: Cold Opener",
                "LI Msg 1: Intro (Day 2)",
                "LI Msg 2: Homework (Day 7)",
                "LI Msg 3: Momentum (Day 14)",
                "LI Msg 4: Scarcity (Day 21)",
                "LI Msg 5: Final (Day 28)"
            ]
            
            # Statuses that should NOT appear in the calendar (user moved them forward)
            _EXCLUDED_STATUSES = {'Call Booked', 'Discovery Call', 'Proposal', 'Secured', 'Lost', 'Not Interested'}
            
            events = []
            for _, row in df_leads.iterrows():
                if pd.notnull(row['Next Action']):
                    # Skip leads that have been moved to a future stage
                    if row['Status'] in _EXCLUDED_STATUSES:
                        continue
                    
                    # Determine next message step from notes
                    notes = row.get('Notes', {})
                    if isinstance(notes, str):
                        try:
                            notes = json.loads(notes)
                        except:
                            notes = {}
                    last_step = notes.get('outreach_step', -1) if isinstance(notes, dict) else -1
                    try:
                        last_step = int(last_step)
                    except:
                        last_step = -1
                    next_step = last_step + 1
                    
                    if next_step < len(_MSG_SEQUENCE):
                        # Show full step label with day info for stage visibility
                        step_name = _MSG_SEQUENCE[next_step]
                        # Extract short label like "LI Msg 2" and day info like "(Day 2)"
                        day_info = ""
                        if "(Day" in step_name:
                            day_info = " " + step_name[step_name.index("("):step_name.index(")")+1]
                        next_msg_label = step_name.split(":")[0].strip() + day_info
                    elif last_step >= 0:
                        next_msg_label = "✅ Sequence Done"
                    else:
                        next_msg_label = "Opener"
                    
                    # Show full contact name + company + sequence step
                    contact_display = (row.get('Contact Name', '') or '').strip()
                    company = row['Business Name']
                    if contact_display:
                        cal_title = f"{contact_display} — {company} → {next_msg_label}"
                    else:
                        cal_title = f"{company} → {next_msg_label}"
                    
                    # Extract contact URL from notes if available
                    event_notes = row.get('Notes', {})
                    if isinstance(event_notes, str):
                        try: event_notes = json.loads(event_notes)
                        except: event_notes = {}
                    event_contact_url = event_notes.get('contact_url', '') if isinstance(event_notes, dict) else ''
                    
                    events.append({
                        "title": cal_title,
                        "start": row['Next Action'].strftime("%Y-%m-%d"),
                        "backgroundColor": get_status_color(row['Status']),
                        "borderColor": get_status_color(row['Status']),
                        "extendedProps": {"id": row['id'], "contact_url": event_contact_url, "contact_name": contact_display}
                    })
            
            calendar_options = {
                "headerToolbar": {
                    "left": "today prev,next",
                    "center": "title",
                    "right": "dayGridMonth,timeGridWeek,timeGridDay"
                },
                "initialView": "dayGridMonth",
                "initialDate": datetime.now().strftime("%Y-%m-%d"),
                "navLinks": True,
            }
            
            cal_data = calendar(events=events, options=calendar_options)
            
            if cal_data.get("eventClick"):
                 event = cal_data["eventClick"]["event"]
                 lead_id = event["extendedProps"]["id"]
                 st.session_state.selected_lead_id = lead_id
                 calendar_contact_card(lead_id)
            
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
                
            st.dataframe(df_view[["Business Name", "Sector", "Status", "Contact Name", "Next Action"]], width="stretch")
            
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

    # Format query for display
    display_query = f"'{search_query}'"
    if isinstance(search_query, list):
        display_query = ", ".join([f"'{q}'" for q in search_query])
        # Truncate if too long
        if len(display_query) > 60: display_query = display_query[:60] + "..."

    st.subheader(f"Find {display_query} within {search_radius} miles of {location_search_ctx}")
    
    # NEW SEARCH (Reset)
    if st.button("Run Search (Scout)", type="primary"):
        st.session_state.leads = pd.DataFrame() # Clear old
        st.session_state.next_page_token = None
        
        if search_mode == "Company Scout" and not scout_company:
             st.error("Please enter a Company Name to scout.")
        else:
            with st.spinner("Scanning Page 1..."):
                # [NEW] Multi-Keyword Support
                sector_arg = selected_sector if search_mode == "Sector Search" else "Target Company"
                queries = search_query if isinstance(search_query, list) else [search_query]

                # DETERMINE PROVIDER
                # [MODIFIED] Force Outscraper only as per user request to compare results
                provider = "Outscraper (Bulk Data)" 
                st.session_state.search_provider = provider
                
                # --- OUTSCRAPER ---
                if "Outscraper" in provider:
                    os_key = st.session_state.user_profile.get("outscraper_key")
                    if not os_key:
                        st.error("⚠️ Outscraper API Key missing. Please go to Settings (left sidebar) and add it.")
                    else:
                        # [NEW] Multi-Keyword Loop for Outscraper (Bulk Data)
                        # We iterate through ALL queries ("Haulage", "Transport" etc) to match Google's breadth
                        
                        all_os_results = []
                        progress_log = st.empty()
                        
                        # Pagination Init
                        st.session_state.outscraper_skip = 0
                        LIMIT_PER_KEYWORD = 15 # Aim for ~50-60 results per batch (across 4 keywords)
                        
                        for idx, q_str in enumerate(queries):
                            progress_log.caption(f"Outscraper: Scanning across regions for '{q_str}' ({idx+1}/{len(queries)})...")
                            
                            full_loc = f"{location_search_ctx}"
                            
                            # Fire the wide-area scatter search for this keyword
                            res_batch, _ = search_outscraper(
                                os_key, 
                                q_str, 
                                full_loc, 
                                radius=search_radius, 
                                limit=LIMIT_PER_KEYWORD,
                                skip=0,
                                google_api_key=google_api_key
                            )
                            
                            if isinstance(res_batch, dict) and "error" in res_batch:
                                st.warning(f"Outscraper error for '{q_str}': {res_batch['error']}")
                            elif isinstance(res_batch, list):
                                all_os_results.extend(res_batch)
                                
                        progress_log.empty()
                        
                        if not all_os_results:
                                st.warning("Outscraper found 0 results.")
                                st.session_state.leads = pd.DataFrame()
                                st.session_state.next_page_token = None
                        else:
                                # Deduplicate
                                temp_df = pd.DataFrame(all_os_results)
                                before_count = len(temp_df)
                                temp_df.drop_duplicates(subset=["Business Name"], keep="first", inplace=True)
                                
                                st.session_state.leads = temp_df
                                if "Distance" in st.session_state.leads.columns:
                                     st.session_state.leads.sort_values(by="Distance", inplace=True)
                                
                                # Strict Limit: Max 50 Results per Page
                                if len(st.session_state.leads) > 50:
                                    st.session_state.leads = st.session_state.leads.head(50)
                                
                                # Enable Load More for Outscraper
                                st.session_state.next_page_token = "outscraper_more" 
                                st.success(f"Outscraper: Showing closest {len(st.session_state.leads)} targets (Merged keywords)")
                
                # --- GOOGLE PLACES (LEGACY / PROXIMITY) ---
                elif "Legacy" in provider and google_api_key:
                    # Legacy uses 'keyword' and 'rankby=distance'. 
                    # It ignores radius in strict sense, but we can filter later or just accept nice local list.
                    
                    combined_results = []
                    
                    # Get Lat/Lon once
                    from search_service import get_lat_long
                    lat, lon, _ = get_lat_long(google_api_key, location_search_ctx)
                    
                    if not lat:
                        st.error("Could not geocode location for Legacy Search.")
                    else:
                        # Legacy search limits: expensive to loop too much.
                        # Just take top 2 keywords if list
                        use_queries = queries[:2] if isinstance(queries, list) else [queries]
                        
                        for q in use_queries:
                             st.caption(f"Proximity Search: '{q}'...")
                             res, _ = search_google_legacy_nearby(google_api_key, q, lat, lon, search_radius)
                             if isinstance(res, list):
                                 combined_results.extend(res)
                        
                        # Dedupe and set
                        if combined_results:
                             temp_df = pd.DataFrame(combined_results)
                             temp_df.drop_duplicates(subset=["Business Name"], keep="first", inplace=True)
                             st.session_state.leads = temp_df
                             st.session_state.next_page_token = None
                             st.success(f"Proximity Search found {len(temp_df)} unique results.")
                        else:
                             st.warning("No results found.")

                
                # --- GOOGLE PLACES (SMART / TEXT) ---
                elif google_api_key:
                    # REAL SEARCH - Page 1
                    sector_arg = selected_sector if search_mode == "Sector Search" else "Target Company"
                    
                    # [NEW] Multi-Keyword Support
                    queries = search_query if isinstance(search_query, list) else [search_query]
                    
                    combined_results = []
                    last_token = None
                    
                    progress_text = st.empty()
                    
                    for i, q in enumerate(queries):
                        progress_text.caption(f"Searching for '{q}' ({i+1}/{len(queries)})...")
                        
                        # Use specific sector name if we have one, else just the query
                        res, tok = search_google_places(google_api_key, q, location_search_ctx, search_radius, sector_name=sector_arg)
                        
                        if isinstance(res, dict) and "error" in res:
                            st.warning(f"Error for '{q}': {res['error']}")
                            continue
                            
                        combined_results.extend(res)
                        # We only keep the token for the LAST query for now usually, 
                        # or we disable deep search for multi-query because it gets complex.
                        # For simplicity: One deep search token or None.
                        last_token = tok 

                    progress_text.empty()
                    
                    if not combined_results:
                         st.warning("No results found.")
                         st.session_state.leads = pd.DataFrame()
                         st.session_state.next_page_token = None
                    else:
                         # Deduplicate by Name
                         # Create DF first for easier drop_duplicates
                         temp_df = pd.DataFrame(combined_results)
                         if not temp_df.empty:
                             before = len(temp_df)
                             temp_df.drop_duplicates(subset=["Business Name"], keep="first", inplace=True)
                             after = len(temp_df)
                             
                             st.session_state.leads = temp_df
                             # If we ran multiple queries, setting a single next_page_token is tricky 
                             # because it only applies to one. We'll disable it for Multi-Search for now to avoid confusion.
                             # Or just keep the last one.
                             st.session_state.next_page_token = None if len(queries) > 1 else last_token
                             
                             st.success(f"Found {after} unique targets! (Merged {len(queries)} searches)")
                         else:
                             st.session_state.leads = pd.DataFrame()
                             st.session_state.next_page_token = None
                             
                else:
                    # MOCK SEARCH (unchanged)
                    mode_arg = "previous" if search_mode == "Company Scout" else "sector"
                    results = mock_search_places(location_search_ctx, search_radius, search_query, mode=mode_arg)
                    st.session_state.leads = pd.DataFrame(results)
                    st.session_state.next_page_token = None
                    st.info("ℹ️ Demo Mode.")

    # LOAD MORE BUTTON
    if st.session_state.get("next_page_token"):
        if st.button("⬇️ Deeper Search (Next Batch)"):
             with st.spinner("Fetching next page..."):
                 token = st.session_state.next_page_token
                 
                 # --- OUTSCRAPER LOAD MORE ---
                 if token == "outscraper_more":
                     os_key = st.session_state.user_profile.get("outscraper_key")
                     queries = search_query if isinstance(search_query, list) else [search_query]
                     LIMIT_PER_KEYWORD = 15
                     
                     st.session_state.outscraper_skip += LIMIT_PER_KEYWORD
                     current_skip = st.session_state.outscraper_skip
                     
                     new_os_results = []
                     
                     for idx, q_str in enumerate(queries):
                        full_loc = f"{location_search_ctx}"
                        res_batch, _ = search_outscraper(
                            os_key, 
                            q_str, 
                            full_loc, 
                            radius=search_radius, 
                            limit=LIMIT_PER_KEYWORD,
                            skip=current_skip,
                            google_api_key=google_api_key
                        )
                        if isinstance(res_batch, list):
                            new_os_results.extend(res_batch)
                     
                     if new_os_results:
                         new_df = pd.DataFrame(new_os_results)
                         
                         # Limit new batch to 50
                         if len(new_df) > 50:
                             new_df = new_df.head(50)
                             
                         # Concat
                         st.session_state.leads = pd.concat([st.session_state.leads, new_df], ignore_index=True)
                         # Dedupe again just in case
                         st.session_state.leads.drop_duplicates(subset=["Business Name"], keep="first", inplace=True)
                         
                         if "Distance" in st.session_state.leads.columns:
                             st.session_state.leads.sort_values(by="Distance", inplace=True)
                             
                         st.success(f"Added {len(new_df)} more! Total: {len(st.session_state.leads)}")
                         st.rerun()
                     else:
                         st.warning("No more results found.")
                         st.session_state.next_page_token = None
                         st.rerun()
                 
                 # --- GOOGLE LOAD MORE ---
                 else:
                     sector_arg = search_query if search_mode == "Sector Search" else "Target Company"
                     new_results, new_token = search_google_places(google_api_key, search_query, location_search_ctx, search_radius, sector_name=sector_arg, pagetoken=token)
                     
                     if isinstance(new_results, dict) and "error" in new_results:
                         st.error(f"Google API Error: {new_results['error']}")
                         # Do not update token so user can retry? Or clear it?
                         # Usually token is single-use, but if error was transient...
                         # Google tokens usually expire if used.
                         # Let's keep the token for a retry if it was a network error, but if it was Invalid Argument, it is dead.
                     elif new_results:
                         # Append to existing DataFrame
                         new_df = pd.DataFrame(new_results)
                         st.session_state.leads = pd.concat([st.session_state.leads, new_df], ignore_index=True)
                         st.success(f"Added {len(new_results)} more! Total: {len(st.session_state.leads)}")
                         
                         st.session_state.next_page_token = new_token # Update token (or None if done)
                         if not new_token:
                             st.info("✅ All pages loaded.")
                         st.rerun()
                     else:
                         st.warning("No more results found.")
                         st.session_state.next_page_token = None
                         st.rerun()

    # Post-Processing: Check for Duplicates (Run always if leads exist)
    if not st.session_state.leads.empty:
        # 1. Fetch current user leads
        my_leads = db.get_leads(st.session_state.user_id)
        existing_names = {l["Business Name"].lower() for l in my_leads}
        
        # 2. Add "In List" column
        df_results = st.session_state.leads.copy()
        df_results["In List"] = df_results["Business Name"].apply(lambda x: "✅" if str(x).lower() in existing_names else "")
        
        # --- QUALITY SCORE DISPLAY ---
        if "Quality" in df_results.columns:
            df_results["Score"] = df_results["Quality"].apply(lambda q: "⭐" * int(q) if q else "")
        
        # --- SIZE DISPLAY ---
        if "Size" not in df_results.columns:
            df_results["Size"] = "—"
        
        # --- SOCIAL PRESENCE INDICATOR ---
        if "Social" in df_results.columns:
            def _social_icons(social_dict):
                if not social_dict or not isinstance(social_dict, dict):
                    return "❌ None"
                icons = []
                if social_dict.get("linkedin"): icons.append("🔗")
                if social_dict.get("facebook"): icons.append("📘")
                if social_dict.get("instagram"): icons.append("📸")
                if social_dict.get("twitter"): icons.append("🐦")
                return " ".join(icons) if icons else "❌ None"
            df_results["Socials"] = df_results["Social"].apply(_social_icons)
        
        # --- MAP DISPLAY (If lat/lon ok) ---
        if "lat" in df_results.columns:
                st.map(df_results)
        
        # --- RESULTS SUMMARY ---
        total = len(df_results)
        high_q = len(df_results[df_results.get("Quality", 0) >= 4]) if "Quality" in df_results.columns else 0
        st.caption(f"📊 **{total} results** found • {high_q} high-quality leads (4+⭐)")
                
        # --- BUILD DISPLAY COLUMNS ---
        disp_cols = ["In List", "Business Name", "Address"]
        
        if "Score" in df_results.columns:
            disp_cols.append("Score")
        if "Size" in df_results.columns:
            disp_cols.append("Size")
        if "Distance" in df_results.columns:
            disp_cols.append("Distance")
        
        # Only show columns that exist
        disp_cols = [c for c in disp_cols if c in df_results.columns]
            
        event = st.dataframe(
                df_results[disp_cols],
                width="stretch",
                column_config={
                    "Score": st.column_config.TextColumn("Quality", width="small", help="A 5-star lead = local business with a website, phone, good reviews, right size. Perfect sponsor candidate."),
                    "Size": st.column_config.TextColumn("Est. Size", width="small"),
                    "Distance": st.column_config.NumberColumn("Miles", format="%.1f", width="small"),
                    "In List": st.column_config.TextColumn("Added", width="small"),
                },
                selection_mode="single-row",
                on_select="rerun",
                key="results_table"
        )
    
        
        # Get selected row from table click
        selected_rows = event.selection.rows if event and event.selection else []
        
        if selected_rows:
            selected_idx = selected_rows[0]
            add_choice = df_results.iloc[selected_idx]["Business Name"]
            is_in_list = str(add_choice).lower() in existing_names
            
            col_s1, col_s2 = st.columns([3, 1])
            with col_s1:
                st.info(f"Selected: **{add_choice}**")
            with col_s2:
                if st.button("➕ Add to My Leads", disabled=is_in_list, use_container_width=True):
                    if is_in_list:
                        st.error("Already in your list!")
                    else:
                        row = df_results.iloc[selected_idx]
                    
                    b_name = row["Business Name"]
                    b_sect = row["Sector"]
                    b_loc = row["Address"]
                    b_web = row.get("Website", "")
                    b_contact = row.get("Owner", "")  # Pre-fill contact from owner
                    
                    # Build enriched notes from search data
                    enriched_notes = {}
                    
                    # --- PRIMARY ENRICHMENT: APOLLO (decision-maker + company data) ---
                    apollo_key = st.session_state.user_profile.get("apollo_api_key", "") or st.secrets.get("apollo_api_key", "")
                    apollo_found = False
                    
                    if apollo_key and b_web:
                        st.toast(f"🔎 Searching Apollo for {b_name} decision maker...")
                        domain = extract_domain(b_web)
                        apollo_res = search_apollo_people(apollo_key, domain)

                        if "error" not in apollo_res:
                            apollo_found = True
                            
                            # Decision-maker data
                            title_str = apollo_res.get('Title', '')
                            name_str = f"{apollo_res.get('First Name', '')} {apollo_res.get('Last Name', '')}".strip()
                            if name_str:
                                b_contact = f"{name_str} ({title_str})" if title_str else name_str
                                enriched_notes["owner"] = b_contact
                                enriched_notes["owner_first"] = apollo_res.get('First Name', '')
                                enriched_notes["owner_last"] = apollo_res.get('Last Name', '')
                                enriched_notes["owner_title"] = title_str
                                st.success(f"🎯 Decision Maker: **{b_contact}**")
                            
                            # Email
                            if apollo_res.get('Email'):
                                enriched_notes["email"] = apollo_res['Email']
                                enriched_notes["emails"] = [apollo_res['Email']]
                                st.success(f"📧 Email: {apollo_res['Email']}")
                            
                            # Personal LinkedIn
                            if apollo_res.get('LinkedIn'):
                                enriched_notes["contact_url"] = apollo_res['LinkedIn']
                                enriched_notes["owner_linkedin"] = apollo_res['LinkedIn']
                                st.success(f"🔗 LinkedIn: {apollo_res['LinkedIn']}")
                            
                            # Company LinkedIn page
                            if apollo_res.get('Company LinkedIn'):
                                enriched_notes["linkedin_company"] = apollo_res['Company LinkedIn']
                                if not enriched_notes.get("contact_url"):
                                    enriched_notes["contact_url"] = apollo_res['Company LinkedIn']
                            
                            # Company firmographic data
                            if apollo_res.get('Employee Count'):
                                emp = apollo_res['Employee Count']
                                enriched_notes["employee_count"] = emp
                                if isinstance(emp, (int, float)) and emp > 0:
                                    if emp > 250: enriched_notes["company_size"] = f"Large ({emp} employees)"
                                    elif emp > 50: enriched_notes["company_size"] = f"Medium ({emp} employees)"
                                    elif emp > 10: enriched_notes["company_size"] = f"Small ({emp} employees)"
                                    else: enriched_notes["company_size"] = f"Micro ({emp} employees)"
                                    st.success(f"👥 Company Size: {emp} employees")
                            
                            if apollo_res.get('Revenue'):
                                enriched_notes["revenue"] = apollo_res['Revenue']
                                st.success(f"💰 Revenue: {apollo_res['Revenue']}")
                            
                            if apollo_res.get('Industry'):
                                enriched_notes["industry"] = apollo_res['Industry']
                            
                            if apollo_res.get('Founded Year'):
                                enriched_notes["founded_year"] = apollo_res['Founded Year']
                            
                            if apollo_res.get('Company Phone'):
                                enriched_notes["company_phone"] = apollo_res['Company Phone']
                            
                            if apollo_res.get('Direct Phone'):
                                enriched_notes["direct_phone"] = apollo_res['Direct Phone']
                            
                            if apollo_res.get('Short Description'):
                                enriched_notes["description"] = apollo_res['Short Description']
                            
                            # Alternate contacts (other directors/managers)
                            if apollo_res.get('Alternates'):
                                enriched_notes["alternate_contacts"] = apollo_res['Alternates']
                                alt_names = [f"{a['name']} ({a['title']})" for a in apollo_res['Alternates'] if a.get('name')]
                                if alt_names:
                                    st.info(f"👤 Also found: {', '.join(alt_names)}")
                        else:
                            st.warning(f"Apollo: {apollo_res.get('error', 'No results')}")
                    
                    # --- FALLBACK: OUTSCRAPER CONTACTS (if Apollo didn't find email) ---
                    os_key = st.session_state.user_profile.get("outscraper_key", "")
                    if os_key and b_web and not enriched_notes.get("email"):
                        st.toast(f"🔎 Outscraper fallback for {b_name}...")
                        domain = extract_domain(b_web)
                        contact_res = search_outscraper_contacts(os_key, domain)

                        if "error" not in contact_res:
                            if contact_res.get("emails") and not enriched_notes.get("email"):
                                enriched_notes["email"] = contact_res["emails"][0]
                                enriched_notes["emails"] = contact_res["emails"]
                                st.success(f"📧 Found email: {contact_res['emails'][0]}")

                            if contact_res.get("phones") and not enriched_notes.get("phones"):
                                enriched_notes["phones"] = contact_res["phones"]

                            if contact_res.get("social"):
                                existing_social = enriched_notes.get("social_links", {})
                                if not isinstance(existing_social, dict):
                                    existing_social = {}
                                for k, v in contact_res["social"].items():
                                    if v and not existing_social.get(k):
                                        existing_social[k] = v
                                enriched_notes["social_links"] = existing_social

                            if contact_res.get("linkedin") and not enriched_notes.get("linkedin_company"):
                                enriched_notes["linkedin_company"] = contact_res["linkedin"]
                                if not enriched_notes.get("contact_url"):
                                    enriched_notes["contact_url"] = contact_res["linkedin"]

                            if contact_res.get("site_description") and not enriched_notes.get("description"):
                                enriched_notes["description"] = contact_res["site_description"]

                    if not b_contact and row.get("Owner"):
                        enriched_notes["owner"] = row["Owner"]
                    if row.get("Description") and not enriched_notes.get("description"):
                        enriched_notes["description"] = row["Description"]
                    if row.get("Social") and isinstance(row["Social"], dict):
                        existing = enriched_notes.get("social_links", {})
                        if not isinstance(existing, dict):
                            existing = {}
                        for k, v in row["Social"].items():
                            if v and not existing.get(k):
                                existing[k] = v
                        if existing:
                            enriched_notes["social_links"] = existing
                    if row.get("Reviews"):
                        enriched_notes["reviews_count"] = int(row["Reviews"])
                    if row.get("Size") and not enriched_notes.get("company_size"):
                        enriched_notes["company_size"] = row["Size"]
                    if row.get("Quality"):
                        enriched_notes["quality_score"] = int(row["Quality"])
                    if row.get("Email") and not enriched_notes.get("email"):
                        enriched_notes["email"] = row["Email"]
                    if row.get("Emails") and isinstance(row["Emails"], list) and not enriched_notes.get("emails"):
                        enriched_notes["emails"] = row["Emails"]

                    # --- COMPANIES HOUSE (UK Directors/PSCs — FREE) ---
                    ch_key = st.secrets.get("companies_house_api_key", "")
                    if ch_key and b_name:
                        st.toast(f"🏛️ Checking Companies House for {b_name}...")
                        ch_res = search_companies_house(ch_key, b_name)
                        
                        if "error" not in ch_res:
                            # Save company data
                            if ch_res.get("company_number"):
                                enriched_notes["ch_company_number"] = ch_res["company_number"]
                                enriched_notes["ch_company_name"] = ch_res.get("company_name", "")
                            if ch_res.get("sic_codes"):
                                enriched_notes["sic_codes"] = ch_res["sic_codes"]
                            if ch_res.get("registered_address"):
                                enriched_notes["ch_address"] = ch_res["registered_address"]
                            
                            # Save directors list
                            if ch_res.get("directors"):
                                enriched_notes["ch_directors"] = [
                                    {"name": d["name"], "role": d["role"]} 
                                    for d in ch_res["directors"]
                                ]
                            
                            # Save PSCs (owners)
                            if ch_res.get("pscs"):
                                enriched_notes["ch_pscs"] = [
                                    {"name": p["name"]} for p in ch_res["pscs"]
                                ]
                            
                            # Use CH best contact if Apollo didn't find one
                            if ch_res.get("best_contact") and not b_contact:
                                b_contact = ch_res["best_contact"]
                                enriched_notes["owner"] = b_contact
                                
                                # Determine title from CH data
                                ch_title = "Director"
                                if ch_res.get("pscs"):
                                    ch_title = "Owner (PSC)"
                                for d in ch_res.get("directors", []):
                                    if d["name"] == ch_res["best_contact"]:
                                        ch_title = d.get("role", "Director").replace("-", " ").title()
                                        break
                                
                                enriched_notes["owner_title"] = ch_title
                                b_contact = f"{ch_res['best_contact']} ({ch_title})"
                                st.success(f"🏛️ Companies House: **{b_contact}**")
                            
                            # Show other directors found
                            all_people = []
                            for p in ch_res.get("pscs", []):
                                if p["name"] != ch_res.get("best_contact"):
                                    all_people.append(f"{p['name']} (Owner)")
                            for d in ch_res.get("directors", []):
                                if d["name"] != ch_res.get("best_contact"):
                                    role_label = d.get("role", "").replace("-", " ").title()
                                    all_people.append(f"{d['name']} ({role_label})")
                            if all_people:
                                st.info(f"🏛️ Also registered: {', '.join(all_people[:3])}")
                        else:
                            st.caption(f"Companies House: {ch_res.get('error', 'No results')}")

                    # --- LINKEDIN COMPANY PAGE LOOKUP (only if nothing found yet) ---
                    has_linkedin = enriched_notes.get("linkedin_company") or \
                                   enriched_notes.get("contact_url", "").startswith("http") or \
                                   (enriched_notes.get("social_links", {}).get("linkedin") if isinstance(enriched_notes.get("social_links"), dict) else False)
                    if not has_linkedin:
                        os_key = st.session_state.user_profile.get("outscraper_key", "")
                        if os_key:
                            st.toast(f"🔗 Searching LinkedIn company page for {b_name}...")
                            li_url = find_linkedin_company_page(os_key, b_name, b_loc)
                            if li_url:
                                enriched_notes["linkedin_company"] = li_url
                                if not enriched_notes.get("contact_url"):
                                    enriched_notes["contact_url"] = li_url
                                st.success(f"🔗 Found LinkedIn: {li_url}")

                    notes_json = json.dumps(enriched_notes) if enriched_notes else "{}"
                    
                    try:
                        new_lead_id = db.add_lead(
                            st.session_state.user_id, b_name, b_sect, b_loc, 
                            website=b_web, contact_name=b_contact, notes_json=notes_json
                        )
                    except Exception as e:
                        st.error(f"Critical Error in add_lead: {e}")
                        new_lead_id = None
                        
                    if new_lead_id:
                        quality_msg = f" (Quality: {'⭐' * int(row.get('Quality', 0))})" if row.get("Quality") else ""
                        st.toast(f"✅ Added {add_choice}{quality_msg} — Opening Outreach Assistant...")
                        
                        # Auto-switch to Outreach Assistant
                        st.session_state.selected_lead_id = new_lead_id
                        st.session_state.requested_tab = "✉️ Outreach Assistant"
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
        # Prepare lists — newest leads first (reverse order)
        reversed_leads = list(reversed(all_leads))
        lead_names = [l["Business Name"] for l in reversed_leads]
        lead_ids = [l["id"] for l in reversed_leads]
        
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
        selected_lead_row = next((l for l in reversed_leads if l["Business Name"] == selected_name), None)
        if selected_lead_row and selected_lead_row['id'] != st.session_state.selected_lead_id:
             st.session_state.selected_lead_id = selected_lead_row["id"]
             st.rerun()

        # 2. MAIN OUTREACH UI
        if st.session_state.selected_lead_id:
            lead = next((l for l in all_leads if l['id'] == st.session_state.selected_lead_id), None)
            
            if lead:
                st.divider() 
                # Header Stats
                h1, h2, h3, h4 = st.columns(4)
                h1.metric("Status", lead['Status'])
                
                # Handle missing or string values
                last_c = lead.get('Last Contact', 'Never')
                next_a = lead.get('Next Action', 'ASAP')
                h2.metric("Last Contact", str(last_c))
                h3.metric("Next Action", str(next_a))
                
                # Revenue / Value Logic
                revenue_val = lead.get("Value", 0.0)
                try:
                    revenue_val = float(revenue_val)
                except:
                    revenue_val = 0.0
                    
                if lead['Status'] == "Secured":
                    # Editable Field
                    with h4:
                        new_rev = st.number_input("Secured Revenue (£)", value=revenue_val, min_value=0.0, step=100.0)
                        if new_rev != revenue_val:
                            if st.button("Save Rev"):
                                db.update_lead_value(lead['id'], new_rev)
                                st.toast("Revenue Updated!")
                                time.sleep(0.5)
                                st.rerun()
                else:
                    # Static Display
                    h4.metric("Potential Value", f"£{revenue_val:,.2f}")

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
                # Parse lead notes for enriched data
                lead_notes_data = lead.get('Notes', {})
                if isinstance(lead_notes_data, str):
                    try: lead_notes_data = json.loads(lead_notes_data)
                    except: lead_notes_data = {}
                if not isinstance(lead_notes_data, dict): lead_notes_data = {}
                
                website_url = lead.get('Website', '')
                domain = ""
                if website_url:
                    domain = website_url.replace("https://", "").replace("http://", "").replace("www.", "").strip("/")
                    domain = domain.split("/")[0]
                
                contact_name_raw = lead.get('Contact Name', '')
                clean_contact = contact_name_raw
                contact_title = ""
                if "(" in clean_contact:
                    contact_title = clean_contact[clean_contact.index("(")+1:clean_contact.index(")")].strip() if ")" in clean_contact else ""
                    clean_contact = clean_contact[:clean_contact.index("(")].strip()
                
                has_contact = bool(clean_contact and clean_contact != lead['Business Name'])
                has_email = bool(lead_notes_data.get('email'))
                has_linkedin = bool(lead_notes_data.get('contact_url', '').startswith('http'))
                
                # ===== STEP 1: INTEL (What Apollo Found) =====
                st.markdown("### Step 1: Review Intel")
                
                if has_contact or has_email:
                    # Apollo found data — show summary card
                    intel_cols = st.columns([1, 1])
                    with intel_cols[0]:
                        st.markdown(f"**🏢 {lead['Business Name']}**")
                        if lead.get('Sector'):
                            st.caption(f"Sector: {lead['Sector']}")
                        if lead_notes_data.get('industry'):
                            st.caption(f"Industry: {lead_notes_data['industry']}")
                        if lead.get('Website'):
                            st.markdown(f"🌐 [{domain}]({lead['Website']})")
                        
                        emp = lead_notes_data.get('employee_count', '')
                        rev = lead_notes_data.get('revenue', '')
                        if emp or rev:
                            size_info = []
                            if emp: size_info.append(f"{emp} employees")
                            if rev: size_info.append(f"Revenue: {rev}")
                            st.caption(" • ".join(size_info))
                    
                    with intel_cols[1]:
                        st.markdown(f"**👤 {clean_contact}**")
                        if contact_title:
                            st.caption(f"Title: {contact_title}")
                        if has_email:
                            st.markdown(f"📧 {lead_notes_data['email']}")
                        if has_linkedin:
                            st.markdown(f"🔗 [LinkedIn Profile]({lead_notes_data['contact_url']})")
                        company_li = lead_notes_data.get('linkedin_company', '')
                        if company_li:
                            st.markdown(f"🏢 [Company LinkedIn]({company_li})")
                        
                        # Alternate contacts (Apollo)
                        alts = lead_notes_data.get('alternates', [])
                        if alts:
                            alt_text = ", ".join([f"{a.get('name','')} ({a.get('title','')})" for a in alts[:2]])
                            st.caption(f"Also found: {alt_text}")
                    
                    # Companies House data (directors/PSCs)
                    ch_dirs = lead_notes_data.get('ch_directors', [])
                    ch_pscs = lead_notes_data.get('ch_pscs', [])
                    if ch_dirs or ch_pscs:
                        with st.expander(f"🏛️ Companies House ({len(ch_dirs)} directors, {len(ch_pscs)} owners)", expanded=False):
                            if ch_pscs:
                                st.markdown("**Owners (PSC):**")
                                for p in ch_pscs:
                                    st.markdown(f"• {p['name']}")
                            if ch_dirs:
                                st.markdown("**Directors:**")
                                for d in ch_dirs:
                                    role = d.get('role', '').replace('-', ' ').title()
                                    st.markdown(f"• {d['name']} — {role}")
                            if lead_notes_data.get('ch_company_number'):
                                ch_url = f"https://find-and-update.company-information.service.gov.uk/company/{lead_notes_data['ch_company_number']}"
                                st.markdown(f"[View on Companies House]({ch_url})")
                    
                    st.success("✅ Decision-maker found. Ready to connect!")
                else:
                    st.warning("⚠️ Apollo couldn't find a contact for this company. Use the research tools below to find one manually.")
                
                st.divider()
                
                # ===== STEP 2: THE MESSAGE =====
                st.markdown("### Step 2: Copy & Send Message")
                
                # Contact details (editable)
                edit_c1, edit_c2, edit_c3 = st.columns([2, 1, 2])
                with edit_c1:
                    new_name = st.text_input("Contact Name", value=contact_name_raw, key=f"contact_name_input_{lead['id']}")
                with edit_c2:
                    saved_salutation = lead_notes_data.get('salutation', 'Mr')
                    sal_options = ["Mr", "Mrs", "Miss", "Ms", "Dr"]
                    sal_idx = sal_options.index(saved_salutation) if saved_salutation in sal_options else 0
                    contact_salutation = st.selectbox("Title", sal_options, index=sal_idx, key=f"sal_{lead['id']}")
                with edit_c3:
                    saved_url = lead_notes_data.get('contact_url', '')
                    contact_url = st.text_input("LinkedIn URL", value=saved_url, key=f"url_{lead['id']}", placeholder="https://linkedin.com/in/...")
                
                # Save contact changes
                if new_name != contact_name_raw or contact_url != saved_url:
                    if st.button("💾 Save Contact Details", key=f"btn_save_{lead['id']}"):
                        if new_name:
                            db.update_lead_contact(lead['id'], new_name)
                            save_notes = lead_notes_data.copy()
                            save_notes['salutation'] = contact_salutation
                            save_notes['contact_url'] = contact_url
                            db.update_lead_notes(lead['id'], save_notes)
                            st.toast(f"✅ Saved: {contact_salutation} {new_name}")
                            time.sleep(0.5)
                            st.rerun()
                
                # Open Profile button
                if has_linkedin:
                    st.markdown(f"**👉 [Open LinkedIn Profile → Send Message]({lead_notes_data['contact_url']})**")
                
                st.divider()
                
                # Message template
                contact_name_for_msg = new_name if new_name else ""
                town = saved_town
                
                seq_options = [
                    "LI Connect: Request",
                    "Email: Cold Opener",
                    "LI Msg 1: Intro (Day 2)",
                    "LI Msg 2: Homework (Day 7)",
                    "LI Msg 3: Momentum (Day 14)",
                    "LI Msg 4: Scarcity (Day 21)",
                    "LI Msg 5: Final (Day 28)"
                ]
                
                # Auto-select next step
                last_sent_step = lead_notes_data.get('outreach_step', -1)
                try: last_sent_step = int(last_sent_step)
                except: last_sent_step = -1
                auto_tpl_idx = min(last_sent_step + 1, len(seq_options) - 1)
                if auto_tpl_idx < 0: auto_tpl_idx = 0
                
                c_mode = st.radio("Mode", ["Draft Opener", "Handle Reply"], horizontal=True, key=f"mode_{lead['id']}")
                
                if c_mode == "Draft Opener":
                    tpl = st.selectbox("Template", seq_options, index=auto_tpl_idx)
                    
                    ctx = {
                        "goal": season_goal, "prev_champ": prev_champ, "achievements": achievements,
                        "audience": audience_size, "tv": tv_viewers, "team": team_name,
                        "rep_mode": user_profile.get("rep_mode", False),
                        "rep_name": user_profile.get("rep_name", ""),
                        "rep_role": user_profile.get("rep_role", "")
                    }
                    
                    draft = generate_message(tpl, lead['Business Name'], rider_name, lead['Sector'], town=town, championship=championship, extra_context=ctx, contact_name=contact_name_for_msg, salutation=contact_salutation)
                    
                    final_msg = st.text_area("Edit Message:", value=draft, height=200)
                    
                    st.caption("👇 Click the Copy icon in the top right of the box below")
                    st.code(final_msg, language=None)
                    
                    # ===== STEP 3: SEND & SCHEDULE =====
                    st.markdown("### Step 3: Mark as Sent")
                    
                    col_d1, col_d2 = st.columns([2, 1])
                    with col_d1:
                        def_days = 2
                        if "Connect" in tpl: def_days = 2
                        elif "Msg 1" in tpl: def_days = 5
                        elif "Msg 2" in tpl: def_days = 7
                        elif "Msg 3" in tpl: def_days = 7
                        elif "Msg 4" in tpl: def_days = 7
                        elif "Msg 5" in tpl: def_days = 30
                        
                        auto_date = datetime.now() + timedelta(days=def_days)
                        auto_str = auto_date.strftime("%Y-%m-%d")
                        
                        use_manual = st.checkbox("Change Date (Manual)?", value=False)
                        if use_manual:
                            final_date_obj = st.date_input("Select Custom Date", value=auto_date)
                            final_date = final_date_obj.strftime("%Y-%m-%d")
                        else:
                            st.info(f"📅 Auto-Schedule: **{auto_str}** (+{def_days} days)")
                            final_date = auto_str
                    
                    with col_d2:
                        st.write("")
                        st.write("")
                        if st.button("✅ Mark as Sent & Schedule", use_container_width=True):
                            st.balloons()
                            db.update_lead_status(lead['id'], "Active", final_date)
                            
                            current_step_idx = seq_options.index(tpl) if tpl in seq_options else 0
                            mark_notes = lead_notes_data.copy()
                            mark_notes['outreach_step'] = current_step_idx
                            mark_notes['last_template'] = tpl
                            mark_notes['salutation'] = contact_salutation
                            if contact_url:
                                mark_notes['contact_url'] = contact_url
                            db.update_lead_notes(lead['id'], mark_notes)
                            
                            st.success(f"🎉 Done! Next follow-up: {final_date}")
                            time.sleep(3)
                            st.rerun()
                
                else:
                    # Handle Reply mode
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
                        
                    st.info("✏️ Edit your reply below, then copy:")
                    edited_reply = st.text_area("Edit Reply:", value=final_script, height=150, key=f"reply_edit_{lead['id']}")
                    st.caption("👇 Copy from here:")
                    st.code(edited_reply, language=None)
                    
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
                
                # --- COLLAPSED MANUAL RESEARCH (fallback if Apollo didn't find contact) ---
                st.divider()
                expand_research = not has_contact  # Auto-expand if no contact found
                with st.expander("🔍 Manual Research Tools (if needed)", expanded=expand_research):
                    st.caption("Use these if Apollo didn't find the decision-maker, or you want to verify.")
                    
                    def google_link(query, label):
                        url = f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}"
                        st.markdown(f"• [{label}]({url})")
                    
                    r_c1, r_c2 = st.columns(2)
                    with r_c1:
                        st.markdown("**🏛️ Companies House**")
                        ch_num = lead_notes_data.get('ch_company_number', '')
                        if ch_num:
                            ch_url = f"https://find-and-update.company-information.service.gov.uk/company/{ch_num}"
                            st.markdown(f"• [View Company Filing]({ch_url})")
                        else:
                            ch_search = f"https://find-and-update.company-information.service.gov.uk/search?q={urllib.parse.quote_plus(lead['Business Name'])}"
                            st.markdown(f"• [Search Companies House]({ch_search})")
                        
                        st.markdown("**👔 LinkedIn**")
                        li_company = f"https://www.linkedin.com/search/results/companies/?keywords={urllib.parse.quote_plus(lead['Business Name'])}"
                        st.markdown(f"• [Search Companies]({li_company})")
                        li_people = f"https://www.linkedin.com/search/results/people/?keywords={urllib.parse.quote_plus(lead['Business Name'])}"
                        st.markdown(f"• [Search People]({li_people})")
                        if clean_contact and has_contact:
                            li_person = f"https://www.linkedin.com/search/results/people/?keywords={urllib.parse.quote_plus(clean_contact)}"
                            st.markdown(f"• [Find {clean_contact}]({li_person})")
                    
                    with r_c2:
                        st.markdown("**🌍 Web Search**")
                        google_link(f'{lead["Business Name"]}', "Google Search")
                        google_link(f'{lead["Business Name"]} sponsorship', "Sponsorship Check")
                        google_link(f'"{lead["Business Name"]}" after:2025-01-01', "Latest News")
                        
                        st.markdown("**👤 Facebook**")
                        fb_company = f"https://www.facebook.com/search/pages/?q={urllib.parse.quote_plus(lead['Business Name'])}"
                        st.markdown(f"• [Company Page]({fb_company})")
                        fb_people = f"https://www.facebook.com/search/people/?q={urllib.parse.quote_plus(lead['Business Name'])}"
                        st.markdown(f"• [Find Owner]({fb_people})")

            # --- STAGE 2: DISCOVERY CALL ---
            elif stage == "2. Discovery Call":
                st.subheader("📞 Discovery Call — Guided Script")
                
                # Load existing notes
                existing_notes = lead.get('Notes', {})
                if isinstance(existing_notes, str):
                    try: existing_notes = json.loads(existing_notes)
                    except: existing_notes = {}
                if not isinstance(existing_notes, dict): existing_notes = {}
                
                contact_name = lead.get('Contact Name', '') or lead['Business Name']
                # Strip Apollo-style title suffix: "Neil Wearing (Depot Manager)" → "Neil Wearing"
                if "(" in contact_name:
                    contact_name = contact_name[:contact_name.index("(")].strip()
                first_name = contact_name.split()[0] if contact_name else "there"
                
                # ---- AUTO-POPULATED COMPANY INTEL ----
                with st.expander("🔍 Pre-Call Intel (Auto-Populated)", expanded=True):
                    st.caption("Review this before the call — reference something specific early to prove you did your homework.")
                    
                    intel_c1, intel_c2 = st.columns(2)
                    with intel_c1:
                        st.markdown(f"**Company:** {lead['Business Name']}")
                        st.markdown(f"**Sector:** {lead.get('Sector', '—')}")
                        if existing_notes.get('industry'):
                            st.markdown(f"**Industry:** {existing_notes['industry']}")
                        st.markdown(f"**Contact:** {contact_name}")
                        if existing_notes.get('owner_title'):
                            st.markdown(f"**Title:** {existing_notes['owner_title']}")
                        if lead.get('Website'):
                            st.markdown(f"🌐 [{lead['Website']}]({lead['Website']})")
                        
                        # Owner personal LinkedIn
                        owner_li = existing_notes.get('owner_linkedin', '')
                        if owner_li:
                            st.markdown(f"👤 [Decision-Maker LinkedIn]({owner_li})")
                        
                        # LinkedIn Company Page
                        li_company = existing_notes.get('linkedin_company', '')
                        if li_company:
                            st.markdown(f"🏢 [Company LinkedIn]({li_company})")
                        
                    with intel_c2:
                        # Company size and revenue
                        size = existing_notes.get('company_size', '')
                        emp_count = existing_notes.get('employee_count', '')
                        revenue = existing_notes.get('revenue', '')
                        founded = existing_notes.get('founded_year', '')
                        
                        if size:
                            st.markdown(f"**Size:** {size}")
                        elif emp_count:
                            st.markdown(f"**Employees:** {emp_count}")
                        if revenue:
                            st.markdown(f"**Revenue:** {revenue}")
                        if founded:
                            import datetime
                            years_old = datetime.datetime.now().year - int(founded) if founded else 0
                            st.markdown(f"**Founded:** {founded} ({years_old} years)")
                        
                        desc = existing_notes.get('description', '')
                        if desc:
                            st.markdown(f"**About:** {desc[:200]}")
                        
                        owner = existing_notes.get('owner', '')
                        if owner:
                            st.markdown(f"**Decision-Maker:** {owner}")

                        # Email
                        enriched_email = existing_notes.get('email', '')
                        if enriched_email:
                            st.markdown(f"**📧 Email:** {enriched_email}")
                        all_emails = existing_notes.get('emails', [])
                        if isinstance(all_emails, list) and len(all_emails) > 1:
                            extra = [e for e in all_emails if e != enriched_email]
                            if extra:
                                st.markdown(f"**Other emails:** {', '.join(extra)}")

                        # Phone
                        direct_phone = existing_notes.get('direct_phone', '')
                        company_phone = existing_notes.get('company_phone', '')
                        phones = existing_notes.get('phones', [])
                        if direct_phone:
                            st.markdown(f"**📱 Direct:** {direct_phone}")
                        if company_phone:
                            st.markdown(f"**📞 Office:** {company_phone}")
                        elif isinstance(phones, list) and phones:
                            st.markdown(f"**📞 Phone:** {phones[0]}")
                        if isinstance(phones, list) and len(phones) > 1:
                            st.markdown(f"**Other phones:** {', '.join(phones[1:])}")
                        
                        # Social links
                        social = existing_notes.get('social_links', {})
                        if isinstance(social, dict) and social:
                            links = []
                            if social.get('linkedin'): links.append(f"[LinkedIn]({social['linkedin']})")
                            if social.get('facebook'): links.append(f"[Facebook]({social['facebook']})")
                            if social.get('instagram'): links.append(f"[Instagram]({social['instagram']})")
                            if social.get('twitter'): links.append(f"[Twitter]({social['twitter']})")
                            if social.get('youtube'): links.append(f"[YouTube]({social['youtube']})")
                            if links:
                                st.markdown("**Social:** " + " • ".join(links))
                    
                    # Alternate contacts (other directors/managers found by Apollo)
                    alt_contacts = existing_notes.get('alternate_contacts', [])
                    if isinstance(alt_contacts, list) and alt_contacts:
                        with st.container():
                            st.markdown("**👥 Other Key People:**")
                            for alt in alt_contacts:
                                alt_line = f"• **{alt.get('name', '')}** — {alt.get('title', '')}"
                                if alt.get('email'):
                                    alt_line += f" | {alt['email']}"
                                if alt.get('linkedin'):
                                    alt_line += f" | [LinkedIn]({alt['linkedin']})"
                                st.markdown(alt_line)
                    
                    homework_notes = st.text_area(
                        "✏️ Your homework notes (2-3 things you noticed about their business)",
                        value=existing_notes.get('homework_notes', ''),
                        height=80, 
                        placeholder="e.g. Just opened a new site, posted about team expansion on LinkedIn, competitor sponsors a BSB team..."
                    )
                
                st.divider()
                
                # ---- 1. THE WARM OPEN ----
                with st.expander("1️⃣ The Warm Open (Script)", expanded=False):
                    rep_mode = user_profile.get("rep_mode", False)
                    rep_name = user_profile.get("rep_name", "")
                    
                    if rep_mode and rep_name:
                        intro_line = f"I'm {rep_name}, calling on behalf of {rider_name}"
                    else:
                        intro_line = f"I'm {rider_name}"
                    
                    st.markdown(f"""
*"Hi {first_name}, thanks so much for making the time — I really appreciate it."*

*"{intro_line} and we're currently in the final stages of putting together our partner group for the {championship} season."*

*"I want to be straight with you — this call isn't about asking for money. Before I even think about putting a proposal together, I want to make sure what we do actually makes sense for your business. So I'd love to ask you a few questions if that's okay — it'll only take about 10 minutes."*

⏸️ **Wait for "yes" before continuing — this consent creates buy-in**
""")
                
                st.divider()
                
                # ---- 2. DISCOVERY QUESTIONS ----
                st.subheader("2️⃣ Discovery Questions")
                st.caption("Work through these conversationally. Every answer is a building block for the proposal.")
                
                with st.form("discovery_form_v2"):
                    answers = {}
                    
                    # Q1 — Past Experience
                    st.markdown("---")
                    st.markdown("**Q1 — Past Experience**")
                    st.markdown('*"Have you ever been involved in sponsorship before, whether motorsport or anything else?"*')
                    st.caption("🎯 Listen for: what worked, what didn't, what they wish they'd got")
                    st.caption("If yes → *'How did that go?'* / If no → *'Is there a reason, or just never come up?'*")
                    answers['past_experience'] = st.text_area("Their answer:", value=existing_notes.get('past_experience', ''), height=70, key="dq1")
                    
                    # Q2 — Ideal Outcome
                    st.markdown("---")
                    st.markdown("**Q2 — Ideal Outcome** *(This becomes the headline of the proposal)*")
                    st.markdown('*"If we did work together this season and it went really well — what would that actually look like for you?"*')
                    st.caption("🎯 Listen for: their primary motivation. Probe: *'New customers, visibility, staff engagement, or entertaining clients?'*")
                    answers['ideal_outcome'] = st.text_area("Their answer:", value=existing_notes.get('ideal_outcome', ''), height=70, key="dq2")
                    
                    # Q3 — What Matters Most
                    st.markdown("---")
                    st.markdown("**Q3 — Most Important Elements**")
                    st.markdown('*"If you were putting a package together, what would be the most important elements for you?"*')
                    st.caption("🎯 Examples if stuck: logo on bike/kit, event hospitality, social media, B2B paddock intros, customer competitions, staff experiences")
                    answers['important_elements'] = st.text_area("Their answer:", value=existing_notes.get('important_elements', ''), height=70, key="dq3")
                    
                    # Q4 — Staff Angle
                    st.markdown("---")
                    st.markdown("**Q4 — Staff & Team Benefit**")
                    st.markdown('*"Do you think your team could get something out of this — coming to a race, being part of something exciting?"*')
                    st.caption("🎯 Listen for: internal buy-in. If yes → *'What would they get most excited about?'*")
                    answers['staff_angle'] = st.text_area("Their answer:", value=existing_notes.get('staff_angle', ''), height=70, key="dq4")
                    
                    # Q5 — Customer Angle
                    st.markdown("---")
                    st.markdown("**Q5 — Customer Benefit**")
                    st.markdown('*"What about your customers — could you see using this as a promotion, loyalty reward, or memorable experience?"*')
                    st.caption("🎯 Listen for: commercial use case. If yes → *'Tell me more — what kind of customers?'*")
                    answers['customer_angle'] = st.text_area("Their answer:", value=existing_notes.get('customer_angle', ''), height=70, key="dq5")
                    
                    # Q6 — Local Activation
                    st.markdown("---")
                    st.markdown("**Q6 — Local Round / Activation**")
                    st.markdown('*"We have a round at [nearest circuit] this season. Is there anything you would want to do around that?"*')
                    st.caption("🎯 Listen for: activation appetite. If they light up, this is the centrepiece of the proposal.")
                    answers['local_activation'] = st.text_area("Their answer:", value=existing_notes.get('local_activation', ''), height=70, key="dq6")
                    
                    # Q7 — Budget Signals
                    st.markdown("---")
                    st.markdown("**Q7 — Budget & Timing Signals**")
                    st.caption("Not a question you ask directly — just note anything they mention about budgets, timing, or decision process.")
                    answers['budget_signals'] = st.text_area("Notes:", value=existing_notes.get('budget_signals', ''), height=70, key="dq7")
                    
                    st.markdown("---")
                    
                    # Follow-up logistics
                    log_c1, log_c2 = st.columns(2)
                    with log_c1:
                        proposal_date = st.text_input("📅 Proposal send date:", value=existing_notes.get('proposal_send_date', ''), placeholder="e.g. Tuesday 4th March", key="dq_date")
                    with log_c2:
                        next_call = st.text_input("📞 Next call booked for:", value=existing_notes.get('next_call_date', ''), placeholder="e.g. Thursday 6th March 2pm", key="dq_call")
                    
                    answers['proposal_send_date'] = proposal_date
                    answers['next_call_date'] = next_call
                    answers['homework_notes'] = homework_notes
                    
                    if st.form_submit_button("💾 Save Call Notes", type="primary"):
                        existing_notes.update(answers)
                        db.update_lead_notes(lead['id'], existing_notes)
                        st.success("✅ All answers saved — ready to build the proposal!")
                
                st.divider()
                
                # ---- 3. THE SOFT CLOSE ----
                with st.expander("3️⃣ Closing The Call (Script)", expanded=False):
                    ideal = existing_notes.get('ideal_outcome', '[their goal]')
                    p_date = existing_notes.get('proposal_send_date', '[specific day]')
                    st.markdown(f"""
*"That's been really useful, thank you. Based on what you've said about {ideal}, I've actually got a couple of ideas already about how we could make that work."*

*"I'll put something together and send it over by **{p_date}**. It won't be long, just the key points so you can give me honest feedback on it."*

*"When would work for a quick 10-minute call to go through it?"*

⚡ **Book it before you hang up**
""")
                
                st.divider()
                
                # ---- 4. NOTESHEET SUMMARY ----
                with st.expander("4️⃣ Call Summary", expanded=False):
                    st.markdown("### Call Notesheet")
                    summary_data = {
                        "Sponsorship experience": existing_notes.get('past_experience', '—'),
                        "Ideal outcome": existing_notes.get('ideal_outcome', '—'),
                        "Most important elements": existing_notes.get('important_elements', '—'),
                        "Staff benefit angle": existing_notes.get('staff_angle', '—'),
                        "Customer benefit angle": existing_notes.get('customer_angle', '—'),
                        "Local activation ideas": existing_notes.get('local_activation', '—'),
                        "Budget signals": existing_notes.get('budget_signals', '—'),
                        "Proposal send date": existing_notes.get('proposal_send_date', '—'),
                        "Next call booked": existing_notes.get('next_call_date', '—'),
                    }
                    for label, val in summary_data.items():
                        st.markdown(f"**{label}:** {val}")
                
                st.divider()
                st.caption("💡 **Golden Rule:** The less you talk, the better the proposal will be. Ask, listen, take notes.")
                
                if st.button("✅ Mark Call Complete → Move to Proposal", type="primary"):
                    db.update_lead_status(lead['id'], "Discovery Call")
                    st.success("Call logged. Switch to 'Proposal' stage to generate your deck.")
                    time.sleep(1)
                    st.rerun()


                
            elif stage == "3. Proposal":
                st.subheader(f"📝 Proposal Creator for {lead['Business Name']}")
                st.caption("Based on *The Blueprint of Approval: Strategic Architecture for Winning Motorsport Sponsorship Proposals*")
                
                # --- PREPARE DATA ---
                r_name = st.session_state.user_name
                r_series = championship
                r_bio = st.session_state.user_profile.get('bio', f"A competitive racer in {r_series}. Known for consistency and speed.")
                r_audience = st.session_state.user_profile.get('audience', 'Growing')
                r_town = st.session_state.user_profile.get('town', '')
                r_country = st.session_state.user_profile.get('country', '')
                r_vehicle = st.session_state.user_profile.get('vehicle', 'Vehicle')
                r_competitors = st.session_state.user_profile.get('competitors', 20)
                r_spectators = st.session_state.user_profile.get('audience', '5000')
                r_tv = st.session_state.user_profile.get('tv', '') if st.session_state.user_profile.get('televised') == "Yes" else ""
                r_streamed = st.session_state.user_profile.get('streamed', 'No')
                r_goal = season_goal
                r_prev_champ = prev_champ
                r_achievements = achievements
                r_team = team_name
                l_name = lead['Business Name']
                l_sector = lead.get('Sector', '')
                l_website = lead.get('Website', '')
                l_address = lead.get('Address', '')
                l_contact = lead.get('Contact Name', '')
                l_notes = lead.get('Notes', {})
                if isinstance(l_notes, str):
                    try: l_notes = json.loads(l_notes)
                    except: l_notes = {}
                if not isinstance(l_notes, dict): l_notes = {}

                # Deep Discovery Context
                disc_context = ""
                has_answers = False
                disc_keys = {
                    "past_experience": "Sponsorship Experience",
                    "ideal_outcome": "Ideal Outcome",
                    "important_elements": "Most Important Elements",
                    "staff_angle": "Staff Benefit",
                    "customer_angle": "Customer Benefit",
                    "local_activation": "Local Activation",
                    "budget_signals": "Budget Signals"
                }
                for key, label in disc_keys.items():
                    answer = l_notes.get(key, "").strip() if isinstance(l_notes.get(key), str) else ""
                    if answer:
                        has_answers = True
                        disc_context += f"- **{label}:** \"{answer}\"\n"
                
                if not has_answers:
                     st.warning("⚠️ No Discovery Call data found. Complete the Discovery Call first — proposals built from client voice have 3x higher close rate.")
                else:
                    st.success("✅ Discovery Call data loaded — your proposal will be tailored to their exact needs.")

                # --- COMPANY LOGO ---
                st.markdown("---")
                st.markdown("### 🏢 Company Branding")
                
                logo_col1, logo_col2 = st.columns([1, 1])
                with logo_col1:
                    st.markdown("**Company Logo**")
                    st.caption("We'll try to auto-fetch the logo from their website. You can also upload one manually.")
                    
                    logo_source = st.radio("Logo Source", ["Auto-fetch from website", "Upload manually"], key="logo_src", horizontal=True)
                    
                    company_logo_url = ""
                    uploaded_logo = None
                    
                    if logo_source == "Auto-fetch from website":
                        if l_website:
                            domain = l_website.replace("https://", "").replace("http://", "").replace("www.", "").strip("/").split("/")[0]
                            company_logo_url = f"https://logo.clearbit.com/{domain}"
                            st.image(company_logo_url, width=150, caption=f"Auto-fetched: {domain}")
                            st.caption("💡 Logo fetched from Clearbit. If this doesn't look right, switch to manual upload.")
                        else:
                            st.info("No website on file — please upload the logo manually or add their website in the Connect stage.")
                    else:
                        uploaded_logo = st.file_uploader("Upload Company Logo", type=["png", "jpg", "jpeg", "svg"], key="upload_logo")
                        if uploaded_logo:
                            st.image(uploaded_logo, width=150, caption="Uploaded Logo")
                
                with logo_col2:
                    st.markdown("**Your Photos**")
                    st.caption("Upload a professional headshot and action photo for the proposal deck.")
                    
                    uploaded_headshot = st.file_uploader("Your Headshot / Portrait", type=["png", "jpg", "jpeg"], key="upload_headshot")
                    if uploaded_headshot:
                        st.image(uploaded_headshot, width=120, caption="Headshot")
                    
                    uploaded_action = st.file_uploader(f"Action Photo ({r_vehicle})", type=["png", "jpg", "jpeg"], key="upload_action")
                    if uploaded_action:
                        st.image(uploaded_action, width=200, caption="Action Photo")
                
                # Background / Theme
                st.markdown("---")
                bg_col1, bg_col2 = st.columns(2)
                with bg_col1:
                    deck_theme = st.selectbox("Deck Theme", [
                        "Dark & Premium (Carbon Fiber)", 
                        "Clean White & Professional",
                        "Racing Red & Black",
                        "Corporate Blue & Grey",
                        "Custom (Sponsor Brand Colors)"
                    ], key="deck_theme")
                with bg_col2:
                    uploaded_mockup = st.file_uploader(f"Livery Mockup (Optional — {r_vehicle} in sponsor colors)", type=["png", "jpg", "jpeg"], key="upload_mockup")
                    if uploaded_mockup:
                        st.image(uploaded_mockup, width=200, caption="Livery Mockup")

                # ============================================
                # THE 12-SLIDE YES-GENERATING PROPOSAL BUILDER
                # ============================================
                st.markdown("---")
                st.markdown("### 📑 The 12-Slide 'YES-GENERATING' Proposal")
                st.caption("Based on *The Blueprint of Approval*. Every field is auto-filled from your profile and discovery call. Edit anything to perfect it.")
                
                with st.form("proposal_deck_builder_v3"):
                    
                    # ---- SLIDE 1: EXECUTIVE SUMMARY ----
                    with st.expander("📌 Slide 1: Executive Summary (The One-Page Sell)", expanded=True):
                        st.info("💡 **Blueprint Tip:** This is NOT about you needing money. Frame it as: *'Here is how we solve your marketing challenge.'* The sponsor should see their ROI before they see your race number.")
                        
                        # Auto-generate title from discovery data
                        ideal = l_notes.get('ideal_outcome', '').strip()
                        if ideal:
                            auto_title = f"{r_name} × {l_name}: Driving {ideal.split('.')[0].capitalize()}"
                        else:
                            auto_title = f"{r_name} × {l_name}: Strategic Partnership Proposal {datetime.now().year}"
                        
                        s1_title = st.text_input("Proposal Title", value=auto_title, help="Lead with THEIR goal, not yours.")
                        
                        # Auto-generate summary
                        if ideal:
                            auto_summary = f"A strategic marketing partnership designed to deliver {ideal.lower()} through the {r_series} platform. This proposal outlines a measurable, activation-led sponsorship with {r_name} that positions {l_name} in front of {r_spectators}+ engaged fans per event."
                        else:
                            auto_summary = f"A commercial partnership opportunity with {r_name} in the {r_series}. This proposal outlines brand exposure, activation opportunities, and measurable returns for {l_name}."
                        
                        s1_summary = st.text_area("Executive Summary (3-4 sentences)", value=auto_summary, height=100)
                        
                        st.warning("⚡ **Recommendation:** If you learned their ideal outcome in the discovery call, lead with that. Sponsors who see their own goals reflected in the first 10 seconds are 4x more likely to read the full proposal.")
                    
                    # ---- SLIDE 2: ATHLETE PROFILE ----
                    with st.expander("👤 Slide 2: Athlete Profile (Why You?)", expanded=False):
                        st.info("💡 **Blueprint Tip:** People invest in people. Share your story in a way that creates emotional connection AND demonstrates professionalism.")
                        
                        p2_c1, p2_c2 = st.columns(2)
                        s2_name = p2_c1.text_input("Full Name", value=r_name)
                        s2_racing_num = p2_c2.text_input("Racing Name / Number", value=f"{r_name} #__")
                        
                        p2_c3, p2_c4, p2_c5 = st.columns(3)
                        s2_age = p2_c3.text_input("Age", placeholder="e.g. 24")
                        s2_home = p2_c4.text_input("Hometown", value=f"{r_town}, {r_country}" if r_town else "")
                        s2_cat = p2_c5.text_input("Racing Category", value=r_series)
                        
                        s2_story = st.text_area("Your Personal Story (300-500 words)", value=r_bio, height=150, help="This is your chance to build an emotional investment. Share WHY you race, not just WHAT you do.")
                        s2_mission = st.text_input("Mission Statement", value="To compete at the highest level while delivering exceptional value to commercial partners.", help="Clear, professional, ambitious.")
                        s2_vision = st.text_area("Long-Term Vision (3-5 years)", value=f"To progress from {r_series} to the next level of professional motorsport.", help="Show them this is a long-term investment, not a one-season deal.")
                        s2_team = st.text_input("Team & Support Network", value=r_team if r_team else "Team Name — Managed by [Name], Engineered by [Name]")
                    
                    # ---- SLIDE 3: PERFORMANCE & VALUE ----
                    with st.expander("📊 Slide 3: Performance & Value (The Data)", expanded=False):
                        st.info("📊 **Blueprint Tip:** Lead with DATA. Sponsors want measurable proof of your trajectory and competitiveness. This is where credibility is built.")
                        
                        st.markdown("**Current Season Performance**")
                        p3_c1, p3_c2, p3_c3 = st.columns(3)
                        p_races = p3_c1.number_input("Races Entered", min_value=0, value=10)
                        p_wins = p3_c2.number_input("Wins", min_value=0, value=0)
                        p_podiums = p3_c3.number_input("Podium Finishes", min_value=0, value=0)
                        
                        p3_c4, p3_c5, p3_c6 = st.columns(3)
                        p_top10 = p3_c4.number_input("Top 10 Finishes", min_value=0, value=0)
                        p_poles = p3_c5.number_input("Pole Positions", min_value=0, value=0)
                        p_frontrow = p3_c6.number_input("Front Row Starts", min_value=0, value=0)
                        
                        p3_c7, p3_c8 = st.columns(2)
                        p_pos = p3_c7.text_input("Championship Position", value="")
                        p_points = p3_c8.number_input("Championship Points", min_value=0, value=0)
                        
                        # AUTO-CALC
                        win_rate = (p_wins / p_races * 100) if p_races > 0 else 0
                        podium_rate = (p_podiums / p_races * 100) if p_races > 0 else 0
                        top10_rate = (p_top10 / p_races * 100) if p_races > 0 else 0
                        
                        st.caption(f"📈 **Auto-Calculated:** Win Rate: {win_rate:.1f}% | Podium Rate: {podium_rate:.1f}% | Top 10: {top10_rate:.1f}%")
                        
                        s3_highlights = st.text_area("Career Highlights (Timeline)", value=r_achievements if r_achievements else "2024: [Result]\n2025: [Result]", help="Year-by-year progression shows trajectory.")
                        s3_goals = st.text_area("2026 Season Goals", value=r_goal if r_goal else "1. Championship Title\n2. Consistent Podiums", help="Ambitious but realistic.")
                        
                        s3_metrics = f"Races: {p_races} | Wins: {p_wins} ({win_rate:.0f}%) | Podiums: {p_podiums} ({podium_rate:.0f}%) | Top 10: {p_top10} ({top10_rate:.0f}%) | Poles: {p_poles} | Champ Pos: {p_pos}"
                        
                        st.warning("⚡ **Recommendation:** Include qualifying vs race pace if available. Show improvement trajectory year-over-year — even small gains prove momentum.")
                    
                    # ---- SLIDE 4: THE PLATFORM ----
                    with st.expander("🏁 Slide 4: The Platform (Championship Value)", expanded=False):
                        st.info("💡 **Blueprint Tip:** Sponsors don't sponsor YOU — they sponsor the PLATFORM you stand on. Show the size of the stage.")
                        
                        auto_platform = f"{r_series}: {r_competitors} competitors. "
                        if r_tv:
                            auto_platform += f"Televised to {r_tv} viewers. "
                        if r_streamed == "Yes":
                            auto_platform += "Live-streamed globally. "
                        auto_platform += f"Average {r_spectators} spectators per event."
                        
                        s4_series = st.text_area("Championship Overview", value=auto_platform, height=80)
                        
                        p4_c1, p4_c2 = st.columns(2)
                        s4_rounds = p4_c1.text_input("Number of Rounds", placeholder="e.g. 8 rounds, April-October")
                        s4_circuits = p4_c2.text_input("Key Venues", placeholder="e.g. Brands Hatch, Silverstone, Donington")
                        
                        s4_media = st.text_area("Media & Broadcast Details", value="TV: [Broadcaster]\nStreaming: [Platform]\nSocial Reach: [Combined Followers]", help="Include viewership, countries reached, event attendance.")
                        
                        st.warning("⚡ **Recommendation:** Get official figures from the championship organiser — TV audience, social reach, event attendance. Real numbers beat estimates.")
                    
                    # ---- SLIDE 5: AUDIENCE ----
                    with st.expander("👥 Slide 5: Audience & Fan Demographics", expanded=False):
                        st.info("💡 **Blueprint Tip:** Show EXACTLY who sees the sponsor. Break down by age, gender, income, interests, buying behaviour. No fake metrics. No inflated numbers.")
                        
                        auto_audience = f"Total Reach: {r_audience}\n"
                        auto_audience += "Demographics:\n- Age: 25-55 (70% of audience)\n- Gender: 70% Male / 30% Female\n- Income: Above-average disposable income\n- Interests: Motorsport, automotive, technology, fitness"
                        
                        s5_data = st.text_area("Audience Profile & Demographics", value=auto_audience, height=120)
                        
                        st.markdown("**Your Digital Reach (Real Numbers Only)**")
                        p5_c1, p5_c2, p5_c3, p5_c4 = st.columns(4)
                        s5_insta = p5_c1.text_input("Instagram Followers", placeholder="e.g. 5,200")
                        s5_fb = p5_c2.text_input("Facebook Followers", placeholder="e.g. 2,100")
                        s5_yt = p5_c3.text_input("YouTube Subscribers", placeholder="e.g. 800")
                        s5_tiktok = p5_c4.text_input("TikTok Followers", placeholder="e.g. 1,500")
                        
                        s5_engagement = st.text_input("Average Engagement Rate", placeholder="e.g. 4.5% (higher than industry avg of 1.5%)")
                        
                        st.warning("⚡ **Recommendation:** Even small followings convert if engagement is high. A 5,000-follower account with 5% engagement beats a 50,000-follower account with 0.3%. Show your authentic engagement rate.")
                    
                    # ---- SLIDE 6: BRAND VALUE PROPOSITION ----
                    st.markdown("---")
                    st.error("👇 **CRITICAL SECTION: The Commercial Heart of Your Proposal**")
                    
                    with st.container(border=True):
                        st.markdown("#### 💰 Slide 6: Brand Value Proposition (Why This Makes Them Money)")
                        st.info("💡 **Blueprint Tip:** This is the COMMERCIAL HEART of the proposal. Translate motorsport into business outcomes. Speak the language of 'marketing services', not 'racing'.")
                        
                        # Auto-generate from discovery data
                        auto_benefits = "1. Brand Visibility — Logo on livery seen by thousands per event + digital reach\n"
                        auto_benefits += "2. B2B Networking — Exclusive paddock access for client hospitality\n"
                        auto_benefits += "3. Content Rights — Professional photos, videos, behind-the-scenes for your marketing"
                        
                        important = l_notes.get('important_elements', '').strip()
                        customer = l_notes.get('customer_angle', '').strip()
                        staff = l_notes.get('staff_angle', '').strip()
                        
                        if important:
                            auto_benefits = f"Based on your discovery call, {l_contact or l_name} values:\n- {important}\n\nWe deliver:\n"
                            auto_benefits += "1. Brand Visibility — Logo placement across all platforms\n"
                            auto_benefits += "2. Lead Generation — Direct access to engaged audience\n"
                            auto_benefits += "3. Customer Loyalty — VIP experiences that money can't buy"
                        if customer:
                            auto_benefits += f"\n4. Customer Activation — {customer}"
                        if staff:
                            auto_benefits += f"\n5. Staff Engagement — {staff}"
                        
                        s6_value = st.text_area("What the sponsor GETS (Business Outcomes)", value=auto_benefits, height=150)
                        
                        st.warning("⚡ **Recommendation:** Mirror their exact words from the discovery call. If they said 'get in front of new customers', use those exact words — not 'brand awareness'.")
                    
                    # ---- SLIDE 7: DELIVERABLES & ACTIVATION ----
                    with st.container(border=True):
                        st.markdown("#### 🎯 Slide 7: Deliverables & Activation Plan")
                        st.info("💡 **Blueprint Tip:** This should feel like a MARKETING CAMPAIGN, not a racing hobby. List specific, measurable deliverables.")
                        
                        local_act = l_notes.get('local_activation', '').strip()
                        
                        auto_deliverables = f"**Brand Visibility:**\n- {r_vehicle} livery (primary/secondary placement)\n- Race suit & helmet branding\n- Team apparel & garage signage\n\n"
                        auto_deliverables += "**Media & Content:**\n- Minimum 2x dedicated social posts per event\n- Behind-the-scenes video content\n- Press release mentions & interview features\n- Website logo placement with backlink\n\n"
                        auto_deliverables += "**Events & Hospitality:**\n- VIP paddock passes (per event)\n- Grid walk access\n- Corporate hospitality days\n- Meet & greet opportunities\n\n"
                        auto_deliverables += "**Community & PR:**\n- Joint charity / community events\n- Product launch appearances\n- School visit programme\n"
                        
                        if local_act:
                            auto_deliverables += f"\n**Local Activation (from Discovery Call):**\n- {local_act}"
                        
                        s7_act = st.text_area("Activation & Deliverables", value=auto_deliverables, height=250)
                        
                        st.warning("⚡ **Recommendation:** Be SPECIFIC. Instead of 'social media posts', say '24 dedicated Instagram posts + 12 Reels across the season'. Numbers make it feel tangible and valuable.")
                    
                    # ---- SLIDE 8: SUSTAINABILITY & ESG ----
                    with st.expander("🌱 Slide 8: Sustainability & ESG (Modern Requirement)", expanded=False):
                        st.info("💡 **Blueprint Tip:** Keep it authentic and minimal. No corporate nonsense. Only list real commitments.")
                        
                        s8_esg = st.text_area("ESG & Sustainability Commitments", value="- Carbon-conscious travel planning\n- Youth coaching & mentorship programs\n- Road safety advocacy\n- Community engagement & school visits", height=100)
                        
                        st.caption("💡 Even a simple commitment to local community work counts. Don't fabricate ESG credentials.")
                    
                    # ---- SLIDE 9: SPONSORSHIP PACKAGES ----
                    st.markdown("---")
                    st.error("👇 **CRITICAL SECTION: Make It Easy To Say Yes**")
                    
                    with st.container(border=True):
                        st.markdown("#### 💎 Slide 9: Sponsorship Packages")
                        st.info("💡 **Blueprint Tip:** Offer 3-4 tiers to anchor the price. The middle tier is your target — most sponsors choose the middle option. Always leave room for custom deals.")
                        
                        # Try to price-anchor from budget signals
                        budget = l_notes.get('budget_signals', '').strip()
                        budget_hint = ""
                        if budget:
                            budget_hint = f"\n\n💰 **Budget Signal from Discovery:** \"{budget}\""
                        
                        auto_packages = "**🏆 Platinum Partner** — £XX,000\n"
                        auto_packages += "- Title naming rights\n- Primary logo on livery\n- Full season hospitality (all rounds)\n- Exclusive content integration\n- Speaking at team events\n\n"
                        auto_packages += "**🥇 Gold Partner** — £XX,000\n"
                        auto_packages += "- Major branding placement\n- VIP passes (selected rounds)\n- Regular social content features\n- Press release mentions\n\n"
                        auto_packages += "**🥈 Silver Partner** — £X,000\n"
                        auto_packages += "- Logo placement on vehicle\n- Social media features\n- Event day access\n\n"
                        auto_packages += "**🤝 Support Partner** — £X,000\n"
                        auto_packages += "- Entry-level exposure\n- Digital presence\n- Recognition on materials"
                        
                        s9_tiers = st.text_area("Investment Tiers", value=auto_packages, height=250)
                        
                        if budget_hint:
                            st.info(budget_hint)
                        
                        st.warning("⚡ **Recommendation:** Price the middle tier at what you actually want. The top tier makes the middle look reasonable. The bottom tier catches those who want in but have less budget. Always add: 'Custom packages available to match your specific objectives.'")
                    
                    # ---- SLIDE 10: ROI & MEDIA VALUE ----
                    with st.expander("📈 Slide 10: ROI & Media Value", expanded=False):
                        st.info("💡 **Blueprint Tip:** Justify the spend with QUANTIFIED returns. Show 2:1 to 4:1 return projections. Include: estimated impressions, media value equivalency, hospitality value, and direct sales potential.")
                        
                        s10_roi = st.text_area("ROI Breakdown", value="**Estimated Media Value:**\n- Livery exposure per event: £X,000 (based on X hrs broadcast time)\n- Social media reach: X impressions per month\n- Website traffic referral: X visits per annum\n\n**Hospitality Value:**\n- VIP experience market rate: £X per person × X guests = £X,000\n\n**Total Estimated Returns:** £XX,000 (X:1 ratio vs investment)", height=150)
                        
                        st.warning("⚡ **Recommendation:** Use the formula: Media Value + Hospitality Value + Content Value + Networking Value > Investment. If returns > 2:1, lead with that number.")
                    
                    # ---- SLIDE 11: VISUAL PROOF ----
                    with st.container(border=True):
                        st.markdown("#### 🎨 Slide 11: Visual Proof (Mockups)")
                        st.info("💡 **Blueprint Tip:** Show them what the partnership LOOKS like. A render of their logo on your vehicle is worth 1,000 words. This is where 'maybe' becomes 'yes'.")
                        
                        s11_visuals = st.text_area("Describe the mockups/visuals to include", value=f"1. {r_vehicle} livery render in {l_name} brand colors\n2. Race suit with {l_name} logo placement\n3. Social media post mockup featuring {l_name}\n4. Hospitality zone branding concept", height=100)
                        
                        st.warning("⚡ **Recommendation:** Even a simple Photoshop mockup of their logo on your vehicle is incredibly powerful. If you uploaded a livery mockup above, Manus will incorporate it into the deck.")
                    
                    # ---- SLIDE 12: CLOSING & CALL TO ACTION ----
                    with st.expander("🤝 Slide 12: Partnership Statement & CTA", expanded=False):
                        st.info("💡 **Blueprint Tip:** End with a clear, low-pressure call to action. Don't ask them to sign — ask them to DISCUSS. Remove all friction.")
                        
                        s12_close = st.text_input("Closing Statement", value=f"Let's build a winning partnership for {datetime.now().year}.")
                        s12_cta = st.text_area("Call to Action", value=f"I'd welcome a 15-minute call to discuss how we can tailor this to your exact objectives.\n\nNo commitment needed — just a conversation.\n\nContact: {r_name}\nEmail: [Your Email]\nPhone: [Your Phone]", height=100)
                        
                        st.warning("⚡ **Recommendation:** The best CTA is: 'Reply with your thoughts — even if it's a no, I'd appreciate the feedback.' This removes pressure and often gets a 'let's talk' reply.")
                    
                    # ============================================
                    # GENERATE
                    # ============================================
                    st.markdown("---")
                    st.markdown("### 🚀 Generate Your Proposal")
                    
                    gen_c1, gen_c2 = st.columns(2)
                    with gen_c1:
                        include_images_note = "✅ Images uploaded" if (uploaded_logo or uploaded_headshot or uploaded_action or uploaded_mockup) else "⚠️ No images uploaded — deck will use placeholders"
                        st.caption(include_images_note)
                    with gen_c2:
                        st.caption(f"Theme: {deck_theme}")
                    
                    if st.form_submit_button("✨ Generate Super-Production Manus Prompt", type="primary"):
                        
                        # Build image instructions
                        image_instructions = ""
                        if company_logo_url:
                            image_instructions += f"\n**Company Logo:** Available at URL: {company_logo_url} — use this as the sponsor logo throughout the deck."
                        if uploaded_logo:
                            image_instructions += f"\n**Company Logo:** Uploaded file '{uploaded_logo.name}' — use this as the sponsor logo throughout."
                        if uploaded_headshot:
                            image_instructions += f"\n**Athlete Headshot:** Uploaded file '{uploaded_headshot.name}' — use on Slide 2 (Athlete Profile)."
                        if uploaded_action:
                            image_instructions += f"\n**Action Photo:** Uploaded file '{uploaded_action.name}' — use as hero image on Slide 1 and Slide 3."
                        if uploaded_mockup:
                            image_instructions += f"\n**Livery Mockup:** Uploaded file '{uploaded_mockup.name}' — use on Slide 11 (Visual Proof) and optionally Slide 1."
                        if not image_instructions:
                            image_instructions = "\n**No images provided.** Create professional placeholder areas where images should be inserted. Use motorsport stock imagery to set the visual tone."
                        
                        # Social media reach summary
                        social_reach = []
                        if s5_insta: social_reach.append(f"Instagram: {s5_insta}")
                        if s5_fb: social_reach.append(f"Facebook: {s5_fb}")
                        if s5_yt: social_reach.append(f"YouTube: {s5_yt}")
                        if s5_tiktok: social_reach.append(f"TikTok: {s5_tiktok}")
                        social_str = " | ".join(social_reach) if social_reach else "Growing digital presence"
                        
                        # ============================================
                        # SUPER-PRODUCTION MANUS PROMPT
                        # ============================================
                        manus_prompt = f"""You are a world-class presentation designer and motorsport sponsorship strategist. Create an absolutely stunning, investor-grade sponsorship proposal deck.

**PROJECT:** {s1_title}
**ATHLETE:** {s2_name}
**SPONSOR TARGET:** {l_name} ({l_sector})
**CONTACT:** {l_contact}

---

## DESIGN DIRECTION

**Theme:** {deck_theme}
**Tone:** Premium, commercial, data-driven. This is a BUSINESS PROPOSAL, not a fan page.
**Style:** Think McKinsey meets Red Bull Racing. Clean typography (use Inter or Montserrat), bold hero images, subtle data visualizations, generous white space. Every slide should feel like it cost £10,000 to design.

**Color Palette:**
- If "Dark & Premium": Primary #0D0D0D, Accent #C8102E (racing red), Secondary #FAFAFA, Gold accents for premium tier
- If "Clean White": Primary #FFFFFF, Accent #1A1A2E, Secondary #E8E8E8
- If "Racing Red": Primary #C8102E, Secondary #1A1A1A, Accent #FFFFFF
- If "Corporate Blue": Primary #0A2463, Secondary #F5F5F5, Accent #3E92CC
- If "Custom": Use {l_name}'s brand colors as primary, {s2_name}'s racing colors as accent

**Typography:** Headlines: Bold condensed (Impact/Montserrat Black). Body: Clean sans-serif (Inter/Roboto). Numbers/Stats: Extra-bold for impact.

---

## IMAGES & ASSETS
{image_instructions}

---

## DISCOVERY CALL INTELLIGENCE (Use this to personalise EVERY slide)
{disc_context if disc_context else "No discovery data available — create a compelling generic proposal."}

---

## SLIDE-BY-SLIDE STRUCTURE (12 SLIDES)

### SLIDE 1: TITLE / EXECUTIVE SUMMARY
**Visual:** Full-bleed hero image of the {r_vehicle} in action. Sponsor logo + Athlete name overlaid.
**Headline:** {s1_title}
**Body:** {s1_summary}
**Design Note:** This slide must create an emotional reaction within 3 seconds. Use cinematic composition.

### SLIDE 2: ATHLETE PROFILE
**Visual:** Professional headshot or portrait. Clean layout.
**Content:**
- Name: {s2_name} (Racing as: {s2_racing_num})
- Age: {s2_age} | Home: {s2_home} | Series: {s2_cat}
- Story: {s2_story}
- Mission: {s2_mission}
- Vision: {s2_vision}
- Team: {s2_team}
**Design Note:** Split layout — photo left, bio right. Keep it personal but professional. Include a quote pull-out.

### SLIDE 3: PERFORMANCE & VALUE
**Visual:** Data visualization / stats dashboard design.
**Content:**
- Season Stats: {s3_metrics}
- Front Row Starts: {p_frontrow}
- Championship Points: {p_points}
- Career Highlights: {s3_highlights}
- 2026 Goals: {s3_goals}
**Design Note:** Use infographic-style stat cards. Large bold numbers with progress indicators. Show trajectory with an upward trend arrow.

### SLIDE 4: THE PLATFORM (CHAMPIONSHIP)
**Visual:** Circuit map or championship banner.
**Content:**
- Series: {s4_series}
- Rounds: {s4_rounds}
- Key Circuits: {s4_circuits}
- Media Coverage: {s4_media}
**Design Note:** Include a map showing circuit locations. Show reach visually with concentric circles or heat map overlay.

### SLIDE 5: AUDIENCE & REACH
**Visual:** Demographics infographic.
**Content:**
- Demographics: {s5_data}
- Digital Reach: {social_str}
- Engagement Rate: {s5_engagement}
**Design Note:** Use pie charts for age/gender split. Bar charts for platform reach. Include verified badges next to real numbers. Make this feel data-rich and trustworthy.

### SLIDE 6: BRAND VALUE PROPOSITION ⚡ KEY SLIDE
**Visual:** Clean layout with bold icons for each benefit.
**Content:**
{s6_value}
**Design Note:** This is the COMMERCIAL HEART. Use a 3-column icon layout. Each benefit gets a bold icon, headline, and 2-line description. Make it feel like a premium menu of options.

### SLIDE 7: ACTIVATION & DELIVERABLES ⚡ KEY SLIDE
**Visual:** Timeline or calendar-style activation plan.
**Content:**
{s7_act}
**Design Note:** Use a visual timeline showing activation moments across the season. Include mini-icons for each deliverable type. This should feel like a campaign plan, not a wish list.

### SLIDE 8: SUSTAINABILITY & ESG
**Visual:** Clean, minimal design with leaf/globe icons.
**Content:**
{s8_esg}
**Design Note:** Keep this understated and authentic. One slide, no greenwashing. Simple icons with brief descriptions.

### SLIDE 9: INVESTMENT PACKAGES ⚡ KEY SLIDE
**Visual:** Tiered pricing table design.
**Content:**
{s9_tiers}

Custom packages available — let's build something that fits your exact objectives.
**Design Note:** Use a pricing table design like a premium SaaS product. Highlight the recommended tier (Gold) with a "MOST POPULAR" or "RECOMMENDED" badge. Include checkmark lists for each tier.

### SLIDE 10: ROI & MEDIA VALUE
**Visual:** ROI calculator / projection chart.
**Content:**
{s10_roi}
**Design Note:** Use a horizontal bar chart showing: Investment vs Returns. Make the returns bar significantly larger. Include a bold "X:1 ROI" number as the hero stat.

### SLIDE 11: VISUAL PROOF (MOCKUPS)
**Visual:** Render gallery showing the partnership in action.
**Content:**
{s11_visuals}
**Design Note:** Create a gallery-style layout with 2-4 mockup images. If a livery mockup was provided, make it the hero. Include captions describing each visual.

### SLIDE 12: NEXT STEPS / CTA
**Visual:** Clean, confident closing design.
**Closing Statement:** {s12_close}
**Call to Action:** {s12_cta}
**Design Note:** Simple, powerful. The closing should feel warm and professional — not desperate. Include contact details prominently with a calendar booking suggestion.

---

## FINAL PRODUCTION NOTES
1. Export as 16:9 widescreen PDF or PowerPoint
2. Ensure all text is legible (minimum 14pt body, 24pt headlines)
3. Include slide numbers subtly in the bottom corner
4. Add a consistent footer with {s2_name}'s name and {l_name}'s logo
5. Every slide should work as a standalone image if screenshotted
6. The deck should take exactly 5-7 minutes to present
7. Use smooth transitions between slides
8. Include a subtle watermark or branding element that ties all slides together
"""
                        
                        st.success("✨ Super-Production Prompt Generated!")
                        
                        # Display in a copyable box
                        st.markdown("### 📋 Your Manus Prompt")
                        st.caption("Copy the entire prompt below and paste it into Manus to generate your professional slide deck.")
                        st.code(manus_prompt, language=None)
                        
                        # Character count
                        st.caption(f"📊 Prompt Length: {len(manus_prompt):,} characters | ~{len(manus_prompt.split()):,} words")
                        
                        st.divider()
                        
                        # ACTION BUTTONS
                        st.markdown("### 📤 Send to Manus")
                        
                        act_c1, act_c2, act_c3 = st.columns(3)
                        with act_c1:
                            st.link_button("🚀 Open Manus", "https://manus.im/app", type="primary")
                            st.caption("Paste the prompt above into Manus")
                        with act_c2:
                            subject = urllib.parse.quote(f"Proposal Prompt: {s2_name} x {l_name}")
                            body = urllib.parse.quote("Please paste the prompt from the Sponsor Finder app into Manus to generate the deck.")
                            mailto = f"mailto:team@caminocoaching.co.uk?subject={subject}&body={body}"
                            st.link_button("📧 Email Prompt", mailto)
                            st.caption("Email to your team")
                        with act_c3:
                            st.link_button("💬 Open ChatGPT", "https://chat.openai.com")
                            st.caption("Alternative: use ChatGPT + Canvas")
                        
                        # Save prompt to notes
                        save_notes = lead.get('Notes', {})
                        if isinstance(save_notes, str):
                            try: save_notes = json.loads(save_notes)
                            except: save_notes = {}
                        if not isinstance(save_notes, dict): save_notes = {}
                        save_notes['proposal_prompt_generated'] = True
                        save_notes['proposal_generated_date'] = datetime.now().strftime("%Y-%m-%d %H:%M")
                        db.update_lead_notes(lead['id'], save_notes)

# =============================================================================
# TAB 4: BULK MAILER
# =============================================================================
if current_tab == "📰 Bulk Mailer":
    st.subheader("📰 Bulk Mailer")
    st.caption("Send newsletters and follow-up emails in batches through your email app.")
    
    # Load all leads
    all_leads_mail = db.get_leads(st.session_state.user_id)
    
    if not all_leads_mail:
        st.info("No leads found. Go to 'Search & Add' to build your list first.")
    else:
        # --- EXTRACT EMAILS FROM LEADS ---
        def _extract_lead_emails(leads_list):
            """Extract leads that have email addresses from notes."""
            leads_with_email = []
            for lead in leads_list:
                notes = lead.get('Notes', {})
                if isinstance(notes, str):
                    try: notes = json.loads(notes)
                    except: notes = {}
                if not isinstance(notes, dict): notes = {}
                
                email = notes.get('email', '')
                emails_list = notes.get('emails', [])
                
                # Collect all valid emails
                all_emails = []
                if email and '@' in str(email):
                    all_emails.append(str(email).strip())
                if isinstance(emails_list, list):
                    for e in emails_list:
                        if e and '@' in str(e) and str(e).strip() not in all_emails:
                            all_emails.append(str(e).strip())
                
                if all_emails:
                    leads_with_email.append({
                        'id': lead['id'],
                        'name': lead['Business Name'],
                        'contact': lead.get('Contact Name', ''),
                        'sector': lead.get('Sector', ''),
                        'email': all_emails[0],  # Primary email
                        'all_emails': all_emails,
                        'status': lead.get('Status', 'Pipeline'),
                        'next_action': lead.get('Next Action', ''),
                        'notes': notes
                    })
            return leads_with_email
        
        leads_with_email = _extract_lead_emails(all_leads_mail)
        
        # Stats bar
        stat_c1, stat_c2, stat_c3, stat_c4 = st.columns(4)
        stat_c1.metric("Total Leads", len(all_leads_mail))
        stat_c2.metric("With Email", len(leads_with_email))
        stat_c3.metric("Without Email", len(all_leads_mail) - len(leads_with_email))
        
        # Count follow-ups due today
        today_str = datetime.now().strftime("%Y-%m-%d")
        due_today = [l for l in leads_with_email if l['next_action'] and l['next_action'] <= today_str]
        stat_c4.metric("Follow-ups Due", len(due_today))
        
        st.divider()
        
        # --- SUB-MODES ---
        mail_mode = st.radio("Mode", ["📰 Newsletter Blast", "📬 Follow-Up Emails"], horizontal=True, key="mail_mode")
        
        # =================================================================
        # MODE 1: NEWSLETTER BLAST
        # =================================================================
        if mail_mode == "📰 Newsletter Blast":
            st.markdown("### 📰 AI Newsletter Generator")
            st.caption("Generate a newsletter update, then send it in batches of 10 via BCC through your email app.")
            
            if not leads_with_email:
                st.warning("⚠️ None of your leads have email addresses. Enrich your leads first (Search & Add → auto-enrich captures emails).")
            else:
                # --- FILTER CONTACTS ---
                with st.expander("🎯 Select Recipients", expanded=True):
                    filter_col1, filter_col2 = st.columns(2)
                    with filter_col1:
                        status_filter = st.multiselect(
                            "Filter by Status",
                            options=list(set(l['status'] for l in leads_with_email)),
                            default=list(set(l['status'] for l in leads_with_email)),
                            key="nl_status_filter"
                        )
                    with filter_col2:
                        sector_filter = st.multiselect(
                            "Filter by Sector",
                            options=list(set(l['sector'] for l in leads_with_email if l['sector'])),
                            default=list(set(l['sector'] for l in leads_with_email if l['sector'])),
                            key="nl_sector_filter"
                        )
                    
                    filtered = [l for l in leads_with_email 
                               if l['status'] in status_filter 
                               and (l['sector'] in sector_filter or not l['sector'])]
                    
                    st.info(f"**{len(filtered)} contacts** selected → **{(len(filtered) + 9) // 10} batches** of up to 10")
                    
                    # Show recipient list
                    if filtered:
                        with st.expander(f"👀 Preview Recipients ({len(filtered)})"):
                            for i, lead in enumerate(filtered):
                                st.caption(f"{i+1}. {lead['name']} — {lead['email']} ({lead['status']})")
                
                st.divider()
                
                # --- NEWSLETTER CONTENT ---
                st.markdown("### ✍️ Newsletter Content")
                
                # AI generation context
                nl_type = st.selectbox("Newsletter Type", [
                    "🏁 Season Update — Results & upcoming events",
                    "🤝 Partnership Spotlight — What sponsors are getting",
                    "📊 Value Report — Audience reach & brand exposure stats",
                    "🎉 Milestone Announcement — Achievement or news",
                    "✏️ Custom — Write your own"
                ], key="nl_type")
                
                # Subject line
                default_subjects = {
                    "🏁 Season Update": f"🏁 {rider_name} — Season Update | {championship}",
                    "🤝 Partnership Spotlight": f"🤝 What Our Partners Are Getting This Season | {rider_name}",
                    "📊 Value Report": f"📊 Your Brand in Front of {audience_size}+ Fans | {rider_name}",
                    "🎉 Milestone Announcement": f"🎉 Big News from {rider_name} | {championship}",
                    "✏️ Custom": f"{rider_name} — Update"
                }
                
                # Match subject to type
                subject_default = ""
                for key_prefix, subj in default_subjects.items():
                    if nl_type.startswith(key_prefix):
                        subject_default = subj
                        break
                
                nl_subject = st.text_input("Subject Line", value=subject_default, key="nl_subject")
                
                # Generate AI body
                nl_templates = {
                    "🏁 Season Update — Results & upcoming events": f"""Hi there,

I wanted to share a quick update on my {championship} season.

{f"Last season in {prev_champ}, I achieved: {achievements}." if achievements else ""}
{f"This year, my goal is: {season_goal}." if season_goal else ""}

The next race is coming up soon and the momentum is building. {f"With {audience_size}+ fans per event" if audience_size else "With a growing fanbase"}, there's a real opportunity for businesses to get their brand in front of an engaged, passionate audience.

{f"As part of {team_name}, we're" if team_name else "We're"} always looking for forward-thinking businesses to join our journey — not just as sponsors, but as genuine partners.

If that sounds interesting, I'd love a quick 10-minute call to see if there's a fit. No pressure, no pitch — just a conversation.

Best regards,
{rider_name}
{championship}""",

                    "🤝 Partnership Spotlight — What sponsors are getting": f"""Hi there,

I often get asked: "What do your partners actually get?"

Here's the honest answer — it's not just a logo on a {user_profile.get('vehicle', 'vehicle')}. Our partners get:

✅ Brand visibility in front of {audience_size}+ fans per event
✅ VIP hospitality they use for client entertainment and team rewards
✅ Exclusive content for their own marketing campaigns
✅ A genuine story to tell — partnering with a competitive athlete in {championship}
{f"✅ Television exposure to {tv_viewers} viewers" if tv_viewers and tv_viewers != "N/A" else ""}

The businesses that get the most out of this are the ones that treat it as a marketing channel, not a charity donation. And that's exactly how I approach every partnership.

If you've been sitting on the fence, I'd love a quick chat to explore whether your business could benefit.

Best regards,
{rider_name}""",

                    "📊 Value Report — Audience reach & brand exposure stats": f"""Hi there,

Quick numbers update from the {championship} season so far:

📊 {audience_size}+ live fans per event
{f"📺 {tv_viewers} TV viewers per round" if tv_viewers and tv_viewers != "N/A" else ""}
🏆 {f"Achievements: {achievements}" if achievements else "Competitive results throughout the season"}
📱 Growing social media reach across all platforms

What does this mean for a partner business? It means your brand gets seen by thousands of engaged, passionate motorsport fans — the kind of audience that's hard to reach through traditional advertising.

I still have limited partnership spots available for this season. If you'd like to know more about what that could look like for your business, I'm happy to have a quick 10-minute chat.

Best regards,
{rider_name}
{championship}""",

                    "🎉 Milestone Announcement — Achievement or news": f"""Hi there,

I'm excited to share some big news!

[— Enter your milestone here —]

This is a testament to the hard work and dedication of {f"the whole {team_name} team" if team_name else "everyone involved"}, and it wouldn't be possible without the support of our partners.

As we build on this momentum heading into the next round of {championship}, I'm looking for one or two more businesses to join us for the ride.

If your business could benefit from associating with a winning motorsport story, I'd love to chat.

Best regards,
{rider_name}""",

                    "✏️ Custom — Write your own": f"""Hi there,

[Write your newsletter content here]

Best regards,
{rider_name}
{championship}"""
                }
                
                nl_body_default = nl_templates.get(nl_type, nl_templates["✏️ Custom — Write your own"])
                nl_body = st.text_area("Newsletter Body", value=nl_body_default, height=350, key="nl_body")
                
                st.divider()
                
                # --- BATCH SENDER ---
                if filtered and nl_subject and nl_body:
                    st.markdown("### 📤 Send in Batches")
                    st.caption("Each batch opens your email app with up to 10 contacts in BCC. Click 'Send' in your email app, then come back and click the next batch.")
                    
                    # Settings
                    set_c1, set_c2 = st.columns(2)
                    with set_c1:
                        batch_size = st.number_input("Contacts per batch", min_value=1, max_value=20, value=10, key="batch_size")
                    with set_c2:
                        sender_email = st.text_input("Your 'From' email (for mailto):", value=st.session_state.user_email, key="sender_email")
                    
                    # Create batches
                    batches = []
                    for i in range(0, len(filtered), batch_size):
                        batches.append(filtered[i:i+batch_size])
                    
                    # Track sent batches
                    if "sent_batches" not in st.session_state:
                        st.session_state.sent_batches = set()
                    
                    # Progress
                    sent_count = len(st.session_state.sent_batches)
                    total_batches = len(batches)
                    
                    if sent_count == total_batches and total_batches > 0:
                        st.success(f"🎉 All {total_batches} batches sent! {len(filtered)} contacts reached.")
                        if st.button("🔄 Reset Batch Tracker"):
                            st.session_state.sent_batches = set()
                            st.rerun()
                    else:
                        st.progress(sent_count / max(total_batches, 1), text=f"Sent {sent_count}/{total_batches} batches")
                    
                    st.markdown("---")
                    
                    # Important note about mailto length limits
                    st.info("💡 **How it works:** The BCC addresses are set automatically. The email body is copied to your clipboard — just paste it into the email body after your email app opens.")
                    
                    # Display batches
                    for batch_idx, batch in enumerate(batches):
                        batch_num = batch_idx + 1
                        is_sent = batch_idx in st.session_state.sent_batches
                        
                        bcc_emails = [l['email'] for l in batch]
                        bcc_str = ",".join(bcc_emails)
                        
                        # Build mailto link (subject + BCC only, body via clipboard)
                        encoded_subject = urllib.parse.quote(nl_subject)
                        mailto_link = f"mailto:?bcc={urllib.parse.quote(bcc_str)}&subject={encoded_subject}"
                        
                        # Batch card
                        with st.expander(
                            f"{'✅' if is_sent else '📧'} Batch {batch_num} — {len(batch)} contacts" + 
                            (" ✓ SENT" if is_sent else ""),
                            expanded=not is_sent
                        ):
                            # Show contacts in this batch
                            for l in batch:
                                st.caption(f"  • {l['name']} — {l['email']}")
                            
                            st.markdown("---")
                            
                            bc1, bc2, bc3 = st.columns([1.5, 1, 1])
                            
                            with bc1:
                                # Copy body button (using st.code for copy icon)
                                st.markdown("**Step 1:** Copy the newsletter body")
                                st.code(nl_body, language=None)
                            
                            with bc2:
                                st.markdown("**Step 2:** Open email")
                                st.link_button(
                                    f"📧 Open Batch {batch_num}",
                                    mailto_link,
                                    type="primary" if not is_sent else "secondary"
                                )
                                st.caption("Opens your email app with BCC pre-filled")
                            
                            with bc3:
                                st.markdown("**Step 3:** Mark as sent")
                                if not is_sent:
                                    if st.button(f"✅ Mark Batch {batch_num} Sent", key=f"mark_batch_{batch_idx}"):
                                        st.session_state.sent_batches.add(batch_idx)
                                        st.balloons()
                                        st.rerun()
                                else:
                                    st.success("Sent ✓")
                
                else:
                    if not filtered:
                        st.warning("No contacts selected. Adjust your filters above.")
                    elif not nl_subject:
                        st.warning("Please enter a subject line.")
        
        # =================================================================
        # MODE 2: FOLLOW-UP EMAILS
        # =================================================================
        elif mail_mode == "📬 Follow-Up Emails":
            st.markdown("### 📬 Follow-Up Emails Due")
            st.caption("Personalised follow-up emails for leads with a scheduled follow-up date of today or earlier.")
            
            if not leads_with_email:
                st.warning("⚠️ None of your leads have email addresses yet.")
            else:
                # Filter leads due for follow-up
                today_str = datetime.now().strftime("%Y-%m-%d")
                
                fu_filter = st.radio("Show", ["📅 Due Today & Overdue", "📋 All Leads with Email", "🔴 Overdue Only"], horizontal=True, key="fu_filter")
                
                if fu_filter == "📅 Due Today & Overdue":
                    followup_leads = [l for l in leads_with_email if l['next_action'] and l['next_action'] <= today_str]
                elif fu_filter == "🔴 Overdue Only":
                    followup_leads = [l for l in leads_with_email if l['next_action'] and l['next_action'] < today_str]
                else:
                    followup_leads = leads_with_email
                
                if not followup_leads:
                    st.success("🎉 No follow-ups due! You're all caught up.")
                else:
                    st.info(f"**{len(followup_leads)} leads** ready for follow-up")
                    
                    # --- BATCH FOLLOW-UP (same message to all) ---
                    st.markdown("---")
                    fu_approach = st.radio("Approach", ["📝 Individual (personalised per lead)", "📦 Batch (same message, BCC groups of 10)"], horizontal=True, key="fu_approach")
                    
                    if fu_approach == "📦 Batch (same message, BCC groups of 10)":
                        st.markdown("#### 📦 Batch Follow-Up")
                        st.caption("Send the same follow-up message to all due leads in BCC batches.")
                        
                        fu_subject = st.text_input("Subject Line", value=f"Quick follow-up — {rider_name} | {championship}", key="fu_batch_subject")
                        
                        fu_body_default = f"""Hi there,

I reached out recently about a potential partnership opportunity with {rider_name} in {championship}.

I know things get busy, so I just wanted to check in. If the timing isn't right, no problem at all — just let me know.

If you're still open to a quick 10-minute conversation about how motorsport could work as a marketing channel for your business, I'd love to find a time that works.

Best regards,
{rider_name}"""
                        
                        fu_body = st.text_area("Follow-up Body", value=fu_body_default, height=250, key="fu_batch_body")
                        
                        if fu_subject and fu_body:
                            # Create batches
                            fu_batch_size = st.number_input("Contacts per batch", min_value=1, max_value=20, value=10, key="fu_batch_size")
                            fu_batches = []
                            for i in range(0, len(followup_leads), fu_batch_size):
                                fu_batches.append(followup_leads[i:i+fu_batch_size])
                            
                            if "fu_sent_batches" not in st.session_state:
                                st.session_state.fu_sent_batches = set()
                            
                            st.progress(
                                len(st.session_state.fu_sent_batches) / max(len(fu_batches), 1),
                                text=f"Sent {len(st.session_state.fu_sent_batches)}/{len(fu_batches)} batches"
                            )
                            
                            st.info("💡 Copy the message body first, then click each batch button to open your email app.")
                            
                            # Copyable body
                            st.markdown("**📋 Copy this message body:**")
                            st.code(fu_body, language=None)
                            
                            st.markdown("---")
                            
                            for b_idx, batch in enumerate(fu_batches):
                                b_sent = b_idx in st.session_state.fu_sent_batches
                                bcc_str = ",".join([l['email'] for l in batch])
                                mailto_link = f"mailto:?bcc={urllib.parse.quote(bcc_str)}&subject={urllib.parse.quote(fu_subject)}"
                                
                                fbc1, fbc2, fbc3 = st.columns([2, 1, 1])
                                with fbc1:
                                    names = ", ".join([l['name'][:20] for l in batch[:3]])
                                    if len(batch) > 3:
                                        names += f" +{len(batch)-3} more"
                                    st.markdown(f"{'✅' if b_sent else '📧'} **Batch {b_idx+1}** ({len(batch)} contacts) — {names}")
                                with fbc2:
                                    st.link_button(
                                        f"📧 Open Batch {b_idx+1}",
                                        mailto_link,
                                        type="primary" if not b_sent else "secondary"
                                    )
                                with fbc3:
                                    if not b_sent:
                                        if st.button(f"✅ Sent", key=f"fu_mark_{b_idx}"):
                                            st.session_state.fu_sent_batches.add(b_idx)
                                            st.rerun()
                                    else:
                                        st.success("Done ✓")
                                
                                st.markdown("---")
                            
                            if len(st.session_state.fu_sent_batches) == len(fu_batches) and fu_batches:
                                st.success(f"🎉 All follow-up batches sent! {len(followup_leads)} contacts reached.")
                                if st.button("🔄 Reset Follow-Up Tracker", key="reset_fu"):
                                    st.session_state.fu_sent_batches = set()
                                    st.rerun()
                    
                    else:
                        # --- INDIVIDUAL FOLLOW-UPS ---
                        st.markdown("#### 📝 Individual Follow-Ups")
                        st.caption("Each lead gets a personalised message based on their current outreach step.")
                        
                        for idx, lead_fu in enumerate(followup_leads):
                            notes = lead_fu['notes']
                            contact_name_fu = lead_fu['contact'] or lead_fu['name']
                            first_name_fu = contact_name_fu.split()[0] if contact_name_fu else "there"
                            
                            # Determine which template step they're on
                            seq_options_fu = [
                                "LI Connect: Request",
                                "Email: Cold Opener",
                                "LI Msg 1: Intro (Day 2)",
                                "LI Msg 2: Homework (Day 7)",
                                "LI Msg 3: Momentum (Day 14)",
                                "LI Msg 4: Scarcity (Day 21)",
                                "LI Msg 5: Final (Day 28)"
                            ]
                            
                            last_step = notes.get('outreach_step', -1)
                            try: last_step = int(last_step)
                            except: last_step = -1
                            
                            next_step_idx = min(last_step + 1, len(seq_options_fu) - 1)
                            if next_step_idx < 0: next_step_idx = 0
                            next_template = seq_options_fu[next_step_idx]
                            
                            salutation_fu = notes.get('salutation', 'Mr')
                            
                            # Card styling
                            overdue = lead_fu['next_action'] and lead_fu['next_action'] < today_str
                            status_icon = "🔴" if overdue else "📅"
                            
                            with st.expander(f"{status_icon} {lead_fu['name']} — {contact_name_fu} ({next_template})", expanded=False):
                                ic1, ic2 = st.columns([2, 1])
                                with ic1:
                                    st.caption(f"📧 Email: {lead_fu['email']}")
                                    st.caption(f"📅 Due: {lead_fu['next_action'] or 'ASAP'}")
                                    st.caption(f"⏭️ Next step: {next_template}")
                                
                                with ic2:
                                    st.caption(f"Status: {lead_fu['status']}")
                                    st.caption(f"Sector: {lead_fu['sector']}")
                                
                                # Generate personalised message
                                ctx_fu = {
                                    "goal": season_goal,
                                    "prev_champ": prev_champ,
                                    "achievements": achievements,
                                    "audience": audience_size,
                                    "tv": tv_viewers,
                                    "team": team_name,
                                    "rep_mode": user_profile.get("rep_mode", False),
                                    "rep_name": user_profile.get("rep_name", ""),
                                    "rep_role": user_profile.get("rep_role", "")
                                }
                                
                                # Generate the personalised email using existing template system
                                personalised_msg = generate_message(
                                    next_template, lead_fu['name'], rider_name, lead_fu['sector'],
                                    town=saved_town, championship=championship, extra_context=ctx_fu,
                                    contact_name=contact_name_fu, salutation=salutation_fu
                                )
                                
                                # Subject line for individual
                                individual_subject = f"Re: {rider_name} — Partnership Opportunity | {lead_fu['name']}"
                                if "Cold Opener" in next_template:
                                    individual_subject = f"{rider_name} — A local partnership opportunity for {lead_fu['name']}"
                                
                                i_subject = st.text_input("Subject", value=individual_subject, key=f"fu_subj_{idx}")
                                final_fu_msg = st.text_area("Message", value=personalised_msg, height=200, key=f"fu_msg_{idx}")
                                
                                st.caption("👇 Copy the message, then click to open email:")
                                st.code(final_fu_msg, language=None)
                                
                                # mailto with single recipient (not BCC)
                                encoded_fu_body = urllib.parse.quote(final_fu_msg[:1500])  # Truncate for URL safety
                                mailto_fu = f"mailto:{lead_fu['email']}?subject={urllib.parse.quote(i_subject)}&body={encoded_fu_body}"
                                
                                ibc1, ibc2 = st.columns(2)
                                with ibc1:
                                    st.link_button(f"📧 Email {first_name_fu}", mailto_fu, type="primary")
                                with ibc2:
                                    if st.button(f"✅ Mark Sent & Schedule Next", key=f"fu_sent_{idx}"):
                                        # Calculate next follow-up
                                        fu_days = 7
                                        if "Msg 2" in next_template: fu_days = 5
                                        elif "Msg 6" in next_template: fu_days = 30
                                        
                                        next_date = (datetime.now() + timedelta(days=fu_days)).strftime("%Y-%m-%d")
                                        
                                        # Update DB
                                        db.update_lead_status(lead_fu['id'], "Active", next_date)
                                        
                                        # Update notes with step
                                        update_notes = notes.copy()
                                        update_notes['outreach_step'] = next_step_idx
                                        update_notes['last_template'] = next_template
                                        db.update_lead_notes(lead_fu['id'], update_notes)
                                        
                                        st.balloons()
                                        st.success(f"🎉 Sent! Next follow-up: {next_date}")
                                        time.sleep(1.5)
                                        st.rerun()
        
        st.divider()
        
        # --- TIPS ---
        with st.expander("💡 Bulk Email Tips", expanded=False):
            st.markdown("""
### How It Works
1. **Newsletter Blast** → Your email app opens with BCC addresses pre-filled. Paste the message body and hit Send.
2. **Follow-Up Emails** → Individual personalised emails based on each lead's outreach stage.

### Why BCC?
- Recipients **can't see** each other's email addresses
- Looks like a personal email, not a mass blast
- Keeps your outreach professional and GDPR-friendly

### Best Practices
- 🕐 **Send between 8-10am** Tuesday-Thursday for best open rates
- 📧 **Max 10 per batch** to avoid spam filters
- ✍️ **Personalise the subject line** — it's the #1 factor in open rates
- 🔄 **Follow up at least 3 times** — most deals close after the 4th-7th touch
- 📱 **Keep it short** — under 150 words gets 2x more replies

### Email App Compatibility
- ✅ Apple Mail — works great
- ✅ Outlook Desktop — works great
- ✅ Thunderbird — works great
- ⚠️ Gmail Web — may truncate long URLs. Use the copy method instead.
""")

