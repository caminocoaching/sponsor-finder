
# 🚀 Search & Infrastructure Upgrade (v2.5) - Feb 4, 2026

## 1. High-Precision Local Search (Outscraper V3)
- **Strict Radius Enforcement:** Replaced broad search with a strict distance filtering mechanism. Results are now guaranteed to be within the user's specified miles (e.g., 50 miles strictly enforced, eliminating results 200+ miles away).
- **International Support:** Added automatic region detection for **UK, USA, Australia, New Zealand, Hungary**, and 10+ other countries. The system detects the user's location string (e.g., "Sydney, Australia") and silently routes the request to the correct API endpoint (`region="AU"`), ensuring global compatibility without user profile changes.
- **Smart Fallback:** If a strict search returns zero results, the system intelligently falls back to a wider search and then filters manually to ensure data quality.

## 2. Cost & Performance Optimization
- **Micro-Batching:** Reduced initial API fetch size from ~500 to **40 results per keyword**. This dramatically lowers API usage costs while providing a faster initial response.
- **Pagination ("Load More"):** Implemented a "Deeper Search" button. Users can now load results in batches (pages of ~40-60) rather than paying for all 500 at once.
- **7-Day Caching:** Added a persistent disk cache layer. If a user repeats the same search within 7 days, results are loaded instantly from the cache ($0 cost) instead of hitting the API again.

## 3. Data Quality & Sorting
- **Distance Sorting:** All search results are now automatically sorted by **distance (closest first)**. Users see the 0.5-mile opportunity before the 40-mile one.
- **Deduplication:** Enhanced logic to merge results from multiple keywords (e.g., "Haulage" + "Transport") into a single, clean list without duplicates.

## 4. Stability Fixes
- **DNS/Connection Fix:** Resolved `NameResolutionError` by integrating the robust `OutscraperClient` SDK with retry logic.
- **Error Handling:** Added better feedback for zero results or API timeouts.
