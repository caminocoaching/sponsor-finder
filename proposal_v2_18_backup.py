                # --- STEP 1: THE TEMPLATE BUILDER (V2.18 YES-GENERATING) ---
                with st.form("deck_builder"):
                    st.markdown("### 🏗️ The 'YES-GENERATING' Proposal Deck (12 Slides)")
                    st.caption("Based on 'YES-GENERATING MOTORSPORT SPONSORSHIP PROPOSAL.pdf'")
                    
                    # Slide 1: Executive Summary
                    with st.expander("Slide 1: Executive Summary (The One-Page Sell)", expanded=False):
                        s1_title = st.text_input("Title", value=f"{r_name} x {l_name}: Partnership Proposal 2026")
                        s1_summary = st.text_area("Summary", value=f"A commercial partnership with {r_name} in the {r_series}. Offers brand exposure, hospitality, and direct activation.")
                        
                    # Slide 2: Athlete Profile
                    with st.expander("Slide 2: Athlete Profile (Why You?)", expanded=False):
                        st.info("💡 **Success Tip:** People invest in people. Share your passion, challenges, and what drives you to compete.")
                        
                        c2a, c2b = st.columns(2)
                        s2_real_name = c2a.text_input("Full Name", value=r_name)
                        s2_race_name = c2b.text_input("Racing Name / Number", value=f"{r_name} #1")
                        
                        c2c, c2d, c2e = st.columns(3)
                        s2_age = c2c.text_input("Age / DOB")
                        s2_home = c2d.text_input("Hometown", value=st.session_state.user_profile.get('town', ''))
                        s2_cat = c2e.text_input("Racing Category", value=r_series)
                        
                        s2_story = st.text_area("Your Personal Story (300-500 words)", value=r_bio, help="This is your opportunity to build an emotional connection.")
                        s2_mission = st.text_input("Mission Statement", value="Clear, professional, ambitious.")
                        s2_vision = st.text_area("Long-Term Vision (3-5 years)", value="To progress from National Champion to World Championship contender.")
                        s2_team = st.text_area("Team & Support Network", value="Managed by [Name], Engineered by [Name].")
                        
                    # Slide 3: Performance (Auto-Calc)
                    with st.expander("Slide 3: Performance & Value (The Data)", expanded=False):
                        st.info("📊 **2026 Standard:** Lead with DATA. Sponsors want measurable proof of your trajectory.")
                        
                        st.markdown("**Current Season Performance**")
                        c3a, c3b, c3c = st.columns(3)
                        p_races = c3a.number_input("Races Entered", min_value=0, value=10)
                        p_wins = c3b.number_input("Wins", min_value=0, value=2)
                        p_podiums = c3c.number_input("Podium Finishes", min_value=0, value=5)
                        
                        c3d, c3e, c3f = st.columns(3)
                        p_top10 = c3d.number_input("Top 10 Finishes", min_value=0, value=8)
                        p_poles = c3e.number_input("Pole Positions", min_value=0, value=1)
                        p_frontrow = c3f.number_input("Front Row Starts", min_value=0, value=3)
                        
                        c3g, c3h = st.columns(2)
                        p_pos = c3g.text_input("Championship Position", value="3rd")
                        p_points = c3h.number_input("Championship Points", min_value=0, value=150)
                        
                        # CALCULATION LOGIC
                        win_rate = (p_wins / p_races * 100) if p_races > 0 else 0
                        podium_rate = (p_podiums / p_races * 100) if p_races > 0 else 0
                        top10_rate = (p_top10 / p_races * 100) if p_races > 0 else 0
                        
                        # Display Calculated Stats
                        st.caption(f"📈 **Auto-Calculated Rates:** Win: {win_rate:.1f}% | Podium: {podium_rate:.1f}% | Top 10: {top10_rate:.1f}%")
                        
                        s3_highlights = st.text_area("Career Highlights (Timeline)", "2024: [Result]\n2025: [Result]")
                        s3_goals = st.text_area("2026 Season Goals", "1. Win the Championship.\n2. Secure 5 Pole Positions.")
                        
                        s3_metrics_summary = f"Races: {p_races} | Wins: {p_wins} ({win_rate:.0f}%) | Podiums: {p_podiums} ({podium_rate:.0f}%) | Champ Pos: {p_pos}"

                    # Slide 4: Championship
                    with st.expander("Slide 4: The Platform (Championship)", expanded=False):
                        s4_series = st.text_area("Series Value", value=f"{r_series}: The premier class for [Region]. Reach: TV global audience, Tier-1 Competition.")
                        
                    # Slide 5: Audience
                    audience_source = "Growing Fanbase"
                    if 'social_audit_data' in st.session_state.user_profile:
                        # Format detailed breakdown
                        audit = st.session_state.user_profile['social_audit_data']
                        total = st.session_state.user_profile.get('social_following', 'Unknown')
                        audience_source = f"Total Reach: {total}. (Verified via Social Audit)"
                    else:
                         audience_source = f"Reach: {r_audience}"
                    with st.expander("Slide 5: Audience (Verified Data)", expanded=False):
                        s5_data = st.text_area("Demographics & Reach", value=f"{audience_source}. \nProfile: Tech-savvy, High disposable income, 70% Male / 30% Female.")

                    # Slide 6: Brand Value (NEW)
                    st.info("👇 **CRITICAL: The Commercial Why**")
                    with st.container(border=True):
                        st.markdown("**Slide 6: Brand Value Proposition**")
                        default_val = "1. Brand Visibility (Livery)\n2. B2B Networking (Paddock Access)\n3. Lead Generation"
                        s6_value = st.text_area("What they get (Business Outcomes)", value=default_val, height=100)
                        
                    # Slide 7: Deliverables
                    st.info("👇 **CRITICAL: The Activation Plan**")
                    with st.container(border=True):
                        st.markdown("**Slide 7: Activation & Deliverables**")
                        s7_act = st.text_area("Activation Ideas", value="1. VIP Trackside Experience.\n2. Co-branded Content Series.\n3. Logo on Bike & Leathers.", height=100)

                    # Slide 8: Sustainability
                    with st.expander("Slide 8: Sustainability & ESG", expanded=False):
                        s8_esg = st.text_input("ESG Commitment", value="Carbon-neutral travel, Youth coaching programs, Road safety advocacy.")
                        
                    # Slide 9: Packages
                    st.info("👇 **CRITICAL: The Deal**")
                    with st.container(border=True):
                        st.markdown("**Slide 9: Sponsorship Packages**")
                        s9_tiers = st.text_area("Investment Tiers", value="Platinum (£25k): Title Rights, Full Livery.\nGold (£15k): Major Branding, VIP Passes.\nSilver (£5k): Logo Placement.")

                    # Slide 10: ROI
                    with st.expander("Slide 10: ROI & Media Value", expanded=False):
                        s10_roi = st.text_input("ROI Method", value="Media Value + Hospitality Value + Direct Sales > Investment Check")

                    # Slide 11: Visual Proof (NEW)
                    st.info("👇 **CRITICAL: Visual Proof**")
                    with st.container(border=True):
                        st.markdown("**Slide 11: Visual Proof (Mockups)**")
                        st.caption("Describe the mockups you will attach (e.g., 'Gold Livery Render').")
                        s11_visuals = st.text_input("Mockup Description", value=f"{r_series} Car/Bike in {l_name} Colors (Render Ready)")
                        
                    # Slide 12: Next Steps
                    with st.expander("Slide 12: Partnership Statement", expanded=False):
                        s12_close = st.text_input("Closing Statement", value="Let's build a winning partnership for 2026.")

                    # GENERATE
                    st.divider()
                    if st.form_submit_button("✨ Generate 'YES-GENERATING' Prompt"):
                        
                        # Build the prompt (V2.17 YES-GENERATING Framework)
                        manus_prompt = f"""
Create a "YES-GENERATING" Motorsport Sponsorship Deck for '{r_name}' pitching to '{l_name}'.
**Framework:** Based on 'YES-GENERATING MOTORSPORT SPONSORSHIP PROPOSAL.pdf'.
**Tone:** Professional, Commercial, Urgent.

**Context:**
{disc_context}

---
**Structure (12 Slides - Strictly Followed):**

**Slide 1: Executive Summary**
- **Title:** {s1_title}
- **Summary:** {s1_summary}

**Slide 2: Athlete Profile**
- **Name:** {s2_real_name} (Racing as: {s2_race_name})
- **Details:** Age: {s2_age}, Home: {s2_home}, Series: {s2_cat}
- **Personal Story:** {s2_story}
- **Mission:** {s2_mission}
- **Vision:** {s2_vision}
- **Team:** {s2_team}

**Slide 3: Performance & Value**
- **2026 Season Stats:**
  - {s3_metrics_summary}
  - Top 10 Finishes: {p_top10}
  - Poles: {p_poles}
  - Champ Points: {p_points}
- **Career Highlights:** {s3_highlights}
- **Goals:** {s3_goals}

**Slide 4: The Platform**
- **Series:** {s4_series}

**Slide 5: Audience**
- **Data:** {s5_data}
- **Visual:** [CHART: Demographics Infographic]

**Slide 6: Brand Value Proposition**
- **Benefits:** {s6_value}

**Slide 7: Activation & Deliverables**
- **Plan:**
{s7_act}

**Slide 8: Sustainability (ESG)**
- **Focus:** {s8_esg}

**Slide 9: Packages**
- **Tiers:**
{s9_tiers}

**Slide 10: ROI**
- **Formula:** {s10_roi}

**Slide 11: Visual Proof**
- **Visuals:** [Include MOCKUPS: {s11_visuals}]
- *Note to Designer: This slide requires high-quality renders.*

**Slide 12: Closing**
- **Statement:** {s12_close}
- **Contact:** [Insert Contact Details]
"""
                        st.success("✨ Strategy Generated (V2.17)!")
                        st.code(manus_prompt, language=None)
                        
                        st.divider()
                        st.markdown("### 📧 Send")
                        subject = urllib.parse.quote(f"Proposal: {r_name} x {l_name}")
                        mailto = f"mailto:team@caminocoaching.co.uk?subject={subject}&body=(Paste%20Prompt)"
                        st.link_button("📤 Open Email", mailto)
                        st.caption("🚀 Or paste into https://manus.im/app")
