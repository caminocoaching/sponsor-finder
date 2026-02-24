---
description: Product backlog and feature priority list from user feedback (Feb 2025)
---

# Sponsor Finder — Product Backlog

> Collected from 3 active users. Organized by impact × effort.

---

## 🔴 TIER 1 — High Impact / Daily Friction (Do First)

These are the items all 3 users feel every day.

### 1. Stage Visibility on Calendar ⭐ (ALL USERS)
- **Problem:** Users don't know what sequence step a contact is at when returning to the calendar
- **Fix:** Calendar events show `[Contact Name] → LI Msg 3 (Day 7)` instead of just company name
- **Effort:** Medium
- **File:** `app.py` (calendar section ~line 1068-1115)
- **Status:** [✅ DONE]

### 2. Contact Name Persistence Across Templates
- **Problem:** Primary contact name doesn't persist when switching between message templates
- **Fix:** Store contact name per lead, auto-populate across all templates once set
- **Effort:** Medium
- **Files:** `app.py` (outreach assistant section), `db_manager.py`
- **Status:** [✅ DONE]

### 3. Mr/Mrs/First Name Auto-Switch
- **Problem:** First message should use Mr/Mrs + surname, follow-ups should use first name
- **Also:** Mr/Mrs/Miss needs manual selection or dropdown to handle gender/marital status
- **Fix:** Add salutation dropdown (Mr/Mrs/Miss/Ms/Dr), auto-format based on message stage
- **Effort:** Small
- **Files:** `app.py` (_format_contact_name function ~line 370)
- **Status:** [Partially done — logic exists but no salutation selector]

### 4. Contact URL (LinkedIn/Facebook) Saved Per Contact
- **Problem:** Users have to manually search for the contact again at each follow-up stage
- **Fix:** Add URL field per lead, calendar links directly to their profile
- **Effort:** Small-Medium
- **Files:** `db_manager.py` (schema), `app.py` (outreach + calendar)
- **Status:** [✅ DONE]

### 5. Time-of-Day Greeting
- **Problem:** Messages always say "Good morning" regardless of time
- **Fix:** Auto-detect time → Good Morning / Good Afternoon / Good Evening
- **Effort:** Tiny
- **File:** `app.py` (generate_message function)
- **Status:** [✅ DONE]

---

## 🟡 TIER 2 — Medium Impact / Workflow Improvement

### 6. Dashboard "Actions Required" Buttons
- **Problem:** Buttons don't function — press them and nothing happens
- **Fix:** Wire up to filter/navigate to relevant contacts
- **Effort:** Medium
- **File:** `app.py` (dashboard section)
- **Status:** [✅ DONE]

### 7. Reply Handler — Editable Before Sending
- **Problem:** Reply handler is copy-paste only, can't edit before sending
- **Fix:** Make reply text editable in a text area before copy
- **Effort:** Small
- **File:** `app.py` (objection handling section)
- **Status:** [✅ DONE]

### 8. Login/Session Persistence
- **Problem:** Requires re-login too frequently
- **Fix:** Improve session handling / cookie persistence
- **Effort:** Small (Streamlit limitation — query params already used)
- **File:** `app.py` (auth section)
- **Status:** [Partially done — query param auto-login exists]

### 9. Calendar Shows Contact Name (Person), Not Company
- **Problem:** Calendar shows company name, users need person name for LinkedIn cross-ref
- **Fix:** Show `[Contact First Name] — [Company]` or just contact name
- **Effort:** Tiny
- **File:** `app.py` (calendar events ~line 1107)
- **Status:** [✅ DONE]

---

## 🟢 TIER 3 — Feature Additions

### 10. Discovery Call Script Update (Hormozi CLOSER)
- **Problem:** Current script too stiff/formal
- **Fix:** Replace with conversational Hormozi CLOSER framework
- **Effort:** Small
- **File:** `app.py` (DISCOVERY_QUESTIONS constant)
- **Status:** [✅ DONE]

### 11. Proposal Generator
- **Problem:** No automated proposal — manual process
- **Fix:** Input company logo, rider photos, package details → generate tailored PDF
- **Options:** Silver/Gold/Bronze tiers OR custom-fit based on discovery call
- **Effort:** Large
- **Files:** New module needed
- **Status:** [✅ DONE]

### 12. LinkedIn Employee X-Ray as Primary Search
- **Problem:** Not elevated to primary search method
- **Fix:** Make X-Ray the default/first option for finding individuals
- **Effort:** Medium
- **File:** `app.py` (search section), `search_service.py`
- **Status:** [✅ DONE]

---

## 🔵 TIER 4 — Search Quality / Filtering

### 13. Filter Out Large National/International Companies
- **Problem:** Results include DHL, large groups with no local decision-maker
- **Fix:** Employee count filter, flag chains vs local businesses
- **Effort:** Medium
- **File:** `search_service.py`
- **Status:** [✅ DONE]

### 14. Flag Companies With No Social/LinkedIn Presence
- **Problem:** Generic contact form companies waste time
- **Fix:** Auto-check for social presence, flag as low-value
- **Effort:** Medium
- **File:** `search_service.py`, `app.py`
- **Status:** [✅ DONE]

### 15. OpenCorporates — Directors Only
- **Problem:** Returns company secretaries alongside directors
- **Fix:** Filter API response to director roles only
- **Effort:** Small
- **File:** `search_service.py`
- **Status:** [✅ DONE]

### 16. Location Radius Accuracy
- **Problem:** Group/subsidiary registrations return companies outside stated radius
- **Fix:** Validate actual trading address vs registered address
- **Effort:** Medium-Large
- **File:** `search_service.py`
- **Status:** [✅ DONE]

---

## Dependency Map

```
[5. Time Greeting] → standalone, do anytime
[9. Calendar Name] → standalone, do anytime  
[3. Mr/Mrs Switch] → needs [2. Contact Persistence] first
[1. Stage on Calendar] → needs contact + stage data (already exists)
[4. Contact URL] → needs DB schema update
[6. Dashboard Buttons] → needs [1. Stage Visibility] context
[11. Proposal Generator] → needs [10. Discovery Script] done first
```
