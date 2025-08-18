````markdown
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Lifeboard is an interactive reflection space and AI-powered planning assistant that transforms daily digital history into a personal newspaper. It integrates conversations, activities, moods, and experiences with AI assistance for discovery and planning.

Key features:
- Interactive reflection space with infinite discovery opportunities
- AI assistant for natural conversation and planning
- Digital history integration (conversations, activities, moods, experiences)
- Random resurfacing of forgotten moments and AI-guided discovery journeys
- Personal assistant functionality (to-dos, meeting insights, medical appointments)
- Open source implementation

## Architecture

The project follows a KISS multi-source memory chat application architecture with:

### Data Flow
- All sources → DataItem objects → processor pipeline (if needed) → store in data_items table → generate embeddings → add to FAISS with same ID
- Search: embed query → search FAISS → retrieve top vector IDs → fetch data_items rows → pass to LLM
- Updates: update data_items row → re-embed → update FAISS vector

**Unified Architecture**: All data sources yield DataItem objects that flow through the standard ingestion pipeline and are stored in the unified `data_items` table. Source-specific processing (deduplication, segmentation) is handled by processor classes where needed.

### Core Services
- **Database Service:** SQLite operations with namespaced ID management.
- **Vector Store Service:** FAISS similarity search.
- **Embedding Service:** Text-to-vector conversion using sentence-transformers.
- **Ingestion Service:** Orchestrates data processing from sources.
- **Scheduler Service:** Manages background tasks and scheduled jobs.
- **Sync Manager Service:** Handles the synchronization of data from various sources.
- **Chat Service:** Manages chat interactions and context.
- **Startup Service:** Orchestrates application initialization and shutdown.

### Database Schema
```sql
-- Core data storage
CREATE TABLE data_items (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    source_id TEXT NOT NULL,
    content TEXT,
    metadata TEXT,
    embedding_status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
   days_date TEXT NOT NULL
);

-- Manages data sources
CREATE TABLE data_sources (
    namespace TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    metadata TEXT,
    item_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    last_synced TIMESTAMP,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Stores chat history
CREATE TABLE chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_message TEXT NOT NULL,
    assistant_response TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Source-specific tables (for specialized queries and caching)
-- All data is also stored in unified data_items table

-- Weather data cache for API response storage
CREATE TABLE weather (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    days_date TEXT NOT NULL,
    response_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- News headlines cache for deduplication
CREATE TABLE news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    link TEXT,
    snippet TEXT,
    days_date TEXT NOT NULL,
    thumbnail_url TEXT,
    published_datetime_utc TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Limitless lifelog data for specialized processing
CREATE TABLE limitless (
    id TEXT PRIMARY KEY,
    lifelog_id TEXT NOT NULL UNIQUE,
    title TEXT,
    start_time TEXT,
    end_time TEXT,
    is_starred BOOLEAN DEFAULT FALSE,
    updated_at_api TEXT,
    processed_content TEXT,
    raw_data TEXT,
    days_date TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- General application settings
CREATE TABLE system_settings (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP
);

-- Database migration tracking
CREATE TABLE migrations (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Namespaced IDs

Format: `namespace:source_id` for data isolation and filtering.

## External Integrations

### Limitless API
*   **Purpose:** Primary source for lifelog data, including conversations and activities.
*   **Base URL:** `https://api.limitless.ai/v1/`
*   **Auth:** `X-API-Key` header

### News API
*   **Purpose:** Fetches real-time news headlines.
*   **Endpoint:** `real-time-news-data.p.rapidapi.com`
*   **Auth:** `X-RapidAPI-Key` header

### Weather API
*   **Purpose:** Retrieves 5-day weather forecasts.
*   **Endpoint:** `easy-weather1.p.rapidapi.com/daily/5`
*   **Auth:** `X-RapidAPI-Key` header

## Development Approach

*   **Configuration:** All configuration is managed through Pydantic models defined in `config/models.py` and loaded via the factory in `config/factory.py`. `.env` files are used for local development.
*   **Dependency Injection:** Services are designed to be injected, improving testability.
*   **Single Responsibility:** Services and modules have a clear and focused purpose.
*   **Database-First Settings:** Application settings are stored in the database to avoid reliance on environment variables for state.
*   **Eager Initialization:** Services are initialized at startup to ensure the application is in a valid state and to fail fast if there are issues.

## Testing

*   **Framework:** `pytest`
*   **Location:** All tests are located in the `/tests` directory at the project root.
*   **Execution:** Run tests using `PYTHONPATH=. python -m pytest`.
*   **Test Review:** A `test_review.md` file is maintained to document the investigation of test failures and propose solutions.

## Project Structure

```
/
├── api/
│   └── routes/
├── config/
├── core/
│   └── migrations/
├── llm/
├── services/
├── sources/
├── templates/
├── tests/
├── logs/
├── supporting_documents/
├── .env.example
├── requirements.txt
├── README.md
└── CLAUDE.md
```

## Logging

*   **Centralized Configuration:** Logging is configured centrally in `core/logging_config.py` using the `setup_application_logging` function.
*   **Log Directory:** All logs are written to the `/logs` directory at the project root.
*   **Error Handling:** All errors should be logged with specific exceptions. Avoid bare `except` clauses.

## Claude Guidelines

### Role

Claude should:

* Write new code, refactor, and explain existing code
* Access and modify all codebase parts without restrictions

### Coding Rules

* Follow KISS, DRY, SOLID principles
* Use `pydantic` for data models and `fastapi` for APIs
* Always add type hints
* Use modern Python features (dataclasses, async/await) where appropriate
* Follow snake\_case naming
* Prefix test files with `test_` in `/tests`
* Write comments and docstrings for all functions and classes
* Avoid code duplication by reusing existing code
* Maintain a list of utilities/helpers for reuse
* Flag/remove unused code only with user permission, document cleanup in commits
* Always prefer well-maintained, popular libraries over custom solutions; verify maintenance and popularity, suggest alternatives with trade-offs

### Configuration

* Read all config (API keys, endpoints, models) from `.env` only
* Never hardcode config values
* Validate presence at startup, fail fast if missing

### Testing

* Auto-generate tests for new/refactored code using `pytest` in `/tests`
* Avoid leaving TODOs or incomplete code; log deferred tasks only in Development log

### Development Log

* Maintain `supporting_documents/Development log.md` as changelog
* Group related changes under existing entries
* Reword or reorganize entries as needed
* Update it automatically on changes, no backups required
* Prioritize code writing before documentation updates

### Error Handling

* Use specific exceptions, avoid bare excepts
* Log errors to `/logs`
* Notify user if tasks cannot be fully completed or require input before proceeding

### Change Management

* Notify user before large or risky changes
* Prioritize bug fixes over new features
* Document cleanup and refactor actions in commit messages or PRs

### Interaction Style

* Provide concise answers
* Ask clarifying questions when needed
* Use neutral, factual tone; avoid phrases like "you're right" or "great question"

## Development Reminders

* **Unified Data Flow**: All sources must yield DataItem objects for consistent processing through the ingestion pipeline
* **Source-Specific Processing**: Use processor classes (LimitlessProcessor, etc.) for specialized data handling while maintaining unified storage
* **Calendar Integration**: Ensure all sources provide proper `days_date` extraction through `_extract_days_date` method
* **Deduplication Strategy**: News sources implement fetch-20-select-5 unique headlines; other sources don't require deduplication
* **Embedding Pipeline**: All DataItems stored in `data_items` table are automatically queued for embedding generation

## Data Source Architecture

### Source Processing Patterns

**Limitless Source**:
- Yields DataItem objects → LimitlessProcessor (deduplication, segmentation, cleanup) → data_items table
- Also stores in dedicated `limitless` table for specialized queries
- Full processor pipeline with markdown extraction and content enhancement

**News Source**:
- Fetches 20 headlines → selects 5 unique → yields DataItem objects → data_items table
- Also stores in `news` table for deduplication tracking
- Simple processing, no complex pipeline needed

**Weather Source**:
- API data → transforms to DataItem objects per forecast day → data_items table
- Also stores raw API response in `weather` table for caching
- No deduplication needed, minimal processing

**Twitter Source**:
- Archive import → yields DataItem objects → data_items table
- No deduplication needed, direct DataItem creation
- Simple processing with TwitterProcessor for metadata enhancement

## Claude Memories

The project will never be run on a mobile device.  only design for desktop and laptop

* Do not inspect or review supporting_documents directory unless directed to do so

* write test files only to /tests directory


## Frontend Architecture Verification Protocol

  BEFORE modifying ANY UI code:

  1. **PORT IDENTIFICATION**
     - localhost:3000 = Create React App
     - localhost:5173 = Vite
     - localhost:8080 = Vue CLI
     - localhost:4200 = Angular CLI

  2. **MANDATORY QUESTIONS**
     - "What port are you accessing?"
     - "Do you see a /frontend directory?"
     - "What's in your browser's Network tab?"
     - "Can you view page source?"

  3. **ARCHITECTURE VERIFICATION**
     - Check package.json in frontend dir
     - Identify framework (React/Vue/Angular)
     - Map UI components to actual files

  4. **CHANGE VERIFICATION**
     - Modify correct frontend files
     - Verify changes affect user's browser
     - Test in development server


NEVER VIOLATE: do not restore code unless requested.  Do not add code for items not requested by the user. Error on the side of caution.  Add code only required to meet the objective.

```
```