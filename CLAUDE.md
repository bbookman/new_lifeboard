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
- Ingest raw data → store in SQLite → generate embeddings → add to FAISS with same ID
- Search: embed query → search FAISS → retrieve top vector IDs → fetch SQLite rows → pass to LLM
- Updates: update SQLite row → re-embed → update FAISS vector

### Core Services
- Database Service: SQLite ops with namespaced ID management
- Vector Store Service: FAISS similarity search
- Embedding Service: text-to-vector conversion
- Source Registry: auto-discovery and data source management
- Namespace Prediction Service: LLM-powered source relevance prediction
- Search Service: orchestrates full search flow

### Database Schema
```sql
CREATE TABLE system_settings (key, value, updated_at);
CREATE TABLE data_sources (namespace, source_type, metadata, item_count, is_active);
CREATE TABLE data_items (id, namespace, source_id, content, metadata, embedding_status);
````

### Namespaced IDs

Format: `namespace:source_id` for data isolation and filtering.

## External Integrations

### Limitless API

* Base URL: `https://api.limitless.ai/v1/`
* Auth: X-API-Key header
* Endpoint: `/lifelogs`
* Features: timezone-aware filtering, pagination, structured markdown content, speaker IDs

## Development Approach

* Database-first settings in SQLite (no OS exports)
* Eager initialization and fail-fast
* Dependency injection for testability
* Single responsibility and interface-first design
* Config from `.env` only; validated on startup

## Testing

* Use `pytest`
* Store all tests under `/tests` at project root
* Write tests for all new or refactored code
* Toggle mock/real API modes via env variables
* Run unit, integration, mock, real API, and performance tests

## Project Structure

```
/
├── supporting_documents/
│   ├── Overview/lifeboard_vision_statement.md
│   ├── Planning/Fresh Build Plan.md
│   └── limitless_api/limitless_api_documentation.md
├── LICENSE
├── README.md
├── tests/
├── logs/
└── supporting_documents/Development log.md
```

## Logging

* All logs must go to `/logs` at project root
* Log all errors with specific exceptions; avoid bare excepts

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
* Use neutral, factual tone; avoid phrases like “you’re right” or “great question”

```
```
