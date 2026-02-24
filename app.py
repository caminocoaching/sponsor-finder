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
        "Email: Cold Opener",
        "LI Msg 1: Connect",
        "LI Msg 2: Thanks for connecting (Day 2)",
        "LI Msg 3: Homework (Day 7)",
        "LI Msg 4: Momentum (Day 14)",
        "LI Msg 5: Scarcity (Day 21)",
        "LI Msg 6: Final (Day 28)"
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
        if "Msg 2" in current_template: def_days = 5
        elif "Msg 3" in current_template: def_days = 7
        elif "Msg 4" in current_template: def_days = 7
        elif "Msg 5" in current_template: def_days = 7
        elif "Msg 6" in current_template: def_days = 7
        
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
        
        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            if st.button("📞 Move to Discovery", key=f"card_disc_{lead_id}"):
                db.update_lead_status(lead_id, "Discovery Call")
                st.rerun()
        with fc2:
            if st.button("📋 Move to Proposal", key=f"card_prop_{lead_id}"):
                db.update_lead_status(lead_id, "Proposal")
                st.rerun()
        with fc3:
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

My name is [Rider Name] and I'm based in [Town], close to your area.

I'm racing this season in the [Championship Name] and I'm reaching out to a small number of local businesses in [Sector Hook] who could benefit from what we're building.

The reason I chose [Business Name] specifically: companies in your space are starting to use motorsport as a platform to stand out, build loyalty, and get in front of [Audience Size]+ engaged fans per event. And most of them started with a single conversation.

I'm not sending a pitch. I'd love to have a quick 10-minute discovery call to understand what [Business Name] is working toward this year — and whether there's even a fit worth exploring.

No commitment. No pressure. Just a conversation between two local businesses.

Best regards,
[Rider Name]""",

    "LI Msg 1: Connect": """Hi [Contact Name], I'm a local [Championship Name] competitor based in [Town]. I'm connecting with a few forward-thinking [Sector] businesses in the area to explore mutual benefits. Would be great to connect.""",

    "LI Msg 2: Thanks for connecting (Day 2)": """[Contact Name] — Appreciate the connection.

Quick intro: I compete in the [Championship Name] this season. [Audience Size]+ fans per event, live coverage, and strong local following.

I've been connecting with businesses in [Sector Hook] because there's a real opportunity for the right partner to own that space in the motorsport world — before your competitors do.

Not pitching anything. Genuinely curious — has [Business Name] ever explored using sport as a marketing channel?

[Rider Name]""",

    "LI Msg 3: Homework (Day 7)": """Hi [Contact Name],

I've been doing some homework on [Business Name] and I can see you're doing impressive things in [Sector Hook].

The reason I'm reaching out: I'm racing in [Championship Name] this season, and our partners don't just get a logo on a bike. They get:

• Their brand in front of [Audience Size]+ engaged fans per event
• VIP hospitality they can use as a client incentive or team reward
• Content and stories they can use across their own marketing

I noticed your competitors aren't doing this yet. That's exactly why the timing is right.

Would 10 minutes be worth exploring whether there's a fit?

[Rider Name]""",

    "LI Msg 4: Momentum (Day 14)": """[Contact Name],

Quick update — I'm deep into pre-season preparation for [Championship Name] and we're locking in the final partnership spots.

Last season in [Previous Champ]: [Achievements]. This year the goal is [Season Goal].

I keep coming back to [Business Name] because I genuinely think there's a strong alignment. Here's what forward-thinking [Sector] businesses are doing with motorsport:

1. Using race days as client hospitality — beats a round of golf every time
2. Getting exclusive content for their marketing — behind-the-scenes, race day stories
3. Building staff engagement — race bike visits to the office, team experiences

I'd rather have one great partner than ten average ones. Is that conversation still worth having?

[Rider Name]""",

    "LI Msg 5: Scarcity (Day 21)": """Hi [Contact Name],

Honest update: I have 2 partnership spots remaining for the [Championship Name] season.

Once they're filled, the opportunity is gone until next year.

I've launched [Team Name] with options from supporter-level all the way to title partnership. But the real value is in building something tailored around what [Business Name] actually needs — whether that's new customer acquisition, team engagement, or competitive differentiation.

Here's my question: if I could show you exactly how this works in 10 minutes, would that be worth your time?

No pressure either way.

[Rider Name]""",

    "LI Msg 6: Final (Day 28)": """[Contact Name],

This is my last follow-up.

I've reached out because I believe [Business Name] would be a strong fit. But I respect your time.

If the answer is "not right now" — no problem at all. Just let me know and I'll stop.

If it's "interested but haven't had time" — reply with "interested" and I'll send a one-page overview. No call needed.

Either way, I'd rather know than guess.

[Rider Name]""",

    "Initial Contact": """(See Email: Cold Opener above)""",
    "Follow Up": """(See LI Msg 2 or others)""",
    "Proposal": """[Contact Name],

No fluff — here’s exactly what I’m proposing based on our conversation.

**The Goal for [Business Name]:**
You told me you’re focused on [Goal Answer]. Everything below is built around that.

**The Plan:**
• Audience: [Audience Answer] — this is who sees your brand every race weekend
• Activation: Logo placement + social media campaign + hospitality access

**Why This Works:**
This directly solves your need for [Success Answer] — and it does it in a way your competitors aren’t.

The proposal deck is attached. I’ve kept it simple on purpose.

Next step: You tell me what you’d change. I’ll adjust and we lock it in.

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
    - Initial messages (Email opener, LI Msg 1): formal 'Mr/Mrs/Miss LastName'
    - Follow-up messages (LI Msg 2+): first name only
    - salutation: 'Mr', 'Mrs', 'Miss', 'Ms', 'Dr' (selected per contact)
    """
    if not full_name or full_name.strip() == "":
        return f"{salutation} [Name]"  # Placeholder if no name set
    
    name_parts = full_name.strip().split()
    first_name = name_parts[0] if name_parts else full_name
    last_name = name_parts[-1] if len(name_parts) > 1 else ""
    
    # Initial contact messages: formal addressing
    is_initial = template_type in ("Email: Cold Opener", "LI Msg 1: Connect")
    
    if is_initial:
        if last_name:
            return f"{salutation} {last_name}"
        else:
            return f"{salutation} {first_name}"
    else:
        # Follow-up messages: use first name (they know you now)
        return first_name

def generate_message(template_type, business_name, rider_name, sector, context_answers=None, town="MyTown", championship="Championship", extra_context={}, contact_name="", salutation="Mr"):
    template = TEMPLATES.get(template_type, "")
    hook = get_sector_hook(sector)
    
    # Format contact name based on message type (formal vs first-name)
    formatted_name = _format_contact_name(contact_name, template_type, salutation)
    
    msg = template.replace("[Business Name]", business_name)\
                  .replace("[Rider Name]", rider_name)\
                  .replace("[Sector]", sector)\
                  .replace("[Town]", town)\
                  .replace("[Championship Name]", championship)\
                  .replace("[Sector Hook]", hook)\
                  .replace("[Contact Name/Business Name]", formatted_name)\
                  .replace("[Contact Name]", formatted_name)\
                  .replace("[Current Year]", "2026")\
                  .replace("Good morning", _get_time_greeting())
                  
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
        
        # 1. Intro Override
        # "My name is [Rider Name]" -> "My name is [Rep Name] and I am the [Role] of [Rider Name]"
        target_intro = f"My name is {rider_name}"
        new_intro = f"My name is {rep_name} and I am the {rep_role} of {rider_name}"
        msg = msg.replace(target_intro, new_intro)
        
        # 2. Activity Pronoun Overrides
        # List of phrases where "I" refers to the Rider performing the sport
        substitutions = [
            ("I am racing", f"{rider_name} is racing"),
            ("I'm currently competing", f"{rider_name} is currently competing"),
            ("I am currently competing", f"{rider_name} is currently competing"),
            ("I’ve recently launched my", f"{rider_name} has recently launched their"),
            ("my race helmet", f"{rider_name}'s race helmet"),
            ("I believe we could", "We believe we could"),
            ("expand my network", "expand our network"),
            ("I’m focusing solely", f"{rider_name} is focusing solely"),
            ("allowing me to", f"allowing {rider_name} to")
        ]
        
        for old_phrase, new_phrase in substitutions:
            msg = msg.replace(old_phrase, new_phrase)
            
        # 3. Signature Override
        # Replace the signer (usually at the very end) from Rider Name to Rep Name
        # We use rsplit to only replace the last occurrence to avoid breaking the text body if name is mentioned there
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
                "Email: Cold Opener",
                "LI Msg 1: Connect",
                "LI Msg 2: Thanks for connecting (Day 2)",
                "LI Msg 3: Homework (Day 7)",
                "LI Msg 4: Momentum (Day 14)",
                "LI Msg 5: Scarcity (Day 21)",
                "LI Msg 6: Final (Day 28)"
            ]
            
            events = []
            for _, row in df_leads.iterrows():
                if pd.notnull(row['Next Action']):
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
                    # Full name for easy cross-referencing with LinkedIn
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
                    lat, lon = get_lat_long(google_api_key, location_search_ctx)
                    
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
        st.caption(f"📊 **{total} results** found • {high_q} high-quality leads (4-5⭐)")
                
        # --- BUILD DISPLAY COLUMNS ---
        disp_cols = ["In List", "Business Name", "Address"]
        
        if "Score" in df_results.columns:
            disp_cols.append("Score")
        if "Size" in df_results.columns:
            disp_cols.append("Size")
        if "Socials" in df_results.columns:
            disp_cols.append("Socials")
        if "Distance" in df_results.columns:
            disp_cols.append("Distance")
        
        # Only show columns that exist
        disp_cols = [c for c in disp_cols if c in df_results.columns]
            
        st.dataframe(
                df_results[disp_cols],
                width="stretch",
                column_config={
                    "Score": st.column_config.TextColumn("Quality", width="small"),
                    "Size": st.column_config.TextColumn("Est. Size", width="small"),
                    "Socials": st.column_config.TextColumn("Social", width="small"),
                    "Distance": st.column_config.NumberColumn("Miles", format="%.1f", width="small"),
                    "In List": st.column_config.TextColumn("Added", width="small"),
                }
        )
    
        
        # Add to DB Logic
        col_s1, col_s2 = st.columns([3, 1])
        with col_s1:
            add_choice = st.selectbox("Select result to track", df_results["Business Name"].unique())
        with col_s2:
            is_in_list = add_choice.lower() in existing_names
            
            if st.button("➕ Add to My Leads", disabled=is_in_list):
                if is_in_list:
                    st.error("Already in your list!")
                else:
                    row = df_results[df_results["Business Name"] == add_choice].iloc[0]
                    
                    b_name = row["Business Name"]
                    b_sect = row["Sector"]
                    b_loc = row["Address"]
                    b_web = row.get("Website", "")
                    b_contact = row.get("Owner", "")  # Pre-fill contact from owner
                    
                    # Build enriched notes from search data
                    enriched_notes = {}
                    if row.get("Owner"):
                        enriched_notes["owner"] = row["Owner"]
                    if row.get("Description"):
                        enriched_notes["description"] = row["Description"]
                    if row.get("Social") and isinstance(row["Social"], dict):
                        enriched_notes["social_links"] = row["Social"]
                        # Auto-save LinkedIn as contact URL if available
                        if row["Social"].get("linkedin"):
                            enriched_notes["contact_url"] = row["Social"]["linkedin"]
                    if row.get("Reviews"):
                        enriched_notes["reviews_count"] = int(row["Reviews"])
                    if row.get("Size"):
                        enriched_notes["company_size"] = row["Size"]
                    if row.get("Quality"):
                        enriched_notes["quality_score"] = int(row["Quality"])
                    
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
                        st.toast(f"Added {add_choice}{quality_msg}")
                        
                        # [NEW] Auto-Switch for SCOUT MODE
                        if search_mode == "Company Scout":
                            st.session_state.selected_lead_id = new_lead_id
                            st.session_state.requested_tab = "✉️ Outreach Assistant"
                            st.rerun()
                            
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
                    
                    # --- HELPER ---
                    def google_link(query, label):
                        url = f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}"
                        st.markdown(f"• [{label}]({url})")

                    # PILLAR 0: OPEN CORPORATES (NEW)
                    st.markdown("### 0️⃣ Corporate Registry (Director Search)")
                    with st.expander("🏛️ OpenCorporates Search", expanded=True):
                         st.caption("Find official directors/officers to target.")
                         
                         oc_url = f"https://opencorporates.com/companies?q={urllib.parse.quote_plus(lead['Business Name'])}"
                         st.markdown(f"**Step 1:** [Search '{lead['Business Name']}' on OpenCorporates]({oc_url})")
                         
                         st.markdown("**Step 2:** Copy found Director names below:")
                         found_directors = st.text_area("Director Names (one per line)", key="director_input", help="Paste names here to generate search links.", height=100)
                         
                         if found_directors:
                             st.markdown("**Step 3:** Deep Dive Targets")
                             # Location Logic for FB
                             addr = lead.get("Address", "")
                             location_term = ""
                             if addr:
                                 # Try to grab the city (simple heuristic: 2nd element if comma sep, else whole)
                                 parts = addr.split(',')
                                 if len(parts) > 1:
                                     location_term = parts[1].strip()
                                 else:
                                     location_term = addr

                             names = [n.strip() for n in found_directors.split('\n') if n.strip()]
                             for i, name in enumerate(names):
                                 # Clean Name (First + Last only, remove titles/commas)
                                 # Logic: "Mr. David James Smith" -> "David Smith"
                                 # Logic: "SMITH, David James" -> "David Smith" (Heuristic fit)
                                 
                                 clean_s = name.replace(",", " ").replace(".", "")
                                 parts = clean_s.split()
                                 
                                 # Strip titles
                                 titles = {"mr", "mrs", "ms", "miss", "dr", "prof", "sir"}
                                 if parts and parts[0].lower() in titles:
                                     parts.pop(0)

                                 if len(parts) >= 2:
                                     # Case: "David James Smith" -> David Smith
                                     cleaned_name = f"{parts[0].title()} {parts[-1].title()}"
                                     display_name = f"{cleaned_name}"
                                 elif parts:
                                     cleaned_name = parts[0].title()
                                     display_name = cleaned_name
                                 else:
                                     cleaned_name = name
                                     display_name = name

                                 c1, c2 = st.columns([3, 1])
                                 with c1:
                                     st.markdown(f"__🔎 {display_name}__")
                                     
                                     # LinkedIn: Use Cleaned Name
                                     google_link(f'site:linkedin.com/in "{cleaned_name}" "{lead["Business Name"]}"', f"LinkedIn Xray")
                                     
                                     # FB: Cleaned Name + Location
                                     fb_query = f"{cleaned_name} {location_term}"
                                     fb_url = f"https://www.facebook.com/search/people/?q={urllib.parse.quote_plus(fb_query)}"
                                     st.markdown(f"• [Facebook Search ({location_term})]({fb_url})")
                                 
                                 with c2:
                                     # check if this is already the saved contact
                                     is_saved = lead.get("Contact Name") == cleaned_name
                                     if is_saved:
                                         st.success("✅ Primary")
                                     else:
                                         # Save the CLEANED name
                                         if st.button("Set Primary", key=f"save_{lead['id']}_{i}"):
                                             db.update_lead_contact(lead['id'], cleaned_name)
                                             st.toast(f"Updated Contact to: {cleaned_name}")
                                             time.sleep(0.5)
                                             st.rerun()
                                 st.divider()

                    # PILLAR 1: WEB DEEP DIVE (FACT FINDING)
                    st.markdown("### 1️⃣ Web Deep Dive (Fact Finding)")
                    with st.expander("🌍 Web Intelligence", expanded=True):
                        # Helper hoisted above

                        if domain:
                            st.caption(f"Searching domain: `{domain}`")
                            # Simplified Stacks
                            google_link(f'{lead["Business Name"]}', "Google Search (General)")
                            google_link(f'{lead["Business Name"]} (news OR "new site" OR expansion OR opening)', "News & Expansion")
                            google_link(f'{lead["Business Name"]} sponsorship', "Sponsorship Check")
                            
                            # Advanced Signals
                            google_link(f'intitle:"{lead["Business Name"]}" "merger" OR "launch" OR "lawsuit"', "High Impact Headlines")
                            google_link(f'"{lead["Business Name"]}" after:2025-01-01', "Latest News (Last 12mo)")
                            google_link(f'"{lead["Business Name"]}" -site:{domain}', "External Press Only")
                        else:
                            google_link(f'{lead["Business Name"]} official site', "Find Website First")
                    
                    
                    # PILLAR 2: LINKEDIN PEOPLE SEARCH
                    st.markdown("### 2️⃣ LinkedIn (People Search)")
                    with st.expander("👔 LinkedIn Deep Search", expanded=True):
                        st.caption("Find the decision makers directly.")
                        # 1. Company Page
                        google_link(f'site:linkedin.com/company "{lead["Business Name"]}"', "Official Company Page")
                        
                        # 2. X-Ray Search (All Employees)
                        google_link(f'site:linkedin.com/in "{lead["Business Name"]}"', "All Employees (X-Ray Search)")


                        
                        # Verify Name
                        if lead.get('Contact Name'):
                            st.markdown("**Verify Contact:**")
                            google_link(f'site:linkedin.com/in "{lead["Contact Name"]}" "{lead["Business Name"]}"', f"Verify '{lead['Contact Name']}'")
                            

                    # PILLAR 3: FACEBOOK SEARCH & FINDER MODULE
                    st.markdown("### 3️⃣ Facebook (Founder Finder)")
                    with st.expander("👤 Facebook Founder Finder (Beta)", expanded=True):
                        st.caption("Use this if you can't find a contact elsewhere. Target owners of local businesses.")
                        
                        # A) Standard Search Links
                        st.markdown("**Manual Search:**")
                        google_link(f'site:facebook.com "{lead["Business Name"]}"', "Company Facebook Page")
                        google_link(f'site:facebook.com "{lead["Business Name"]}" "owner" OR "director"', "Find People associated with Company")
                        
                        st.divider()
                        






                    
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
                    

                    


                with col2:
                    # Top Controls: Action Mode + Contact Details
                    top_c1, top_c2 = st.columns([1.2, 1])
                    with top_c1:
                         c_mode = st.radio("Action Mode", ["Draft Opener", "Handle Reply"], horizontal=True)
                    with top_c2:
                         # [UPDATE] Auto-populate with latest DB value if available
                         current_contact = lead.get('Contact Name', '')
                         new_name = st.text_input("Found Contact Name", value=current_contact, key=f"contact_name_input_{lead['id']}")
                    
                    # Contact Details Row: Salutation + Profile URL
                    detail_c1, detail_c2 = st.columns([1, 2])
                    with detail_c1:
                         # Salutation selector (persisted in notes)
                         lead_notes_sal = lead.get('Notes', {})
                         if isinstance(lead_notes_sal, str):
                             try: lead_notes_sal = json.loads(lead_notes_sal)
                             except: lead_notes_sal = {}
                         saved_salutation = lead_notes_sal.get('salutation', 'Mr') if isinstance(lead_notes_sal, dict) else 'Mr'
                         sal_options = ["Mr", "Mrs", "Miss", "Ms", "Dr"]
                         sal_idx = sal_options.index(saved_salutation) if saved_salutation in sal_options else 0
                         contact_salutation = st.selectbox("Title", sal_options, index=sal_idx, key=f"sal_{lead['id']}")
                    with detail_c2:
                         # Contact Profile URL (LinkedIn, Facebook, etc.)
                         saved_url = lead_notes_sal.get('contact_url', '') if isinstance(lead_notes_sal, dict) else ''
                         contact_url = st.text_input("Profile URL (LinkedIn/Facebook)", value=saved_url, key=f"url_{lead['id']}", placeholder="https://linkedin.com/in/...")
                    
                    # Save button for all contact details
                    if st.button("Update Contact", key=f"btn_update_contact_{lead['id']}"):
                         if new_name:
                             db.update_lead_contact(lead['id'], new_name)
                             # Also save salutation and URL in notes
                             save_notes = lead.get('Notes', {})
                             if isinstance(save_notes, str):
                                 try: save_notes = json.loads(save_notes)
                                 except: save_notes = {}
                             if not isinstance(save_notes, dict): save_notes = {}
                             save_notes['salutation'] = contact_salutation
                             save_notes['contact_url'] = contact_url
                             db.update_lead_notes(lead['id'], save_notes)
                             st.toast(f"✅ Contact updated: {contact_salutation} {new_name}")
                             time.sleep(0.5)
                             st.rerun()
                         else:
                             st.warning("Please enter a contact name first.")
                    
                    if c_mode == "Draft Opener":
                        st.subheader("Outreach Message")
                        contact_name_raw = new_name if new_name else ""
                        
                        # Use saved town from profile
                        town = saved_town 
                        
                        seq_options = [
                            "Email: Cold Opener",
                            "LI Msg 1: Connect",
                            "LI Msg 2: Thanks for connecting (Day 2)",
                            "LI Msg 3: Homework (Day 7)",
                            "LI Msg 4: Momentum (Day 14)",
                            "LI Msg 5: Scarcity (Day 21)",
                            "LI Msg 6: Final (Day 28)"
                        ]
                        
                        # Auto-select to the next step based on last sent
                        lead_notes = lead.get('Notes', {})
                        if isinstance(lead_notes, str):
                            try:
                                lead_notes = json.loads(lead_notes)
                            except:
                                lead_notes = {}
                        last_sent_step = lead_notes.get('outreach_step', -1) if isinstance(lead_notes, dict) else -1
                        try:
                            last_sent_step = int(last_sent_step)
                        except:
                            last_sent_step = -1
                        auto_tpl_idx = min(last_sent_step + 1, len(seq_options) - 1)
                        if auto_tpl_idx < 0:
                            auto_tpl_idx = 0
                        
                        tpl = st.selectbox("Template", seq_options, index=auto_tpl_idx)
                        
                        # Context from Sidebar/DB
                        ctx = {
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
                        
                        # Generate message with automatic name formatting
                        # Initial messages use Mr/Mrs LastName, follow-ups use first name
                        draft = generate_message(tpl, lead['Business Name'], rider_name, lead['Sector'], town=town, championship=championship, extra_context=ctx, contact_name=contact_name_raw, salutation=contact_salutation)
                        
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
                                # 🎈 Fire balloons FIRST so the animation starts immediately
                                st.balloons()
                                
                                # 2. Update DB using decided date
                                db.update_lead_status(lead['id'], "Active", final_date)
                                
                                # 3. Track which step was sent in notes
                                current_step_idx = seq_options.index(tpl) if tpl in seq_options else 0
                                mark_notes = lead.get('Notes', {})
                                if isinstance(mark_notes, str):
                                    try:
                                        mark_notes = json.loads(mark_notes)
                                    except:
                                        mark_notes = {}
                                if not isinstance(mark_notes, dict):
                                    mark_notes = {}
                                mark_notes['outreach_step'] = current_step_idx
                                mark_notes['last_template'] = tpl
                                # Persist salutation and contact URL
                                mark_notes['salutation'] = contact_salutation
                                if contact_url:
                                    mark_notes['contact_url'] = contact_url
                                db.update_lead_notes(lead['id'], mark_notes)
                            
                                st.success(f"🎉 Message Logged! 📅 Next follow-up on {final_date}.")
                                time.sleep(3)
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
                first_name = contact_name.split()[0] if contact_name else "there"
                
                # ---- AUTO-POPULATED COMPANY INTEL ----
                with st.expander("🔍 Pre-Call Intel (Auto-Populated)", expanded=True):
                    st.caption("Review this before the call — reference something specific early to prove you did your homework.")
                    
                    intel_c1, intel_c2 = st.columns(2)
                    with intel_c1:
                        st.markdown(f"**Company:** {lead['Business Name']}")
                        st.markdown(f"**Sector:** {lead.get('Sector', '—')}")
                        st.markdown(f"**Contact:** {contact_name}")
                        if lead.get('Website'):
                            st.markdown(f"🌐 [{lead['Website']}]({lead['Website']})")
                    with intel_c2:
                        desc = existing_notes.get('description', '')
                        size = existing_notes.get('company_size', '')
                        owner = existing_notes.get('owner', '')
                        if desc:
                            st.markdown(f"**About:** {desc[:200]}")
                        if size:
                            st.markdown(f"**Est. Size:** {size}")
                        if owner:
                            st.markdown(f"**Owner/Contact:** {owner}")
                        
                        social = existing_notes.get('social_links', {})
                        if isinstance(social, dict) and social:
                            links = []
                            if social.get('linkedin'): links.append(f"[LinkedIn]({social['linkedin']})")
                            if social.get('facebook'): links.append(f"[Facebook]({social['facebook']})")
                            if social.get('instagram'): links.append(f"[Instagram]({social['instagram']})")
                            if links:
                                st.markdown("**Social:** " + " • ".join(links))
                    
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
                st.caption("Auto-filled from your Profile & Discovery Call. Edit any section below to perfect your '10/10 Template'.")
                
                # --- PREPARE DATA ---
                r_name = st.session_state.user_name
                r_series = championship
                r_bio = st.session_state.user_profile.get('bio', f"A competitive racer in {r_series}. Known for consistency and speed.")
                r_audience = f"{st.session_state.user_profile.get('social_following', 'Growing')} Followers"
                l_name = lead['Business Name']
                l_notes = lead.get('Notes', {})

                # Deep Discovery Context
                disc_context = "**Deep Discovery Findings (Client Voice):**\n"
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
                     st.warning("⚠️ No Discovery Data found. Complete the Discovery Call first for best results.")

                # --- STEP 1: PROPOSAL WORKFLOW (BLANKED) ---
                st.markdown("### 📝 Proposal Generator")
                st.info("🚧 **Under Construction**: We are defining the best workflow for V2.18 Slide Generation.")
                st.caption("The previous 'YES-GENERATING' template has been backed up while we refine this page.")
                
                # Placeholder for future workflow
                # st.markdown("#### Upcoming Features:")
                # st.markdown("- Drag & Drop Slide Ordering")
                # st.markdown("- AI-Powered Content Writing")
                # st.markdown("- PDF Export")
