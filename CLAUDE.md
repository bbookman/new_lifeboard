````markdown
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Lifeboard is an interactive reflection space and AI-powered planning assistant that transforms daily digital history into a personal newspaper. It integrates conversations, activities, moods, and experiences with AI assistance for discovery and planning.

Key features:
- Interactive reflection space with infinite discovery opportunities
- AI assistant for natural conversation and planning using OpenAI GPT or Ollama models
- Digital history integration (conversations, activities, moods, experiences)
- Random resurfacing of forgotten moments and AI-guided discovery journeys
- Personal assistant functionality (to-dos, meeting insights, medical appointments)
- Modern React + TypeScript frontend with Vite build system
- FastAPI backend with comprehensive data processing pipeline
- Vector search using FAISS for semantic similarity
- SQLite database with unified data storage architecture
- Open source implementation

Technology Stack:
- **Frontend**: React 18 + TypeScript + Vite + Tailwind CSS + Radix UI components
- **Backend**: Python 3.9+ + FastAPI + Uvicorn + Pydantic
- **Database**: SQLite with aiosqlite for async operations
- **Vector Search**: FAISS with sentence-transformers for embeddings
- **LLM Integration**: OpenAI API and Ollama for local models
- **External APIs**: Limitless, News API, Weather API, Twitter API
- **Testing**: pytest with comprehensive test coverage
- **Development Tools**: ESLint, TypeScript, Prettier, Vitest

## Architecture

The project follows a comprehensive full-stack architecture with modern Python backend and React frontend:

### Backend Architecture

**FastAPI Application with Advanced Orchestration:**
- **Server Management**: Complex server lifecycle with signal handling, graceful shutdown, and process management
- **Dependency Injection**: Centralized dependency registry system for service management
- **Orchestration**: FullStackOrchestrator for coordinated startup/shutdown of frontend and backend
- **Signal Handling**: Advanced signal management with custom handlers for SIGINT/SIGTERM
- **Process Management**: Automatic cleanup of existing processes and session lock management
- **Async Lifecycle**: Comprehensive async context manager with monitoring and diagnostics

### Data Flow Architecture

**Unified Data Pipeline:**
- All sources → DataItem objects → processor pipeline (if needed) → store in data_items table → generate embeddings → add to FAISS with same ID
- Search: embed query → search FAISS → retrieve top vector IDs → fetch data_items rows → pass to LLM
- Updates: update data_items row → re-embed → update FAISS vector

**Data Processing Patterns:**
- **Limitless Source**: DataItem objects → LimitlessProcessor (deduplication, segmentation, cleanup) → data_items table + limitless table
- **News Source**: Fetches 20 headlines → selects 5 unique → DataItem objects → data_items table + news table
- **Weather Source**: API data → DataItem objects per forecast day → data_items table + weather table
- **Twitter Source**: Archive import → DataItem objects → data_items table (no deduplication needed)

### Core Services Architecture

**Service Layer with Dependency Injection:**
- **Database Service**: SQLite operations with aiosqlite for async operations and namespaced ID management
- **Vector Store Service**: FAISS similarity search with index management and ID mapping
- **Embedding Service**: Text-to-vector conversion using sentence-transformers with configurable models
- **Ingestion Service**: Orchestrates data processing from multiple sources with error handling
- **Scheduler Service**: Background task management with configurable intervals and job timeouts
- **Sync Manager Service**: Handles synchronization of data from various sources with rate limiting
- **Chat Service**: Manages chat interactions and context with configurable history limits
- **Startup Service**: Orchestrates application initialization with comprehensive diagnostics
- **WebSocket Manager**: Real-time notifications and live updates with heartbeat monitoring
- **Session Lock Manager**: Prevents multiple server instances with proper cleanup
- **Port State Service**: Advanced port conflict detection and management

### Database Architecture

**SQLite Database**: The application uses SQLite with the main database file located at `lifeboard.db` in the project root. All database operations use aiosqlite for async compatibility.

**Database Schema**:
```sql
-- Core unified data storage for all sources
CREATE TABLE data_items (
    id TEXT PRIMARY KEY,                    -- Namespaced ID (namespace:source_id)
    namespace TEXT NOT NULL,                -- Data source namespace
    source_id TEXT NOT NULL,                -- Original source identifier
    content TEXT,                           -- Main content text
    metadata TEXT,                          -- JSON metadata for source-specific data
    embedding_status TEXT DEFAULT 'pending', -- pending, processing, completed, failed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    days_date TEXT NOT NULL                 -- Date in YYYY-MM-DD format for grouping
);

-- Data source management and tracking
CREATE TABLE data_sources (
    namespace TEXT PRIMARY KEY,             -- Unique namespace identifier
    source_type TEXT NOT NULL,              -- limitless, news, weather, twitter
    metadata TEXT,                          -- JSON configuration and stats
    item_count INTEGER DEFAULT 0,           -- Number of items from this source
    is_active BOOLEAN DEFAULT TRUE,         -- Whether source is enabled
    last_synced TIMESTAMP,                  -- Last successful sync timestamp
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Chat conversation history
CREATE TABLE chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_message TEXT NOT NULL,
    assistant_response TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    session_id TEXT,                        -- For grouping conversations
    metadata TEXT                           -- Additional context (JSON)
);

-- Specialized tables for source-specific queries and caching

-- Weather API response cache
CREATE TABLE weather (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    days_date TEXT NOT NULL,                -- Forecast date
    response_json TEXT NOT NULL,            -- Raw API response
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(days_date)                       -- One forecast per day
);

-- News headlines with deduplication tracking
CREATE TABLE news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    link TEXT,
    snippet TEXT,
    days_date TEXT NOT NULL,
    thumbnail_url TEXT,
    published_datetime_utc TEXT,
    source_hash TEXT,                       -- For deduplication
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Limitless lifelog data with enhanced processing
CREATE TABLE limitless (
    id TEXT PRIMARY KEY,                    -- Namespaced ID
    lifelog_id TEXT NOT NULL UNIQUE,        -- Original Limitless ID
    title TEXT,
    start_time TEXT,                        -- ISO format timestamp
    end_time TEXT,                          -- ISO format timestamp
    is_starred BOOLEAN DEFAULT FALSE,
    updated_at_api TEXT,                    -- Last API update timestamp
    processed_content TEXT,                 -- Enhanced content after processing
    raw_data TEXT,                          -- Original API response (JSON)
    days_date TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Application settings storage (database-first approach)
CREATE TABLE system_settings (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Database migration tracking
CREATE TABLE migrations (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Vector store metadata (for FAISS index management)
CREATE TABLE vector_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data_item_id TEXT NOT NULL,             -- References data_items.id
    vector_index INTEGER,                   -- Position in FAISS index
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (data_item_id) REFERENCES data_items(id) ON DELETE CASCADE
);
```

### Namespaced IDs

Format: `namespace:source_id` for data isolation and filtering.

## External Integrations

### LLM Providers

**OpenAI Integration:**
*   **Purpose:** Primary LLM provider for chat and AI assistance
*   **Models:** Configurable (default: gpt-3.5-turbo)
*   **Features:** Streaming responses, configurable temperature and max tokens
*   **Configuration:** API key required in `.env` as `OPENAI_API_KEY`
*   **Fallback:** Automatic fallback to Ollama if OpenAI unavailable

**Ollama Integration:**
*   **Purpose:** Local LLM provider for privacy and offline usage
*   **Default Model:** llama2 (configurable)
*   **Endpoint:** `http://localhost:11434` (configurable)
*   **Features:** Local inference, no API costs, configurable models
*   **Configuration:** No API key required, just local Ollama installation

### Data Source APIs

**Limitless API:**
*   **Purpose:** Primary source for lifelog data, including conversations and activities
*   **Base URL:** `https://api.limitless.ai/v1/`
*   **Auth:** `X-API-Key` header with bearer token
*   **Features:** Conversation history, activity logs, starred items
*   **Rate Limiting:** Built-in retry logic with exponential backoff

**News API:**
*   **Purpose:** Fetches real-time news headlines with deduplication
*   **Endpoint:** `real-time-news-data.p.rapidapi.com`
*   **Auth:** `X-RapidAPI-Key` header
*   **Features:** 20 headlines fetched, 5 unique selected daily
*   **Processing:** Content deduplication and metadata enhancement

**Weather API:**
*   **Purpose:** Retrieves 5-day weather forecasts
*   **Endpoint:** `easy-weather1.p.rapidapi.com/daily/5`
*   **Auth:** `X-RapidAPI-Key` header
*   **Features:** Daily forecasts, configurable location (latitude/longitude)
*   **Storage:** Raw API responses cached in weather table

**Twitter API:**
*   **Purpose:** Twitter archive import and live data fetching
*   **Auth:** Bearer token authentication
*   **Features:** Archive import, live tweet fetching (if configured)
*   **Processing:** TwitterProcessor for metadata enhancement
*   **Rate Limiting:** TwitterRateLimitService for API quota management

## Development Approach

**Configuration Management:**
*   **Pydantic Models:** All configuration managed through comprehensive Pydantic models in `config/models.py`
*   **Validation:** Extensive validation with custom validators for API keys, URLs, and data types
*   **Environment Variables:** `.env` files for local development with automatic loading
*   **Configuration Factory:** Centralized configuration creation via `config/factory.py`
*   **Validation Mixins:** BaseConfigMixin provides common validation patterns

**Architecture Patterns:**
*   **Dependency Injection:** Services use centralized dependency registry in `core/dependencies.py`
*   **Single Responsibility:** Each service and module has a clear, focused purpose
*   **Database-First Settings:** Application settings stored in database via `system_settings` table
*   **Eager Initialization:** Services initialized at startup with comprehensive diagnostics
*   **Async/Await:** Full async architecture using FastAPI and aiosqlite
*   **Signal Handling:** Advanced signal management with graceful shutdown orchestration

**Code Quality Standards:**
*   **Type Hints:** Comprehensive type annotations throughout the codebase
*   **Pydantic Models:** Data validation using Pydantic v2 with field validators
*   **Error Handling:** Specific exception types with proper logging and user feedback
*   **Documentation:** Industry-standard docstrings for all classes and functions
*   **SOLID Principles:** Applied throughout the architecture for maintainability

**Development Tools:**
*   **Frontend:** Vite dev server, TypeScript, ESLint, Tailwind CSS, Vitest
*   **Backend:** FastAPI, Uvicorn, pytest, Alembic (migrations)
*   **Code Quality:** Pre-commit hooks, linting, type checking
*   **Testing:** pytest with async support, test fixtures, coverage reporting
*   **Debugging:** Comprehensive logging, network diagnostics, debug services

## Testing

**Test Framework and Structure:**
*   **Framework:** `pytest` with async support via `pytest-asyncio`
*   **Location:** All tests in `/tests` directory with organized subdirectories
*   **Execution:** `PYTHONPATH=. python -m pytest` or `python -m pytest tests/`
*   **Configuration:** `pytest.ini` for test configuration and markers

**Test Organization:**
```
tests/
├── api/                          # API endpoint tests
├── backend/                      # Backend service tests
│   ├── e2e/                      # End-to-end tests
│   │   ├── full_stack/           # Full stack integration tests
│   │   └── user_workflows/       # User workflow tests
│   ├── integration/              # Service integration tests
│   │   ├── api_endpoints/        # API endpoint integration
│   │   ├── database/             # Database integration tests
│   │   └── service_interactions/ # Service interaction tests
│   └── unit/                     # Unit tests for individual components
├── contracts/                    # Contract tests
├── examples/                     # Example-based tests
├── fixtures/                     # Test fixtures and mock data
├── frontend/                     # Frontend component tests (Vitest)
├── media/                        # Media-related tests
└── utilities/                    # Test utility functions
```

**Test Categories:**
*   **Unit Tests:** Test individual functions, classes, and modules in isolation
*   **Integration Tests:** Test interactions between services and components
*   **E2E Tests:** Test complete user workflows from frontend to backend
*   **API Tests:** Test FastAPI endpoints with proper request/response validation
*   **Contract Tests:** Ensure API contracts are maintained between services

**Testing Tools:**
*   **faker:** Generate realistic test data
*   **pytest-asyncio:** Async test support
*   **Frontend:** Vitest + React Testing Library for component testing
*   **Coverage:** pytest-cov for test coverage reporting

**Test Execution Commands:**
*   `python -m pytest tests/` - Run all tests
*   `python -m pytest tests/backend/unit/` - Run unit tests only
*   `python -m pytest tests/api/` - Run API tests only
*   `python -m pytest -k "test_name"` - Run specific test
*   `python -m pytest --cov=services` - Run with coverage

**Test Standards:**
*   Test files prefixed with `test_` in `/tests` directory
*   Async tests use `pytest.mark.asyncio`
*   Fixtures defined in `tests/fixtures/` for reusable test data
*   Mock external dependencies for reliable testing
*   Test both success and failure scenarios

## Dependencies

### Python Backend Dependencies

**Core Framework:**
- `fastapi>=0.104.0` - Modern async web framework
- `uvicorn>=0.24.0` - ASGI server for FastAPI
- `pydantic>=2.0.0` - Data validation and serialization

**Database and Vector Search:**
- `aiosqlite>=0.19.0` - Async SQLite database operations
- `faiss-cpu>=1.7.0` - Vector similarity search
- `sentence-transformers>=2.6.0` - Text embeddings
- `numpy>=1.24.0`, `scikit-learn>=1.3.0` - Numerical computing

**LLM Integration:**
- `openai>=1.0.0` - OpenAI API client
- `anthropic>=0.25.0` - Anthropic API client (future use)

**HTTP and Async:**
- `httpx>=0.24.0` - Async HTTP client
- `aiohttp>=3.8.0` - Additional async HTTP support

**Configuration and Utilities:**
- `python-dotenv>=1.0.0` - Environment variable loading
- `alembic>=1.11.1` - Database migrations
- `pytz>=2023.3` - Timezone handling

**Testing and Development:**
- `pytest>=7.0.0` - Testing framework
- `pytest-asyncio>=0.21.0` - Async test support
- `faker` - Test data generation

### Frontend Dependencies

**Core Framework:**
- `react>=18.3.1` - React framework
- `react-dom>=18.3.1` - React DOM rendering
- `@types/react>=18.3.3` - React TypeScript definitions

**Build Tools:**
- `vite>=5.4.1` - Fast build tool and dev server
- `@vitejs/plugin-react-swc>=3.5.0` - React plugin for Vite

**UI Components and Styling:**
- `@radix-ui/*` - Headless UI components (accordion, dialog, dropdown, etc.)
- `tailwindcss>=3.4.11` - Utility-first CSS framework
- `lucide-react>=0.462.0` - Icon library
- `class-variance-authority>=0.7.1` - Component variant utilities

**State Management and Data:**
- `@tanstack/react-query>=5.56.2` - Data fetching and caching
- `react-hook-form>=7.53.0` - Form state management
- `zod>=3.23.8` - Schema validation

**Development Tools:**
- `typescript>=5.5.3` - TypeScript compiler
- `@types/node>=22.5.5` - Node.js TypeScript definitions
- `eslint>=9.9.0` - Code linting
- `vitest>=3.2.4` - Testing framework
- `@testing-library/react>=16.3.0` - React testing utilities

### Development Scripts

**Package.json Scripts:**
- `npm run dev` - Start Vite dev server on port 5173
- `npm run build` - Build for production
- `npm run preview` - Preview production build
- `npm run test` - Run Vitest tests
- `npm run lint` - Run ESLint

**Python Commands:**
- `python3 -m pytest tests/` - Run all tests
- `python3 -m uvicorn api.server:app --reload` - Start backend dev server
- `PYTHONPATH=. python3 -m pytest tests/backend/unit/` - Run unit tests

## Project Structure

```
/
├── .env                              # Environment variables (created from .env.example)
├── .env.example                      # Environment variables template
├── .kilocodemodes                    # Kilo Code mode configurations
├── lifeboard.db                      # SQLite database file
├── Gemini.md                         # Additional AI assistant guidelines
├── CLAUDE.md                         # This file - Claude Code guidelines
├── README.md                         # Project documentation
├── LICENSE                           # MIT License
├── requirements.txt                  # Python dependencies
├── package.json                      # Node.js project configuration
├── package-lock.json                 # Node.js lockfile
├── pytest.ini                        # pytest configuration
├── start_full_stack.sh               # Full stack startup script
├── install_project.sh                # Project installation script
├── reset.sh                          # Database reset script
├── api/                              # FastAPI backend
│   ├── server.py                     # Main FastAPI application with orchestration
│   ├── server_deprecated.py          # Legacy server (deprecated)
│   └── routes/                       # API route modules
│       ├── __init__.py
│       ├── calendar.py               # Calendar/date-based endpoints
│       ├── chat.py                   # Chat and LLM endpoints
│       ├── clean_up_crew.py          # Data cleanup endpoints
│       ├── data_items.py             # Data item CRUD operations
│       ├── documents.py              # User documents management
│       ├── embeddings.py             # Vector embedding operations
│       ├── health.py                 # Health check endpoints
│       ├── headings.py               # Document headings
│       ├── llm.py                    # LLM provider endpoints
│       ├── news.py                   # News data endpoints
│       ├── semantic_patterns.py      # Semantic search patterns
│       ├── settings.py               # Application settings
│       ├── sources.py                # Data source management
│       ├── sync_status.py            # Synchronization status
│       ├── sync.py                   # Data synchronization
│       ├── system.py                 # System management
│       ├── weather.py                # Weather data endpoints
│       └── websocket.py              # WebSocket connections
├── config/                           # Configuration management
│   ├── __init__.py
│   ├── factory.py                    # Configuration factory
│   ├── models.py                     # Pydantic configuration models
│   ├── startup_validation.py         # Startup validation logic
│   └── validation.py                 # Configuration validation
├── core/                             # Core system components
│   ├── migrations/                   # Database migrations
│   │   └── versions/                 # Migration version files
│   ├── dependencies.py               # Dependency injection registry
│   ├── logging_config.py             # Centralized logging configuration
│   ├── signal_handler.py             # Signal handling utilities
│   ├── frontend_orchestrator.py      # Frontend process management
│   └── orchestration.py              # Full stack orchestration
├── frontend/                         # React + TypeScript frontend
│   ├── public/                       # Static assets
│   ├── src/                          # Source code
│   │   ├── assets/                   # Static assets
│   │   ├── components/               # React components
│   │   │   ├── __tests__/            # Component tests
│   │   │   ├── layout/               # Layout components
│   │   │   └── ui/                   # UI components (Radix-based)
│   │   ├── hooks/                    # Custom React hooks
│   │   │   └── __tests__/            # Hook tests
│   │   ├── pages/                    # Page components
│   │   ├── providers/                # React context providers
│   │   ├── test/                     # Test utilities
│   │   ├── App.tsx                   # Main application component
│   │   ├── main.tsx                  # Application entry point
│   │   └── index.css                 # Global styles
│   ├── components.json               # shadcn/ui configuration
│   ├── eslint.config.js              # ESLint configuration
│   ├── index.html                    # HTML template
│   ├── package.json                  # Frontend dependencies
│   ├── package-lock.json             # Frontend lockfile
│   ├── tailwind.config.ts            # Tailwind CSS configuration
│   ├── tsconfig.app.json             # TypeScript app config
│   ├── tsconfig.json                 # TypeScript configuration
│   ├── tsconfig.node.json            # TypeScript Node config
│   ├── vite.config.ts                # Vite configuration
│   └── README.md                     # Frontend documentation
├── llm/                              # LLM integration
│   └── [LLM provider modules]
├── services/                         # Business logic services
│   ├── __init__.py
│   ├── chat_service.py               # Chat functionality
│   ├── clean_up_crew_service.py      # Data cleanup operations
│   ├── debug_mixin.py                # Debugging utilities
│   ├── document_service.py           # Document management
│   ├── example_debug_service.py      # Debug service example
│   ├── ingestion.py                  # Data ingestion pipeline
│   ├── llm_service.py                # LLM service integration
│   ├── monitor.py                    # System monitoring
│   ├── network_diagnostics.py        # Network diagnostics
│   ├── network_recovery.py           # Network recovery utilities
│   ├── news_service.py               # News data service
│   ├── port_state_service.py         # Port management
│   ├── scheduler.py                  # Background task scheduling
│   ├── semantic_deduplication_service.py # Content deduplication
│   ├── session_lock_manager.py       # Session management
│   ├── startup_integration.py        # Startup integration
│   ├── startup.py                    # Application startup
│   ├── sync_manager_service.py       # Data synchronization
│   ├── sync_status_service.py        # Sync status tracking
│   ├── template_processor.py         # Template processing
│   ├── twitter_api_service.py        # Twitter API integration
│   ├── twitter_rate_limit_service.py # Twitter rate limiting
│   ├── weather_service.py            # Weather data service
│   └── websocket_manager.py          # WebSocket management
├── sources/                          # Data source integrations
│   ├── __init__.py
│   ├── base.py                       # Base source class
│   ├── limitless_processor.py        # Limitless data processing
│   ├── limitless.py                  # Limitless API integration
│   ├── news.py                       # News API integration
│   ├── semantic_deduplication_processor.py # Content deduplication
│   ├── sync_manager.py               # Source synchronization
│   ├── twitter_processor.py          # Twitter data processing
│   ├── twitter.py                    # Twitter API integration
│   └── weather.py                    # Weather API integration
├── tests/                            # Test suite
│   ├── __init__.py
│   ├── api/                          # API endpoint tests
│   ├── backend/                      # Backend service tests
│   │   ├── e2e/                      # End-to-end tests
│   │   ├── integration/              # Integration tests
│   │   └── unit/                     # Unit tests
│   ├── contracts/                    # Contract tests
│   ├── examples/                     # Example tests
│   ├── fixtures/                     # Test fixtures
│   ├── frontend/                     # Frontend tests
│   ├── media/                        # Media-related tests
│   └── utilities/                    # Test utilities
├── tools/                            # Development and utility tools
│   ├── cli_network_diagnostics.py    # Network diagnostics CLI
│   ├── install-mcp-servers.sh        # MCP server installation
│   └── setup_venv.sh                 # Virtual environment setup
├── logs/                             # Application logs directory
├── supporting_documents/             # Documentation and specifications
│   ├── async_refactor.md             # Async refactoring documentation
│   ├── template_system.md            # Template system documentation
│   ├── Testing_Standards.md          # Testing standards
│   ├── limitless_api/                # Limitless API documentation
│   └── Archive/                      # Archived documentation
├── .claude/                          # Claude-specific configurations
├── .vscode/                          # VS Code workspace settings
└── .gitignore                        # Git ignore patterns
```

## Logging

*   **Centralized Configuration:** Logging is configured centrally in `core/logging_config.py` using the `setup_application_logging` function.
*   **Log Directory:** All logs are written to the `/logs` directory at the project root.
*   **Error Handling:** All errors should be logged with specific exceptions. Avoid bare `except` clauses.

## Claude Guidelines

### Primary Role and Scope

**Claude Code's primary responsibilities:**
* Write new code following established patterns in the codebase
* Refactor existing code while maintaining functionality
* Explain existing code and architecture decisions
* Access and modify all codebase parts without restrictions
* Follow the project's coding standards and architectural patterns

### Coding Standards and Patterns

**Language and Framework Usage:**
* **Python Backend:** Use FastAPI, Pydantic v2, async/await patterns
* **Frontend:** Use React + TypeScript + Vite + Tailwind CSS + Radix UI
* **Database:** Use aiosqlite for async database operations
* **Type Hints:** Required on all functions, methods, and classes
* **Naming:** snake_case for Python, camelCase for TypeScript/JavaScript
* **Documentation:** Industry-standard docstrings for all Python functions/classes

**Code Quality Principles:**
* **TDD (Test-Driven Development):** Write tests before implementing code
* **KISS:** Keep implementations simple and straightforward
* **DRY:** Eliminate code duplication through reusable functions/utilities
* **SOLID:** Follow single responsibility, open/closed, and dependency inversion principles
* **YAGNI:** Implement only what is explicitly requested
* **Type Safety:** Use comprehensive type hints and Pydantic validation

**Test-Driven Development (TDD) Standards:**

**CRITICAL: TDD is the mandatory development approach for this project.**

**TDD Workflow:**
1. **RED:** Write a failing test first that defines the desired behavior
2. **GREEN:** Write the minimal code to make the test pass
3. **REFACTOR:** Clean up the code while ensuring tests still pass

**TDD Implementation Rules:**
* **Never write production code without a failing test**
* **Write tests for all new features and bug fixes**
* **Run tests frequently during development**
* **Use descriptive test names that explain the behavior being tested**
* **Test both happy path and error scenarios**
* **Mock external dependencies to isolate unit tests**

**Test Categories and Locations:**
* **Unit Tests:** `/tests/backend/unit/` - Test individual functions/classes
* **Integration Tests:** `/tests/backend/integration/` - Test service interactions
* **API Tests:** `/tests/api/` - Test FastAPI endpoints
* **E2E Tests:** `/tests/backend/e2e/` - Test complete user workflows
* **Frontend Tests:** `/tests/frontend/` - Test React components with Vitest

**Test File Naming Convention:**
* Unit tests: `test_unit_[component].py`
* Integration tests: `test_integration_[service].py`
* API tests: `test_api_[endpoint].py`
* E2E tests: `test_e2e_[workflow].py`

**Current Codebase Patterns:**
* **Service Layer:** Business logic in `/services` with dependency injection
* **Data Sources:** Source-specific processing in `/sources` with base class inheritance
* **API Routes:** Modular FastAPI routes in `/api/routes` with dependency injection
* **Configuration:** Pydantic models in `/config` with validation mixins
* **Database Operations:** Async operations using aiosqlite with connection pooling
* **Error Handling:** Specific exception types with proper logging and user feedback

### Configuration Management

**Environment Variables:**
* All configuration read from `.env` file using python-dotenv
* API keys, endpoints, and sensitive data stored in environment variables
* Configuration validated at startup with clear error messages
* Never hardcode configuration values in source code

**Pydantic Configuration:**
* Use comprehensive Pydantic models with field validators
* Implement BaseConfigMixin for common validation patterns
* Validate API keys, URLs, and data types at model instantiation
* Fail fast on configuration errors with descriptive messages

### Testing Requirements - TDD MANDATORY

**CRITICAL: Test-Driven Development (TDD) is the mandatory development approach for this project.**

**TDD Workflow:**
1. **RED:** Write a failing test first that defines the desired behavior
2. **GREEN:** Write the minimal code to make the test pass
3. **REFACTOR:** Clean up the code while ensuring tests still pass

**TDD Implementation Rules:**
* **Never write production code without a failing test**
* **Write tests for all new features and bug fixes**
* **Run tests frequently during development**
* **Use descriptive test names that explain the behavior being tested**
* **Test both happy path and error scenarios**
* **Mock external dependencies to isolate unit tests**

**Test Structure:**
* All tests located in `/tests` directory with organized subdirectories
* Unit tests for individual components in `tests/backend/unit/`
* Integration tests for service interactions in `tests/backend/integration/`
* API endpoint tests in `tests/api/`
* E2E tests for complete workflows in `tests/backend/e2e/`

**Test Execution:**
* Run tests using: `PYTHONPATH=. python -m pytest tests/`
* Use `pytest-asyncio` for async test functions
* Generate realistic test data using `faker` library
* Mock external dependencies for reliable testing

**Test Standards:**
* Test files prefixed with `test_` in appropriate subdirectories
* Test both success and failure scenarios
* Use fixtures for reusable test data and setup
* Maintain test coverage for critical functionality

### Error Handling and Logging

**Error Handling Patterns:**
* Use specific exception types, never bare `except` clauses
* Log all errors to `/logs` directory with appropriate log levels
* Provide user-friendly error messages through API responses
* Implement graceful degradation for non-critical failures

**Logging Configuration:**
* Centralized logging setup in `core/logging_config.py`
* Structured logging with correlation IDs for request tracing
* Different log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
* Log rotation and file size management

### Change Management Protocol

**Before Making Changes:**
* Notify user before large or risky modifications
* Explain the scope and impact of proposed changes
* Ask for confirmation on significant architectural changes
* Document cleanup and refactoring actions in commit messages

**Implementation Priority:**
* Prioritize bug fixes and stability improvements
* Implement new features only when explicitly requested
* Maintain backward compatibility unless explicitly stated otherwise
* Follow existing patterns and architectural decisions

### Interaction Style and Communication

**Response Style:**
* Provide concise, factual answers without unnecessary commentary
* Use technical, precise language appropriate for software development
* Avoid conversational phrases like "you're right" or "great question"
* Focus on actionable information and clear explanations

**Question Asking:**
* Ask clarifying questions when requirements are ambiguous
* Provide specific suggestions with concrete examples
* Use structured formats (bullet points, numbered lists) for complex information
* Reference specific files, functions, or patterns when relevant

### Critical: Implementation vs Documentation Distinction

**CRITICAL DECISION FRAMEWORK:**

**Documentation Tasks (DEFAULT BEHAVIOR):**
* Keywords: "document", "add to document", "update document", "reorganize", "record", "plan", "analyze", "explain", "describe"
* Actions: ONLY update/create documentation files
* Restrictions: DO NOT implement code changes unless explicitly requested

**Implementation Tasks (REQUIRES EXPLICIT REQUEST):**
* Keywords: "implement", "fix", "build", "create code", "write function", "add feature", "develop", "code"
* Actions: Write/modify actual source code
* Requirements: Must be explicitly requested with implementation keywords

**Decision Protocol:**
1. **Analyze Request:** Identify primary intent using keyword analysis
2. **If Ambiguous:** Ask user to clarify: "Should I implement these changes or just document them?"
3. **Default Behavior:** When in doubt, default to documentation-only
4. **Explicit Confirmation:** Never implement code without clear implementation keywords

**Prohibited Actions:**
* NEVER implement code changes for documentation requests
* NEVER add code for items not explicitly requested by the user
* NEVER assume implementation intent from ambiguous language
* ALWAYS err on the side of caution and ask for clarification

**Examples:**
* ✅ "Document the startup process" → Update documentation only
* ✅ "Implement user authentication" → Write authentication code
* ❓ "Fix the login issue" → Ask: "Should I implement the fix or document the solution?"
* ✅ "Add error handling to the API" → Implement error handling code

## Development Tools and Utilities

### Tools Directory (`/tools`)

**Development Utilities:**
* `cli_network_diagnostics.py` - Network connectivity and diagnostics CLI tool
* `install-mcp-servers.sh` - Installation script for MCP (Model Context Protocol) servers
* `setup_venv.sh` - Virtual environment setup and configuration script

**Utility Scripts:**
* `install_project.sh` - Complete project installation and setup
* `start_full_stack.sh` - Full-stack application startup script
* `reset.sh` - Database reset and cleanup script

### Project-Specific Files

**Configuration Files:**
* `.kilocodemodes` - Kilo Code mode configurations for different development workflows
* `Gemini.md` - Additional AI assistant guidelines (complements this CLAUDE.md)
* `.env` - Environment variables (created from `.env.example`)
* `.env.example` - Template for environment variable configuration

**Development Configuration:**
* `pytest.ini` - pytest configuration and test settings
* `package.json` - Node.js project configuration and scripts
* `requirements.txt` - Python dependencies specification

## Development Reminders

**Data Processing Patterns:**
* **Unified Data Flow**: All sources yield DataItem objects for consistent processing
* **Source-Specific Processing**: Use processor classes for specialized data handling
* **Calendar Integration**: All sources provide `days_date` extraction for date-based grouping
* **Deduplication Strategy**: News sources implement fetch-20-select-5 pattern
* **Embedding Pipeline**: DataItems automatically queued for vector embedding generation

**Database Operations:**
* Use aiosqlite for all async database operations
* Implement proper connection pooling and transaction management
* Store application settings in `system_settings` table (database-first approach)
* Use namespaced IDs (`namespace:source_id`) for data isolation

**Code Quality Standards:**
* Follow KISS, DRY, SOLID, and YAGNI principles
* Use comprehensive type hints and Pydantic validation
* Write industry-standard docstrings for all functions and classes
* Implement proper error handling with specific exception types
* Use centralized logging with appropriate log levels

## Frontend Architecture Verification Protocol

**CRITICAL: Before modifying ANY frontend code:**

### Step 1: Environment Verification
**Port Identification:**
- `localhost:5173` = Vite React development server (current setup)
- `localhost:3000` = Create React App (legacy/alternative)
- `localhost:8080` = Vue CLI
- `localhost:4200` = Angular CLI

**Mandatory Pre-Check Questions:**
1. "What port is the frontend development server running on?"
2. "Can you confirm the `/frontend` directory exists and contains source code?"
3. "What's visible in the browser's Network tab for the frontend?"
4. "Can you access the page source and see the expected HTML structure?"

### Step 2: Architecture Verification
**Framework Confirmation:**
- Verify `frontend/package.json` contains React and Vite dependencies
- Confirm TypeScript configuration in `frontend/tsconfig.json`
- Check Tailwind CSS setup in `frontend/tailwind.config.ts`
- Validate Radix UI components in dependencies

**File Structure Mapping:**
- React components located in `frontend/src/components/`
- Page components in `frontend/src/pages/`
- Custom hooks in `frontend/src/hooks/`
- UI components in `frontend/src/components/ui/` (Radix-based)

### Step 3: Development Workflow
**Change Implementation:**
- Modify files in the correct `frontend/src/` subdirectories
- Use Vite dev server for hot reloading during development
- Test changes in browser at `localhost:5173`
- Verify component re-rendering and state updates

**Build Process:**
- Development: `npm run dev` (Vite dev server)
- Production: `npm run build` (Vite build process)
- Type checking: TypeScript compilation
- Linting: ESLint for code quality

## Critical Project Constraints

**Python Version Requirement:**
- Project uses Python 3.9+ exclusively
- NEVER execute commands with `python` - always use `python3`
- All scripts and commands must specify `python3` explicitly

**Platform Limitations:**
- Application designed exclusively for desktop and laptop environments
- No mobile device support or responsive design requirements
- Desktop-first UI/UX approach

**Progress Monitoring Integration:**
- Calendar view contains progress monitor UI
- When new data sources are added, update progress calculation logic
- Modify completeness percentage calculations in calendar components
- Update data source status indicators in the UI

**Database Persistence:**
- SQLite database file `lifeboard.db` created in project root
- Contains all application data and vector embeddings
- Implement proper backup strategies for production use
- Use database transactions for data consistency

## Implementation Restrictions

**CRITICAL: Code Modification Policy**
- **TDD REQUIREMENT:** All code changes MUST follow Test-Driven Development (RED → GREEN → REFACTOR)
- NEVER write production code without first writing a failing test
- NEVER restore or modify code unless explicitly requested by user
- NEVER add code for features not specifically requested
- Error on the side of caution - ask before implementing
- Only implement what is required to meet the stated objective

**Documentation vs Implementation:**
- Distinguish clearly between documentation and implementation tasks
- Default to documentation-only unless implementation is explicitly requested
- Ask for clarification when intent is ambiguous
- Never implement code changes for documentation requests


```
```