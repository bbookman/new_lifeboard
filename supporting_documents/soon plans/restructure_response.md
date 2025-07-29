# Plan for Implementing Restructured Response Feature

This document outlines the plan to implement a feature that restructures the response from the Limitless API to support a table of contents in the UI. The core of this plan is to pre-process the API data and store it in a new database column for efficient retrieval.

## 1. Database Migration

*   **Objective:** Add a new `restructured_response` column to the database table that stores lifelog data.
*   **Action:**
    1.  Identify the SQLAlchemy model corresponding to the lifelogs data.
    2.  Add a new column `restructured_response` to the model, using the `JSON` data type.
    3.  Generate a new database migration script using Alembic.
    4.  Apply the migration to update the database schema.

## 2. Backend Data Transformation

*   **Objective:** Create the logic to transform the raw Limitless API response into a structured format suitable for the UI.
*   **Action:**
    1.  Locate the service or function responsible for fetching data from the Limitless API.
    2.  Implement a new function that takes the raw `contents` array from the API response as input.
    3.  This function will iterate through the `contents` and build a new JSON structure composed of "sections," where each section has a heading, an anchor ID, a "borrowed" `startTime`, and a list of associated transcripts.
    4.  Integrate this transformation function into the data ingestion process. When new data is fetched from Limitless, it will be immediately processed and the resulting JSON will be stored in the `restructured_response` column.

## 3. API Endpoint Modification

*   **Objective:** Update the API endpoint that serves data to the frontend to use the new, pre-processed data.
*   **Action:**
    1.  Identify the FastAPI route that provides lifelog data to the frontend.
    2.  Modify the endpoint's logic to retrieve the data directly from the `restructured_response` column instead of processing it on-the-fly.
    3.  This will ensure the API is fast and sends a clean, purpose-built data structure to the client.

This plan ensures a robust, performant, and maintainable implementation by separating the data transformation from the presentation layer.
