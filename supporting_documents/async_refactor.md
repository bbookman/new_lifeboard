# DatabaseService Async Refactoring Plan

## Progress Tracking
The following will be updated after each phase

**Phase 0:** ✅ COMPLETED (2025-08-31)
**Phase 1:** ✅ COMPLETED (2025-08-31)
- Core CRUD operations: `async_store_data_item`, `async_get_data_items_by_ids`
- Query operations: `async_get_data_items_by_namespace`, `async_get_data_items_by_date_range`, `async_get_data_items_by_date`, `async_get_available_dates`, `async_get_days_with_data`, `async_get_all_namespaces`
- Settings & metadata: `async_get_setting`, `async_set_setting`, `async_register_data_source`, `async_get_active_namespaces`, `async_update_source_item_count`, `async_get_database_stats`
- Chat operations: `async_store_chat_message`, `async_get_chat_history`
- Embedding operations: `async_update_embedding_status`, `async_update_ingestion_status`, `async_get_pending_embeddings`
- Transaction support: Enhanced `async_transaction` context manager with proper rollback
- Test coverage: 29 async tests with 100% coverage of new async methods
- Performance validation: Async operations tested and validated
**Phase 2:** ✅ COMPLETED (2025-09-01)
**Phase 3:** PENDING
**Phase 4:** PENDING
**Phase 5:** PENDING
**Phase 6:** PENDING


## Executive Summary
Convert the synchronous DatabaseService to async using aiosqlite to align with the application's async architecture. This TDD-based plan covers ~66 self.database calls and ~210 total database calls across the codebase, ensuring proper async/await patterns throughout.

## Architecture Analysis

### Current State Assessment
- **Database Layer**: Synchronous SQLite operations using `sqlite3` with ~30 DatabaseService methods
- **Application Layer**: Fully async (FastAPI routes, services, sources)
- **Problem**: Blocking I/O operations in async contexts hurt performance
- **Impact**: ~66 self.database calls, ~210 total database calls across multiple files
- **Existing Async Wrappers**: `fetch_one` and `execute_query` methods already exist in DatabaseService (lines 555-582) - **CRITICAL: These are fake async methods that use synchronous operations**

### Target Architecture
- **Database Layer**: Async SQLite operations using `aiosqlite`
- **Connection Management**: Async context managers with proper connection lifecycle
- **Transaction Handling**: Async transaction patterns with rollback capabilities
- **Error Handling**: Async-specific error propagation and recovery
- **All Operations**: Non-blocking I/O with proper async/await patterns
- **Performance**: Improved concurrency with concrete benchmarks and monitoring

## TDD Implementation Strategy

### Core TDD Principles
1. **Red-Green-Refactor Cycle**: Every change starts with a failing test
2. **Test Coverage**: 100% coverage for all converted methods
3. **Regression Prevention**: All existing tests must pass with async changes
4. **Performance Validation**: Concrete benchmarking with measurable targets
5. **Async Safety**: Ensure no blocking operations in async contexts

### Test Categories
```python
# Unit Tests: Individual method conversion
@pytest.mark.asyncio
async def test_async_store_data_item(async_database):
    # RED: Write failing test first
    # GREEN: Implement async method
    # REFACTOR: Optimize for performance

# Integration Tests: Service layer updates
@pytest.mark.asyncio
async def test_async_service_database_interaction(async_service):
    # Test service + async database integration

# E2E Tests: Full application async flow
@pytest.mark.asyncio
async def test_async_api_endpoint_database_flow(async_client):
    # Test FastAPI + async database end-to-end
```

## Implementation Roadmap (25 Days)

### Phase 0: Critical Foundation & Setup (Days 1-2)  ✅
**CRITICAL: Address fundamental issues before any implementation**

#### Day 1: Fix Fake Async Methods & Dependencies  ✅
**🚨 CRITICAL TASKS - Must be completed first:**

1. **Fix Fake Async Methods**
   ```python
   # CRITICAL: Convert existing fake async methods to real async
   async def fetch_one(self, query: str, params: tuple = None) -> Optional[Dict[str, Any]]:
       """Convert from fake async to real async with aiosqlite"""
       async with aiosqlite.connect(self.db_path) as conn:
           conn.row_factory = aiosqlite.Row
           async with conn.execute(query, params or ()) as cursor:
               row = await cursor.fetchone()
               return dict(row) if row else None

   async def execute_query(self, query: str, params: tuple = None) -> None:
       """Convert from fake async to real async with aiosqlite"""
       async with aiosqlite.connect(self.db_path) as conn:
           await conn.execute(query, params or ())
           await conn.commit()
   ```

2. **Add aiosqlite dependency**
   ```
   # requirements.txt
   aiosqlite>=0.19.0
   # Note: pytest-asyncio>=0.21.0 already exists
   ```

3. **Update pytest.ini for async support**
   ```ini
   [tool:pytest]
   asyncio_mode = auto
   asyncio_default_fixture_loop_scope = function
   markers =
       asyncio: marks tests as async tests
       async_integration: marks tests as async integration tests
       async_performance: marks tests as async performance tests
   ```

#### Day 2: Technical Specifications & Planning  ✅
**CRITICAL: Define missing technical details**

1. **Async Transaction Handling Patterns**
   ```python
   @asynccontextmanager
   async def transaction(self):
       """Async transaction context manager with rollback support"""
       async with aiosqlite.connect(self.db_path) as conn:
           try:
               yield conn
               await conn.commit()
           except Exception:
               await conn.rollback()
               raise
   ```

2. **Connection Lifecycle Management**
   ```python
   class AsyncDatabaseService:
       def __init__(self, db_path: str = "lifeboard.db"):
           self.db_path = db_path
           self._connection_pool = None  # Future enhancement

       async def initialize(self):
           """Async initialization with migration support"""
           await self._init_database()
           await self._validate_schema()

       @asynccontextmanager
       async def get_connection(self):
           """Async context manager with proper cleanup"""
           async with aiosqlite.connect(self.db_path) as conn:
               conn.row_factory = aiosqlite.Row
               try:
                   yield conn
               finally:
                   # Ensure connection is properly closed
                   pass
   ```

3. **Error Handling Patterns**
   ```python
   async def _handle_async_errors(self, operation: str):
       """Async-specific error handling with proper propagation"""
       try:
           # Operation logic
           pass
       except aiosqlite.OperationalError as e:
           logger.error(f"Database operation error in {operation}: {e}")
           raise DatabaseOperationError(f"Failed {operation}") from e
       except asyncio.TimeoutError as e:
           logger.error(f"Timeout in {operation}: {e}")
           raise DatabaseTimeoutError(f"Timeout in {operation}") from e
   ```

4. **Performance Benchmark Baselines**
   - Establish current sync performance metrics
   - Define async performance targets (< 5% degradation)
   - Set up monitoring for concurrent operations

### Phase 1: Core DatabaseService Conversion (Days 3-7)

#### Day 3: Core CRUD Operations
**TDD Cycle for each method:**

1. **store_data_item conversion**
   ```python
   # RED: Write failing test
   @pytest.mark.asyncio
   async def test_async_store_data_item(async_database):
       data_item = create_test_data_item()
       await async_database.store_data_item(**data_item)  # Will fail

   # GREEN: Implement async method
   async def store_data_item(self, id: str, namespace: str, ...):
       async with self.get_connection() as conn:
           await conn.execute("""INSERT OR REPLACE...""", params)
           await conn.commit()
   ```

2. **get_data_items_by_ids conversion**
   ```python
   # RED: Test batch fetching
   @pytest.mark.asyncio
   async def test_async_get_data_items_by_ids():
       ids = ["test:1", "test:2"]
       results = await async_database.get_data_items_by_ids(ids)
       assert len(results) == 2
   ```

3. **Convert all 30+ database methods** following same TDD pattern

#### Day 4: Query Operations
**Methods to convert:**
- `get_data_items_by_namespace`
- `get_data_items_by_date`
- `get_data_items_by_date_range`
- `get_days_with_data`
- `get_available_dates`
- `get_all_namespaces`

#### Day 5: Settings & Metadata Operations
**Methods to convert:**
- `get_setting` / `set_setting`
- `register_data_source`
- `update_source_item_count`
- `get_database_stats`
- `store_chat_message`
- `get_chat_history`

#### Day 6: Transaction & Error Handling
**CRITICAL: Implement proper async transaction support**
- Add transaction context managers
- Implement rollback procedures
- Add async-specific error handling
- Test concurrent transaction scenarios

#### Day 7: Performance Validation
**CRITICAL: Establish performance baselines**
- Benchmark sync vs async operations
- Test concurrent request handling
- Validate memory usage patterns
- Establish performance regression thresholds

### Phase 2: Service Layer Updates (Days 8-14)

#### Day 8: Core Services
**ChatService Update (TDD):**
```python
# RED: Write failing async service test
@pytest.mark.asyncio
async def test_async_chat_service_process_message():
    chat_service = ChatService(config, async_database, ...)
    response = await chat_service.process_chat_message("test")
    assert response is not None

# GREEN: Convert service methods
class ChatService:
    async def process_chat_message(self, message: str):
        context = await self._get_chat_context(message)  # Now async
        # ... rest of async implementation
```

**IngestionService Update:**
- Convert database calls to async
- Update data item processing pipeline

#### Day 9: Additional Services
**Services to update:**
- **WeatherService**: Convert 4 database calls
- **NewsService**: Convert 8 database calls
- **TemplateProcessor**: Convert 12 database calls
- **DocumentService**: Convert database operations
- **CleanUpCrewService**: Convert database queries
- **SemanticDeduplicationService**: Convert deduplication operations
- **NetworkDiagnosticsService**: Convert performance metrics
- **PortStateService**: Convert database logging

#### Day 10: Startup & Rate Limit Services
**StartupService:**
```python
async def initialize_database(self):
    self.database = AsyncDatabaseService(db_path)
    await self.database.initialize()  # Async initialization
```

**TwitterRateLimitService Update:**
```python
# Convert existing fetch_one/execute_query wrappers to native async
async def can_fetch_now(self):
    row = await self.database.fetch_one("SELECT last_fetch_time FROM twitter_rate_limits WHERE id = 1")
    # Convert to native async database calls
```

#### Day 11: Risk Mitigation Implementation
**CRITICAL: Add rollback capabilities**
- Implement feature flags for async/sync toggle
- Create database backup procedures
- Add monitoring for async operation failures
- Establish rollback procedures for each service

#### Day 12: Concurrent Operation Testing
**CRITICAL: Test async concurrency**
- Test 50+ concurrent database operations
- Validate connection pool behavior
- Monitor memory usage under load
- Test error propagation in concurrent scenarios

#### Day 13: Integration Testing
**CRITICAL: End-to-end async validation**
- Test service-to-service async communication
- Validate FastAPI dependency injection with async database
- Test websocket integration with async database
- Validate startup sequence with async initialization

#### Day 14: Performance Benchmarking
**CRITICAL: Comprehensive performance validation**
- Compare sync vs async performance under load
- Test response time degradation (< 100ms target)
- Validate memory usage patterns
- Establish performance monitoring baselines

### Phase 3: Source Layer Updates (Days 15-18)

#### Day 15: Twitter & Limitless Sources
**TwitterSource (10+ database calls):**
```python
# TDD: Async source tests
@pytest.mark.asyncio
async def test_async_twitter_source_fetch():
    twitter_source = TwitterSource(config, async_database, ...)
    items = await twitter_source.fetch_items()
    assert isinstance(items, list)

# Implementation
async def fetch_today_tweets(self):
    existing = await self.db_service.get_data_items_by_date(date, [self.namespace])
    # ... async implementation
```

**LimitlessSource (20+ database calls):**
- Async lifelog data processing
- Async batch imports
- Async deduplication

#### Day 16: WeatherSource & NewsSource
- Convert all database operations to async
- Test concurrent source operations
- Validate error handling in source layer

#### Day 17: Source Integration Testing
**CRITICAL: Test source-to-database async flow**
- Test data ingestion pipelines
- Validate batch processing performance
- Test error recovery in source operations
- Monitor resource usage during ingestion

#### Day 18: Source Performance Optimization
**CRITICAL: Optimize source performance**
- Benchmark source operation throughput
- Optimize batch processing sizes
- Test memory usage during large imports
- Validate concurrent source operations

### Phase 4: API Layer Updates (Days 19-22)

#### Day 19: FastAPI Routes
**Routes to update:**
- **calendar.py**: 25+ database calls
- **data_items.py**: Data item CRUD operations
- **settings.py**: Application settings management
- **sync.py**: Synchronization status endpoints
- **documents.py**: Document search and indexing
- **weather.py, news.py, headings.py, semantic_patterns.py**: Convert all database dependencies

**Update Pattern:**
```python
# Before (sync in async context - BAD)
@router.get("/day/{date}")
async def get_day_details(date: str, database: DatabaseService = Depends(...)):
    data_items = database.get_data_items_by_date(date, namespaces)  # Blocking!
    return {"data": data_items}

# After (proper async)
@router.get("/day/{date}")
async def get_day_details(date: str, database: AsyncDatabaseService = Depends(...)):
    data_items = await database.get_data_items_by_date(date, namespaces)
    return {"data": data_items}
```

#### Day 20: API Integration Testing
**CRITICAL: Test FastAPI async integration**
- Test concurrent API requests
- Validate dependency injection with async database
- Test websocket API endpoints
- Monitor API response times

#### Day 21: API Performance Testing
**CRITICAL: API performance validation**
- Test API throughput under load
- Validate response time targets
- Test concurrent user scenarios
- Monitor API resource usage

#### Day 22: API Documentation & Monitoring
**CRITICAL: Add API monitoring**
- Implement async operation tracing
- Add performance monitoring endpoints
- Create health check endpoints
- Document async API patterns

### Phase 5: Test Suite Migration & Validation (Days 23-25)

#### Day 23: Test Infrastructure Updates
1. **Create async test fixtures**
   ```python
   @pytest_asyncio.fixture
   async def async_database():
       """Async database fixture for testing"""
       with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
           db_path = tmp.name

       db_service = AsyncDatabaseService(db_path)
       await db_service.initialize()

       yield db_service

       # Async cleanup
       await db_service.close()
       if os.path.exists(db_path):
           os.unlink(db_path)
   ```

2. **Migrate DatabaseService unit tests** (53 tests)
   ```python
   # Before (sync test)
   def test_store_data_item_success(database):
       item_id = "test:123"
       database.store_data_item(item_id, "test", "123", "content")
       items = database.get_data_items_by_ids([item_id])
       assert len(items) == 1

   # After (async test)
   @pytest.mark.asyncio
   async def test_store_data_item_success(async_database):
       item_id = "test:123"
       await async_database.store_data_item(item_id, "test", "123", "content")
       items = await async_database.get_data_items_by_ids([item_id])
       assert len(items) == 1
   ```

3. **Update integration tests**
   ```python
   @pytest.mark.asyncio
   async def test_calendar_api_async_database_integration():
       """Test full async flow from API to database"""
       async with AsyncClient(app=app, base_url="http://test") as client:
           response = await client.get("/calendar/day/2024-01-01")
           assert response.status_code == 200
   ```

#### Day 24: Performance Benchmarking
```python
@pytest.mark.asyncio
async def test_async_concurrent_operations_performance(async_database):
    """Test concurrent async operations performance"""
    start_time = time.perf_counter()

    tasks = []
    for i in range(100):
        task = async_database.store_data_item(f"perf:concurrent_{i}", "perf", str(i), f"Content {i}")
        tasks.append(task)

    await asyncio.gather(*tasks)
    concurrent_time = time.perf_counter() - start_time

    # Compare with sequential operations
    start_time = time.perf_counter()
    for i in range(100, 200):
        await async_database.store_data_item(f"perf:sequential_{i}", "perf", str(i), f"Content {i}")
    sequential_time = time.perf_counter() - start_time

    # Concurrent should be significantly faster
    assert concurrent_time < sequential_time * 0.5
```

#### Day 25: Final Validation & Documentation
**CRITICAL: Comprehensive final validation**
- Run full test suite with async configuration
- Validate all performance benchmarks
- Test production-like load scenarios
- Document all async patterns and best practices
- Create rollback procedures and monitoring guides

## Technical Implementation Details

### Async Connection Management
```python
class AsyncDatabaseService:
    def __init__(self, db_path: str = "lifeboard.db"):
        self.db_path = db_path

    async def initialize(self):
        """Async initialization"""
        await self._init_database()

    @asynccontextmanager
    async def get_connection(self):
        """Async context manager for database connections"""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            yield conn

    async def store_data_item(self, id: str, namespace: str, source_id: str,
                             content: str, metadata: Dict = None, days_date: str = None,
                             ingestion_status: str = 'complete'):
        """Async data storage"""
        async with self.get_connection() as conn:
            await conn.execute("""
                INSERT OR REPLACE INTO data_items
                (id, namespace, source_id, content, metadata, days_date, updated_at, ingestion_status)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
            """, (id, namespace, source_id, content,
                  JSONMetadataParser.serialize_metadata(metadata), days_date, ingestion_status))
            await conn.commit()
```

### Application Integration
- **Dependency Injection**: Update factory functions to create AsyncDatabaseService instances
- **Startup Sequence**: Update lifespan context manager to await async initialization
- **Migration Runner**: Convert to async migration execution

### Service Update Pattern
```python
# Before (sync)
class ChatService:
    def process_chat_message(self, message: str) -> str:
        context = self._get_chat_context(message)
        response = self._generate_response(message, context)
        self.database.store_chat_message(message, response)
        return response

# After (async)
class ChatService:
    async def process_chat_message(self, message: str) -> str:
        context = await self._get_chat_context(message)
        response = await self._generate_response(message, context)
        await self.database.store_chat_message(message, response)
        return response
```

## Risk Mitigation & Quality Assurance

### Technical Risks & Mitigation
1. **Async Complexity**: Deadlocks, race conditions, improper await usage
   - Mitigation: Comprehensive test coverage, code reviews, async linting

2. **Performance Regression**: Slower performance than sync version
   - Mitigation: Benchmarking at each phase, performance monitoring

3. **Connection Management**: Connection leaks, resource exhaustion
   - Mitigation: Proper async context managers, connection monitoring

4. **Migration Failures**: Database schema issues, data loss
   - Mitigation: Database backups, rollback procedures, migration testing

### Quality Gates
- [ ] All ~66 self.database calls converted to async
- [ ] All existing tests pass with async changes
- [ ] Performance benchmarks within 5% of baseline
- [ ] No memory leaks in async operations
- [ ] All database connections properly closed
- [ ] No blocking operations in async contexts

### Rollback Strategy
1. **Feature Flag**: Implement async/sync toggle for gradual rollout
2. **Database Backup**: Full backup before migration starts
3. **Gradual Migration**: Phase-by-phase rollout with monitoring
4. **Quick Revert**: Ability to revert to sync version within 1 hour

## Estimated Effort & Timeline

### Development Effort: 25 Days
- **Foundation & Critical Fixes**: 2 days
- **Core Database Conversion**: 5 days
- **Service Layer Updates**: 7 days
- **Source Layer Updates**: 4 days
- **API Layer Updates**: 4 days
- **Test Migration & Validation**: 3 days

### Resource Requirements
- **Primary Developer**: Full-time on async conversion
- **Test Engineer**: Parallel test migration and validation

### Success Metrics
- **Performance**: Improved concurrent request handling
- **Architecture**: 100% async consistency across all layers
- **Quality**: Zero regression in functionality or reliability
- **Maintainability**: Cleaner async/await patterns throughout codebase

## Document Corrections Summary

**This document has been corrected based on comprehensive codebase analysis:**

### Key Corrections Made:
1. **Database Method Calls**: Corrected from ~421 to ~66 self.database calls and ~210 total database calls
2. **Existing Async Wrappers**: Documented existing `fetch_one` and `execute_query` methods
3. **Dependencies**: Added aiosqlite to requirements, noted existing pytest-asyncio
4. **Timeline**: Extended from 10 days to 25 days for realistic completion
5. **Enterprise Architecture**: Removed premature advanced features (circuit breakers, complex connection pooling)
6. **Test Configuration**: Added pytest.ini async configuration requirements

### Additional Analysis Findings:
- DatabaseService has ~30 methods requiring async conversion
- Many services already use async patterns but with sync database calls
- TwitterRateLimitService already has partial async integration
- FastAPI dependency injection patterns are established for easy conversion
- Comprehensive test coverage exists to aid TDD conversion
