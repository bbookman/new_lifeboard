# Simplify Database Architecture

## Overview

This document outlines the plan to simplify the database architecture by removing the dedicated `limitless` table and consolidating all Limitless data into the `data_items` table.

## Current State

*   **Dual Storage:** The system is designed to store Limitless data in two places:
    1.  The `data_items` table for unified search and embeddings.
    2.  A dedicated `limitless` table for specialized queries.
*   **Ingestion Flow:**
    1.  `LimitlessSource` fetches data from the Limitless API.
    2.  The data is transformed into a `DataItem`.
    3.  `LimitlessProcessor` processes the `DataItem` to enrich it with additional metadata.
    4.  The `IngestionService` saves the `DataItem` to the `data_items` table.
*   **Problem:** The `limitless` table methods exist but the ingestion pipeline never calls them - all data flows only to `data_items` table, making the dedicated `limitless` table unused and redundant.

## Objectives

1.  **Eliminate the `limitless` table:** Remove the redundant table to simplify the database schema.
2.  **Store cleaned markdown in `data_items`:** Add the cleaned markdown to the `metadata` column of the `data_items` table.
3.  **Update data retrieval logic:** Modify the Day View UI and any other relevant components to fetch the cleaned markdown from the `data_items` table.

## Steps

1.  **Update `LimitlessProcessor`:**
    *   Modify the `LimitlessProcessor` in `sources/limitless_processor.py` to generate the cleaned markdown.
    *   Add the cleaned markdown to the `metadata` field of the `DataItem` with a key like `"cleaned_markdown"`.
2.  **Update `DatabaseService`:**
    *   Remove the following methods from `core/database.py`:
        *   `store_limitless_item`
        *   `get_limitless_items`
        *   `get_limitless_item_by_lifelog_id`
        *   `get_limitless_items_by_date`
3.  **Update `api/routes/calendar.py`:**
    *   Modify the calendar route to fetch data directly from the `data_items` table instead of the `limitless` table.
    *   Extract the cleaned markdown from the `metadata` field.
4.  **Remove `limitless` table migration:**
    *   Delete the `LimitlessTableMigration` class from `core/migrations.py`.
5.  **Update Documentation:**
    *   Update any documentation that refers to the `limitless` table to reflect the new architecture.

This simplification will result in a more streamlined and maintainable codebase.
