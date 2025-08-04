# Plan for Implementing Restructured Response Feature

This document outlines the plan to implement a feature that restructures the response from the Limitless API to support a table of contents in the UI. This plan aligns with the simplified database architecture, which consolidates all Limitless data into the `data_items` table.

## 1. Backend Data Transformation

*   **Objective:** Create the logic to transform the raw Limitless API response into a structured format suitable for the UI and store it in the `metadata` column of the `data_items` table.
*   **Action:**
    1.  Locate the `LimitlessProcessor` in `sources/limitless_processor.py`.
    2.  Implement a new function within the processor that takes the raw `contents` array from the API response as input.
    3.  This function will iterate through the `contents` and build a new JSON structure composed of "sections," where each section has a heading, an anchor ID, a "borrowed" `startTime`, and a list of associated transcripts.
    4.  Integrate this transformation function into the `process` method of the `LimitlessProcessor`. The resulting JSON will be added to the `metadata` field of the `DataItem` with a key like `"restructured_response"`.

## 2. API Endpoint Modification

*   **Objective:** Update the API endpoint that serves data to the frontend to use the new, pre-processed data from the `metadata` column.
*   **Action:**
    1.  Identify the FastAPI route that provides lifelog data to the frontend (likely in `api/routes/calendar.py`).
    2.  Modify the endpoint's logic to retrieve the `DataItem` from the `data_items` table.
    3.  Extract the `restructured_response` JSON from the `metadata` column.
    4.  This will ensure the API is fast and sends a clean, purpose-built data structure to the client.

This plan ensures a robust, performant, and maintainable implementation by leveraging the simplified database architecture and centralizing data transformation within the `LimitlessProcessor`.
