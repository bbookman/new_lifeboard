### Feature Goal

The primary goal is to create a new data source for the application that can parse a user's downloaded Twitter data archive, extract key information from their tweets, and store it in the application's database for display and analysis.

### Plan Overview

The implementation will follow the existing architectural pattern for data sources like Weather and News. This involves creating a configuration model, a database migration, a dedicated source service for the core logic, and integrating it into the application's startup and sync processes.

---

### 1. Configuration

**File:** `config/models.py`, `config/factory.py`

-   **Create `TwitterConfig` Model:** A new Pydantic model named `TwitterConfig` will be created in `config/models.py`. It will manage settings specific to the Twitter data source.
    -   `enabled`: A boolean to turn the feature on or off.
    -   `data_path`: The absolute file path to the root of the unzipped Twitter archive directory (e.g., `/path/to/twitter-2024-07-30`). This will be loaded from the `.env` variable `PATH_TO_TWITTER_DATA`.
    -   `delete_after_import`: A boolean (from `.env` variable `DELETE_AFTER_IMPORT`) to control whether the source directory is deleted after a successful import.
    -   `sync_interval_hours`: How often the application should check the `data_path` for new data.

-   **Update `AppConfig`:** The main `AppConfig` model will be updated to include the new `TwitterConfig`.

-   **Update Config Factory:** The `create_production_config` function in `config/factory.py` will be updated to load these new environment variables from the `.env` file.

### 2. Database Migration

**File:** `core/migrations.py`

-   **Create `tweets` Table:** A new database migration will be created to add a table named `tweets`. This ensures the database schema is correctly set up on application startup. The table will have the following columns:
    -   `tweet_id`: `TEXT`, `PRIMARY KEY`
    -   `created_at`: `TEXT` (storing the ISO 8601 timestamp)
    -   `days_date`: `TEXT` (a `YYYY-MM-DD` string derived from `created_at` for efficient querying)
    -   `text`: `TEXT` (the full text of the tweet)
    -   `media_urls`: `TEXT` (a JSON-encoded array of strings for any associated media URLs)

### 3. Twitter Source Implementation

**File:** `sources/twitter.py` (new file)

-   **Create `TwitterSource` Class:** A new class inheriting from `BaseSource` will be created. This class will encapsulate all logic for handling the Twitter data.
    -   **Parsing Logic:** The core logic will be adapted from the provided example script (`supporting_documents/extract_tweets.py`). It will be responsible for reading the `tweet.js` file (and `tweet-headers.js` if needed) from the Twitter archive, handling the specific JS-wrapped JSON format, and extracting the required fields for each tweet.
    -   **Data Storage:** A method will be created to take the list of parsed tweets and insert them into the `tweets` table. It will use an `INSERT OR IGNORE` statement to prevent duplicate entries and gracefully handle re-running the import on the same data.
    -   **File Handling:** The source will implement the `fetch_data` method. This method will check if the `data_path` is valid, trigger the parsing and storing process, and, if `delete_after_import` is true, it will delete the entire Twitter data directory upon successful completion.

### 4. System Integration

**Files:** `services/startup.py`, `api/routes/sync.py`, `templates/settings.html`

-   **On-Demand API Endpoint:** A new API endpoint, `POST /api/sync/twitter`, will be created in `api/routes/sync.py`. This endpoint will be responsible for initiating the Twitter data import process. It will not be on a timer and will only run when explicitly called by the user from the UI.

-   **Background Task Processing:** To prevent UI freezes and request timeouts during potentially long imports, the endpoint will use FastAPI's `BackgroundTasks`. It will immediately add the import process to a background queue and return a success message to the user, while the actual import runs asynchronously.

-   **Source Registration:** The `TwitterSource` will be registered with the `IngestionService` in `services/startup.py`. This makes the application aware of the source so it can be called by the API endpoint. It will *not* be registered with the `SyncManagerService` to ensure it never runs on an automatic schedule.

-   **UI Trigger:** The `templates/settings.html` page will contain the button that, when clicked, makes a `POST` request to the `/api/sync/twitter` endpoint, triggering the entire process.
