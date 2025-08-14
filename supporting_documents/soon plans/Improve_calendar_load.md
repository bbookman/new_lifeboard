# Recommendations for Improving Calendar Data Load Times

Here are some recommendations for improving the calendar data load times, especially after a server restart:

## Backend (`api/routes/calendar.py` and Database Layer):

1.  **Optimize Database Queries for `get_days_with_data`:**
    *   The current implementation makes multiple database calls (`database.get_days_with_data()` for 'all' and then for each namespace).
    *   **Recommendation:** Refactor `database.get_days_with_data()` to retrieve all necessary date-namespace mappings in a single, optimized query. This could involve a single query that groups by date and aggregates associated namespaces, or returns `(date, namespace)` pairs that can be processed in Python to build the required structure. This reduces database round-trips.
2.  **Implement Server-Side Caching:**
    *   The `get_days_with_data` endpoint fetches data that doesn't change frequently.
    *   **Recommendation:** Introduce an in-memory cache for the results of `get_days_with_data`. This could be a simple `functools.lru_cache` on the `DatabaseService` method or a more sophisticated caching solution. The cache should be invalidated whenever new data is ingested (e.g., via `fetch_limitless_for_date` or other ingestion processes) to ensure data freshness. This will significantly speed up subsequent requests after the initial load and after server restarts (once the cache is warmed).
3.  **Consider Database Indexing:**
    *   **Recommendation:** Ensure that the underlying database table storing calendar data has appropriate indexes on columns used for querying, such as `date` and `namespace`. This will speed up the raw database queries.
4.  **Pre-computation/Warm-up (Advanced):**
    *   **Recommendation:** For the very first load after a server restart, consider a mechanism to pre-compute and load the `days_with_data` into the server-side cache during application startup. This would make the initial request almost instantaneous.

## Frontend (`frontend/src/components/CalendarView.tsx`):

1.  **Client-Side Caching:**
    *   The frontend currently refetches data for each month navigation.
    *   **Recommendation:** Implement a client-side cache (e.g., a `Map` object in `CalendarView.tsx`) to store the `DaysWithDataResponse` for previously viewed months. Before making an API call, check if the data for the requested month is already in the cache.
2.  **Prefetching Adjacent Months:**
    *   **Recommendation:** When a user views a particular month, proactively fetch the data for the previous and next months in the background. This anticipates user navigation and makes transitions between months feel much faster.
