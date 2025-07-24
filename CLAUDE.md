# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Lifeboard is an interactive reflection space and AI-powered planning assistant that transforms daily digital history into a personal newspaper. It seamlessly integrates conversations, activities, moods, and experiences with AI assistance for discovery and planning.

Key features:
- Interactive reflection space with infinite discovery opportunities
- AI assistant for natural conversation and planning
- Digital history integration (conversations, activities, moods, experiences)
- Random resurfacing of forgotten moments and AI-guided discovery journeys
- Personal assistant functionality (to-dos, meeting insights, medical appointments)
- Open source implementation

## Architecture

The project follows a KISS (Keep It Simple, Stupid) multi-source memory chat application architecture with the following core components:

### Data Flow
- **Ingestion:** Fetch/store raw data in SQLite → Generate embedding → Add to FAISS with same ID
- **Search:** Embed query → Search FAISS → Get top-N vector IDs → Fetch corresponding SQLite rows → Pass full data into LLM
- **Updates:** Update SQLite row → Re-embed → Update FAISS vector

### Core Services
- **Database Service:** SQLite operations with namespaced ID management
- **Vector Store Service:** FAISS operations for similarity search
- **Embedding Service:** Text-to-vector conversion
- **Source Registry:** Auto-discovery and management of data sources
- **Namespace Prediction Service:** LLM-powered source relevance prediction
- **Search Service:** Main search orchestration combining all components

### Database Schema
```sql
-- System settings table for database-backed configuration
CREATE TABLE system_settings (key, value, updated_at)

-- Data sources registry for namespace management
CREATE TABLE data_sources (namespace, source_type, metadata, item_count, is_active)

-- Unified data storage with namespaced IDs
CREATE TABLE data_items (id, namespace, source_id, content, metadata, embedding_status)
```

### Namespaced ID System
All data items use namespaced IDs in the format `namespace:source_id` to maintain data isolation and enable efficient filtering during vector search operations.

## External Integrations

### Limitless API
The project integrates with Limitless AI's Pendant data API:
- **Base URL:** `https://api.limitless.ai/v1/`
- **Authentication:** X-API-Key header
- **Primary Endpoint:** `/lifelogs` for retrieving conversation and activity data
- **Data Format:** Structured lifelogs with markdown content, timestamps, and speaker identification

Key parameters for Limitless integration:
- Timezone-aware date filtering
- Pagination with cursor support
- Configurable content inclusion (markdown, headings)
- Speaker identification and conversation structure

## Development Approach

### Architectural Principles
- **Database-first settings:** Store runtime configuration in SQLite rather than environment files
- **Eager initialization:** Fail fast if components can't start properly
- **Dependency injection:** Pass dependencies to constructors for testability
- **Single responsibility:** Keep components focused on specific tasks
- **Interface-first design:** Define clear APIs between components
- **Configuration Management:** All configuration settings such as endpoints, api keys, llm models and others are read from .env and not from exports. There should be zero dependency on exports to the OS

### Implementation Strategy
The project follows a phased development approach:
1. Core foundation (database, vector store, embeddings)
2. Source abstraction and registry system
3. LLM integration and namespace prediction
4. Main application and API layer
5. Comprehensive testing and integration

### Testing Strategy
- **Unit tests:** Individual service testing with mocked dependencies for fast feedback
- **Integration tests:** Complete search flow testing with real API calls to validate end-to-end functionality
- **Mock tests:** Fast tests using mocked external services (LLM calls, Limitless API) for development velocity
- **Real API tests:** Integration tests that use actual external services with proper API keys and rate limiting
- **Performance tests:** Vector search and database operations under load
- **Hybrid approach:** Core business logic tested with mocks, critical paths validated with real APIs

Test organization:
- Use environment variables or test configuration to toggle between mock and real API modes
- Include both fast-running mocked test suite and slower integration test suite with real APIs
- Ensure real API tests can be skipped when API keys are not available

## Project Structure
```
/
├── supporting_documents/
│   ├── Overview/lifeboard_vision_statement.md
│   ├── Planning/Fresh Build Plan.md
│   └── limitless_api/limitless_api_documentation.md
├── LICENSE (MIT License)
└── README.md
```

The project is currently in planning phase with comprehensive documentation for a fresh implementation of the memory chat architecture.

## Development Practices

### Package Management
- Keep requirments.txt up to date

## Claude Guidelines

### Recommendation Approach
- Claude should always recommend an approach that:
  - Prioritizes simplicity and readability
  - Follows KISS (Keep It Simple, Stupid) principles
  - Emphasizes maintainability and clear design patterns
  - Considers performance and scalability
  - Provides clear, actionable recommendations

### Questioning Approach
- When asking questions of the user, add information for the decisions:
  - Include the impact on user experience for each potential decision
  - Provide insights into the performance implications of different choices
  - Help users understand the trade-offs and consequences of their decisions

## Memory Management Guidelines
- Updates to the development log are intentional and made by the human
- Purge cache of the development log and only read the file that exists and not any kind of memory or cache

## Development Guidelines
- For every plan, the plan must include a step to create and run tests