# Monetization & Token Usage Strategy

This document outlines a theoretical framework for monetizing the Sponsor Finder app using a usage-based (token) model to ensure API costs are covered and profit is generated.

## 1. The Core Concept: "Credits"
Instead of charging just a flat monthly fee, you sell **Credits** (or Tokens). Every expensive action in the app consumes credits.

### Why this works:
*   **Aligns Cost with Price:** Google charges you per API call (Search, Details, Maps). If a user searches 100 times, they cost you more than a user who searches once.
*   **Scalable:** Heavy users pay more, light users pay less.
*   **Perceived Value:** Users treat "Credits" like currency, making them more thoughtful about their searches.

## 2. Token Economy (Example)

**Your Costs (Approximate):**
*   Google Places Search: ~$0.02 - $0.03 per request (loading 20 results).
*   Google Place Details (Phone/Website): ~$0.02 per result.

**Proposed Exchange Rate:**
*   **1 Credit = £0.10 (10 pence)**
*   **Search (20 Results):** Costs User **1 Credit** (You pay ~2p, Profit ~8p).
*   **Unlock Full Details (Email/Phone):** Costs User **1 Credit** (You pay ~2p, Profit ~8p).

## 3. Pricing Models

### A. Subscription Plans (Recurring Revenue)
*   **Starter (£29/month):** Includes **300 Credits** (enough for ~6000 leads).
*   **Pro (£79/month):** Includes **1000 Credits**.

### B. Pay-As-You-Go (Top-Ups)
*   If a user runs out, they can buy a "Race Fuel Pack":
    *   **£10** for **100 Credits**
    *   **£50** for **600 Credits** (Bulk discount)

## 4. Technical Implementation Strategies

### Step 1: Database Updates
You need to track the balance.
**Table: `users`**
*   Add column: `credit_balance` (Integer, default 10).
*   Add column: `stripe_customer_id` (String).

**Table: `transactions`** (New)
*   Columns: `id`, `user_id`, `amount`, `type` (debit/credit), `description` (e.g., "Search - Silverstone"), `timestamp`.

### Step 2: The Gatekeeper (Middleware)
Before running a function like `search_google_places`, the app checks the balance.

```python
def run_search(user_id, query):
    # 1. Check Balance
    balance = db.get_user_balance(user_id)
    cost = 1 # 1 Credit per search
    
    if balance < cost:
        st.error(f"⚠️ Insufficient Fuel! You need {cost} credits but have {balance}.")
        st.markdown("[⛽ Buy More Credits](#)")
        return None

    # 2. Run API
    results = google_places_api.search(query)

    # 3. Deduct
    if results:
        db.update_balance(user_id, -cost)
        db.log_transaction(user_id, -cost, f"Search: {query}")
        
    return results
```

### Step 3: Payment Integration (Stripe)
*   Use **Stripe Checkout** links. It's the easiest way. No complex frontend code needed.
*   Create a "Product" in Stripe called "100 Credits".
*   Stripe gives you a generic link (or you generate a specific one via API).
*   **Webhook Listener:** You need a small background script (or serverless function) that listens for Stripe to say "Payment Success". When that happens, it finds the user in your DB and adds +100 to `credit_balance`.

## 5. Protecting Your Margins

### Caching (The Secret Weapon)
You only pay Google **once** per unique search.
*   **Tech:** If User A searches "Plumbers in Silverstone", save the JSON result in your database.
*   **Scenario:** If User B searches "Plumbers in Silverstone" tomorrow, serve them the **saved database result**.
*   **Result:** User B pays you 1 Credit. You pay Google **£0**. **100% Profit margin.**

## 6. Where to Start? (Roadmap)
1.  **Manual Mode (MVP):** Add the `credit_balance` column. Give everyone 50 free credits. When they run out, they have to email you to buy more (you manually update the DB). This tests if people *want* the data enough to pay.
2.  **Stripe Link:** Add a "Buy Credits" button that opens a Stripe payment link.
3.  **Full Automation:** Build the webhook to auto-credit the account.
