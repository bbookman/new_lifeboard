# Plan: Ensuring Complete Limitless Data

This document outlines the plan to address the issue of incomplete Limitless data being displayed to the user, with a robust system for updating it once the complete data is available.

## Status

- [x] **Step 1: Database Migration** - Create migration for `ingestion_status` column.
- [x] **Step 2: Update Backend Logic** - Modify `DatabaseService` and ingestion scripts.
- [ ] **Step 3: Implement Notifications** - Add WebSocket broadcast after scheduled ingestion. [NOT STARTED]
- [ ] **Step 4: Update Frontend** - Add WebSocket listener and data-refetch logic in React. [NOT STARTED]

---

## Recommended Approach: Status Flag & WebSocket Notifications

This approach combines a database status flag to track data completeness with a real-time WebSocket notification system to inform the frontend when new data is ready.

### New Architectural Insight: FullStackOrchestrator

A recent refactoring introduced `core/orchestration.py` and the `FullStackOrchestrator`. This orchestrator is now responsible for managing the overall startup of both the frontend and backend components, including port resolution and process management. However, it does *not* directly initialize the core backend services (like `DatabaseService`, `IngestionService`, `SyncManagerService`, or `WebSocketManager`). These services are still initialized within the `lifespan` context of `api/server.py` via the `initialize_application` function.

This means the strategy for integrating `WebSocketManager` into the backend services remains largely the same: initialize it early in `api/server.py`'s `lifespan` and make it globally accessible.

### 1. Database: Add an `ingestion_status` Column [COMPLETED]

*   **Action**: A migration file (`0008_add_ingestion_status_to_data_items.py`) has been created to add the `ingestion_status` column to the `data_items` table.
*   **Note on Execution**: This migration is expected to be run implicitly when the application starts and `DatabaseService` is initialized.

### 2. Backend Logic: Update Ingestion Pipeline [COMPLETED]

*   **Action**: The backend services have been updated to handle the new status.
    *   `core/database.py` was modified to save and update the `ingestion_status`.
    *   `services/ingestion.py` was modified to accept an `ingestion_mode` and pass the status to the database.
    *   `services/sync_manager_service.py` was modified to specify `'partial'` or `'complete'` ingestion modes for different sync types.

### 3. Backend: Implement a Notification Service [NOT STARTED]

*   **Goal**: Enable real-time notifications from the backend to the frontend when complete data for a day is available.
*   **Mechanism**: Utilize the `WebsocketManager` (`services/websocket_manager.py`).
*   **Steps**:
    1.  **Re-implement Global `WebSocketManager` Singleton**: Add a global instance and getter/setter functions (`get_websocket_manager`, `set_websocket_manager`) in `services/websocket_manager.py` to make the manager accessible throughout the application.
    2.  **Initialize `WebSocketManager` in `api/server.py` Lifespan**: Create an instance of `WebSocketManager` and set the global instance during the application's startup phase within the `lifespan` context in `api/server.py`. Ensure its `start()` and `stop()` methods are called appropriately during application lifecycle.
    3.  **Update `api/routes/websocket.py`**: Modify this file to use the globally accessible `WebSocketManager` instance instead of creating its own.
    4.  **Integrate Notifications into `IngestionService`**: Modify `services/ingestion.py` to:
        *   Import `get_websocket_manager`.
        *   Track all unique `days_date` values of items processed during an ingestion run.
        *   After a successful `'complete'` ingestion (i.e., when `ingestion_mode` is `'complete'`), retrieve the global `WebSocketManager` instance.
        *   For each unique `days_date` that was processed, call `websocket_manager.send_day_update(days_date=date, update_data={"status": "complete"})`.

### 4. Frontend: Listen for and React to Notifications [NOT STARTED]

*   **Action**: Update the relevant React component (e.g., `DayView.tsx`) to handle WebSocket communication.
*   **Logic**: (Remains unchanged from previous plan)
    1.  Establish a WebSocket connection on component mount.
    2.  Listen for the `data_updated` event.
    3.  If the message's `source` is `limitless` and the `date` matches the currently viewed date, trigger an API call to re-fetch the data.
    4.  React's state will automatically update the UI with the complete data.

## Benefits of this Approach

*   **Efficiency**: Eliminates the need for the frontend to repeatedly poll the server.
*   **User Experience**: Provides seamless, automatic updates for the user without requiring a manual refresh.
*   **Robustness**: The database `ingestion_status` serves as a reliable source of truth for data state.
*   **Scalability**: This pattern is reusable for other asynchronous data sources.