# Codebase Structure

## Root Level
```
/
├── api/                 # FastAPI server and routes
├── config/             # Pydantic configuration models  
├── core/               # Database, embeddings, utilities
├── services/           # Business logic services
├── sources/            # Data source implementations
├── frontend/           # React TypeScript frontend
├── tests/              # Test suites (pytest config)
├── logs/               # Runtime logs (created by startup script)
├── supporting_documents/ # Project documentation
├── requirements.txt    # Python dependencies
├── package.json       # Node.js workspace config
├── start_full_stack.sh # Development server startup
└── CLAUDE.md          # Project guidance for Claude
```

## Core Architecture Components

### `/api` - FastAPI Server
- `server.py`: Main FastAPI application
- `routes/`: API endpoint definitions
  - `chat.py`: Chat interface endpoints
  - `data_items.py`: Unified data access
  - `sync.py`: Data synchronization
  - `health.py`, `system.py`: System status

### `/services` - Business Logic  
- `startup.py`: Application initialization
- `ingestion.py`: Data processing pipeline
- `chat_service.py`: LLM interaction
- `sync_manager_service.py`: Data source coordination
- `scheduler.py`: Background task management

### `/sources` - Data Integrations
- `base.py`: BaseSource ABC for all data sources
- `limitless.py`: Limitless API integration
- `news.py`: News API integration  
- `weather.py`: Weather API integration
- `twitter.py`: Twitter data integration
- `*_processor.py`: Data processing logic

### `/core` - Infrastructure
- `database.py`: SQLite database operations
- `embeddings.py`: Text-to-vector conversion
- `vector_store.py`: FAISS similarity search
- `unified_database.py`: Unified data access layer
- `migrations/`: Database schema migrations

### `/config` - Configuration Management
- `models.py`: Pydantic configuration models
- `factory.py`: Configuration loading and validation
- `validation.py`: Startup validation logic

### `/frontend` - React Frontend
```
frontend/
├── src/
│   ├── components/     # Reusable UI components
│   ├── pages/         # Route components  
│   ├── hooks/         # Custom React hooks
│   ├── lib/           # Utilities and helpers
│   └── types/         # TypeScript type definitions
├── public/            # Static assets
└── dist/             # Built assets (created by build)
```

### `/tests` - Test Organization
```
tests/
├── backend/           # Python service tests
├── frontend/          # Frontend component tests
├── api/              # API endpoint tests
├── fixtures/         # Test data and mocks
├── utilities/        # Test utilities
└── conftest.py       # pytest configuration
```

## Database Schema Structure
- `data_items`: Unified storage for all sources
- `data_sources`: Source metadata and status
- `chat_messages`: Chat history storage
- Source-specific tables: `weather`, `news`, `limitless` (for specialized queries)
- `system_settings`: Application configuration
- `migrations`: Schema version tracking

## Key Design Patterns
- **Unified Data Flow**: All sources → DataItem objects → data_items table
- **Namespace Isolation**: `namespace:source_id` format for data separation  
- **Processor Pipeline**: Specialized processing while maintaining unified storage
- **Configuration as Code**: Pydantic models with factory pattern
- **Service Injection**: Dependency injection for testability