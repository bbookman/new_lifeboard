# Development Guidelines & Patterns

## Core Development Principles  
- **KISS Approach**: Keep it simple, avoid over-engineering
- **DRY**: Don't repeat yourself, abstract common functionality
- **SOLID Principles**: Single responsibility, open/closed, etc.
- **Evidence-Based**: All claims verifiable through testing/documentation
- **Database-First Settings**: Store app state in database, not environment variables

## Data Architecture Patterns

### Unified Data Flow (Critical)
```
All sources → DataItem objects → processor pipeline → data_items table → embeddings → FAISS
```
- **Never bypass**: All sources must yield DataItem objects
- **Processor Pattern**: Use *_processor.py for specialized handling
- **Unified Storage**: Everything stored in data_items table
- **Calendar Integration**: All sources provide proper days_date extraction

### Source Implementation Pattern
```python
class ExampleSource(BaseSource):
    async def fetch_items(self, since: Optional[datetime] = None, limit: int = 100) -> AsyncIterator[DataItem]:
        # Implementation that yields DataItem objects
    
    def get_source_type(self) -> str:
        return "example"
    
    async def test_connection(self) -> bool:
        # Connection validation logic
```

### Processor Pattern
- **LimitlessProcessor**: Deduplication, segmentation, cleanup  
- **NewsProcessor**: Fetch-20-select-5 unique headlines
- **TwitterProcessor**: Metadata enhancement
- **WeatherProcessor**: API response transformation

## Configuration Management

### Pydantic Models (Required)
```python
# config/models.py
class ExampleConfig(BaseModel):
    api_key: str
    endpoint: str = "https://api.example.com"
    timeout: int = 30
```

### Factory Loading
```python
# config/factory.py  
from config.models import ExampleConfig

def load_config() -> AppConfig:
    # Centralized config loading with validation
```

## Testing Requirements

### Test Organization
- **Location**: All tests in `/tests` directory only
- **Naming**: Prefix with `test_`, descriptive names
- **Structure**: Mirror source structure in test organization
- **Async Support**: Use pytest-asyncio for async tests

### Test Categories (pytest markers)
- `@pytest.mark.unit`: Unit tests
- `@pytest.mark.integration`: Integration tests  
- `@pytest.mark.slow`: Long-running tests
- `@pytest.mark.async_integration`: Async integration tests

## Error Handling Standards

### Specific Exceptions
```python
# Good
try:
    result = await api_call()
except httpx.TimeoutError:
    logger.error("API timeout", extra={"endpoint": url})
except httpx.HTTPStatusError as e:
    logger.error("API error", extra={"status": e.response.status_code})

# Bad - avoid bare except
except:
    logger.error("Something went wrong")
```

### Logging Requirements
- **Location**: All logs to `/logs` directory
- **Context**: Include relevant context in log messages
- **Levels**: Use appropriate log levels (DEBUG, INFO, WARNING, ERROR)
- **Structured**: Use structured logging with extra parameters

## Frontend Development

### Component Architecture
- **shadcn/ui**: Use established design system components
- **TypeScript**: Strict typing for all components
- **React Query**: Server state management  
- **React Hook Form**: Form handling with validation

### Styling Approach
- **Tailwind CSS**: Utility-first styling
- **Design Tokens**: Consistent spacing, colors, typography
- **Responsive**: Desktop-first (never mobile - project requirement)
- **Dark Mode**: Support both light and dark themes

## Service Design Patterns

### Service Initialization
- **Eager Initialization**: Services initialized at startup
- **Fail Fast**: Application fails if required services unavailable
- **Dependency Injection**: Services designed for injection
- **Interface Segregation**: Clear service interfaces

### Background Tasks
- **Scheduler Service**: Centralized task scheduling
- **Sync Manager**: Coordinates data source synchronization
- **Startup Service**: Orchestrates application initialization

## Database Patterns

### Unified Data Access
```python
# All data through unified data_items table
data_item = DataItem(
    namespace="example",
    source_id="item_123", 
    content="Item content",
    metadata={"key": "value"},
    days_date="2024-01-01"
)
```

### Specialized Tables
- **Purpose**: Caching, deduplication, specialized queries
- **Pattern**: Store in both data_items AND specialized table
- **Examples**: `weather` for API caching, `news` for deduplication

## Performance Guidelines

### Embedding Pipeline
- **Automatic**: All DataItems automatically queued for embedding
- **FAISS Integration**: Vector search with same IDs as data_items  
- **Efficient**: Batch processing for embedding generation

### Caching Strategy  
- **API Responses**: Cache expensive API calls (weather, news)
- **Embeddings**: Persistent vector storage with FAISS
- **Configuration**: Database-based settings for cross-session persistence