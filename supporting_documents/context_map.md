# 📊 Lifeboard Project Context Map

## 🏗️ Architecture Overview
**Type**: Full-stack AI-powered reflection platform  
**Backend**: FastAPI + SQLite + FAISS vector search  
**Frontend**: React + Vite + TypeScript + Tailwind CSS  
**Ports**: Backend (8000), Frontend (5173)  

## 🔧 Technology Stack

### Backend Core
- **Python 3.9.6** with FastAPI/Uvicorn
- **Database**: SQLite with unified data_items table
- **Vector Search**: FAISS + sentence-transformers
- **LLM**: Ollama (local) | OpenAI (cloud) 
- **Testing**: pytest with async support

### Frontend Core  
- **React 18.3** + TypeScript + Vite 5.4
- **UI**: Radix UI + Tailwind CSS + Lucide icons
- **State**: TanStack Query for server state
- **Rich Text**: React Quill editor
- **Charts**: Recharts visualization

## 📁 Key Directories
```
/api/routes/          → 15 API endpoints
/services/           → 12 core services  
/sources/            → 4 data sources (Limitless, News, Weather, Twitter)
/frontend/src/       → React components & hooks
/core/migrations/    → Database schema management
/tests/              → Comprehensive test suite (100+ files)
```

## 🔌 Data Sources & APIs
- **Limitless AI**: Lifelog data via API
- **News**: Real-time headlines (RapidAPI)  
- **Weather**: 5-day forecasts (RapidAPI)
- **Twitter**: Archive import + current data

## ⚡ Development Workflow
```bash
npm run dev:full     # Full stack (frontend + backend)
npm test            # Run pytest backend tests
cd frontend && npm run test  # Run Vitest frontend tests
```

## 🎯 Current State
- **Branch**: check_db_code (clean working tree)
- **Virtual Environment**: Active with all dependencies
- **Node Dependencies**: Installed with workspace setup
- **Configuration**: Environment-based with .env.example template

## 📦 Dependencies Summary

### Backend Dependencies (requirements.txt)
- **Core**: pydantic, alembic, python-dotenv, pytz
- **Database**: sqlite3 (built-in)
- **Vector/ML**: faiss-cpu, sentence-transformers, torch, numpy, scikit-learn
- **LLM**: openai, anthropic
- **Web**: fastapi, uvicorn, jinja2, httpx, aiohttp
- **Testing**: pytest, pytest-asyncio, faker

### Frontend Dependencies (package.json)
- **Core**: React 18.3, TypeScript 5.5, Vite 5.4
- **UI Library**: Radix UI components, Tailwind CSS
- **State Management**: TanStack Query
- **Forms**: React Hook Form, Zod validation
- **Rich Text**: React Quill
- **Testing**: Vitest, Testing Library
- **Build**: SWC compiler, ESLint

## 🗃️ Database Architecture

### Unified Data Flow
All sources → DataItem objects → processor pipeline → data_items table → FAISS embeddings

### Core Tables
- **data_items**: Unified storage for all data sources
- **data_sources**: Source management and metadata
- **chat_messages**: Chat history storage
- **user_documents**: User-created content with full-text search
- **limitless/news/weather/twitter**: Source-specific caching

### Migration System
- Alembic-based migrations in `/core/migrations/versions/`
- Bootstrap schema in `/core/migrations/bootstrap_schema.py`
- Latest migration: 0014_add_template_cache.py

## 🚀 Service Architecture

### Core Services
- **StartupService**: Application initialization and health checks
- **SyncManagerService**: Data source synchronization orchestration
- **ChatService**: LLM interaction and conversation management
- **DatabaseService**: SQLite operations with connection pooling
- **VectorStoreService**: FAISS similarity search and embedding management
- **EmbeddingService**: Text-to-vector conversion pipeline
- **IngestionService**: Data processing and storage orchestration

### Specialized Services
- **WeatherService**: Weather API integration and caching
- **NewsService**: News headline fetching with deduplication
- **TwitterAPIService**: Twitter data import and processing
- **DocumentService**: User document management with full-text search
- **TemplateProcessor**: Dynamic content template resolution

## 🔄 Data Processing Pipeline

### Ingestion Flow
1. **Source Detection**: Identify and register data sources
2. **Data Fetching**: Retrieve data from external APIs/files
3. **Processor Pipeline**: Apply source-specific processing (deduplication, segmentation)
4. **Unified Storage**: Store as DataItem objects in data_items table
5. **Embedding Generation**: Create vector embeddings for similarity search
6. **FAISS Indexing**: Add vectors to search index with ID mapping

### Search & Retrieval
1. **Query Embedding**: Convert search query to vector
2. **Similarity Search**: Find top matching vectors in FAISS
3. **Data Retrieval**: Fetch corresponding data_items records
4. **LLM Context**: Pass relevant data to language model
5. **Response Generation**: Generate contextual AI responses

## 🎨 Frontend Architecture

### Component Structure
- **Views**: CalendarView, ChatView, DocumentsView, SettingsView
- **UI Components**: Comprehensive Radix UI component library
- **Data Hooks**: Custom hooks for API interaction and state management
- **Layouts**: GridShell layout system with responsive design

### Development Setup
- **Vite Dev Server**: Port 5173 with hot reload
- **API Proxy**: Routes /api/* to backend on port 8000
- **Testing**: Vitest with jsdom environment
- **Linting**: ESLint with React hooks and TypeScript rules

## 🔧 Configuration Management

### Environment Variables
- **API Keys**: Limitless, RapidAPI, Twitter, OpenAI
- **Service URLs**: Base URLs and endpoints for external services
- **Feature Flags**: Enable/disable data sources and features
- **Performance**: Rate limiting, timeouts, batch sizes
- **Logging**: Log levels and file paths

### Pydantic Models
- Type-safe configuration with validation
- Environment variable parsing and defaults
- Startup validation with fail-fast behavior
- Factory pattern for configuration creation

## 📋 Testing Strategy

### Test Organization
- **Unit Tests**: Service and component isolation testing
- **Integration Tests**: Service interaction and API endpoint testing
- **E2E Tests**: Full-stack workflow validation
- **Performance Tests**: Load testing and optimization validation

### Test Coverage
- **Backend**: 100+ test files covering all services and APIs
- **Frontend**: Component tests with Testing Library and Vitest
- **Fixtures**: Comprehensive test data and mock services
- **Contracts**: Service interface validation testing