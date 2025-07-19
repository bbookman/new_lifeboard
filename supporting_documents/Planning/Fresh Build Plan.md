# KISS Fresh Build Plan

## Overview
This document provides detailed instructions for building a new KISS multi-source memory chat application from scratch, implementing the clean architecture defined in the "Refactor plan.md" without the complexity of the existing codebase.

## Purpose
- Enable parallel development of a clean implementation
- Validate architectural decisions without legacy constraints
- Create a reference implementation of the target architecture
- Allow comparison between refactored and fresh approaches

## Target Architecture (From Refactor Plan)

**Data Flow:**
- **Ingestion:** Fetch/store raw data in SQLite → Generate embedding → Add to FAISS with same ID
- **Search:** Embed query → Search FAISS → Get top-N vector IDs → Fetch corresponding SQLite rows → Pass full data into LLM  
- **Updates:** Update SQLite row → Re-embed → Update FAISS vector

## Phase 1: Core Foundation (Week 1)

### 1.1 Project Structure
```
kiss-fresh/
├── README.md
├── requirements.txt
├── main.py
├── config/
│   ├── __init__.py
│   ├── models.py          # Pydantic configuration models
│   ├── settings.py        # Database-backed settings
│   └── factory.py         # Configuration factory
├── core/
│   ├── __init__.py
│   ├── database.py        # SQLite operations
│   ├── vector_store.py    # FAISS operations  
│   ├── embeddings.py      # Embedding service
│   └── ids.py             # Namespaced ID management
├── sources/
│   ├── __init__.py
│   ├── base.py            # Source abstraction
│   ├── registry.py        # Auto-registration
│   └── adapters/
├── services/
│   ├── __init__.py
│   ├── namespace_prediction.py
│   ├── search.py          # Main search orchestration
│   ├── ingestion.py       # Data ingestion pipeline
│   └── scheduler.py       # Re-embedding scheduler
├── api/
│   ├── __init__.py
│   ├── server.py          # FastAPI application
│   └── models.py          # API request/response models
└── tests/
```

### 1.2 Dependencies (requirements.txt)
```
# Core
pydantic>=2.0.0
python-dotenv>=1.0.0

# Database
sqlite3 (built-in)

# Vector Search
faiss-cpu>=1.7.0
sentence-transformers>=2.6.0
numpy>=1.24.0

# LLM Integration
openai>=1.0.0
anthropic>=0.25.0

# Web API
fastapi>=0.104.0
uvicorn>=0.24.0

# Testing
pytest>=7.0.0
pytest-asyncio>=0.21.0
```

### 1.3 Database Schema (core/database.py)
```sql
-- System settings table
CREATE TABLE system_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Data sources registry
CREATE TABLE data_sources (
    namespace TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    item_count INTEGER DEFAULT 0,
    metadata TEXT, -- JSON
    is_active BOOLEAN DEFAULT TRUE
);

-- Unified data storage
CREATE TABLE data_items (
    id TEXT PRIMARY KEY,  -- Format: "namespace:source_id"
    namespace TEXT NOT NULL,
    source_id TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata TEXT,        -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    embedding_status TEXT DEFAULT 'pending', -- pending, completed, failed
    FOREIGN KEY (namespace) REFERENCES data_sources(namespace)
);

-- Create indexes
CREATE INDEX idx_data_items_namespace ON data_items(namespace);
CREATE INDEX idx_data_items_embedding_status ON data_items(embedding_status);
CREATE INDEX idx_data_items_updated_at ON data_items(updated_at);
```

## Phase 2: Core Services (Week 2)

### 2.1 Namespaced ID System (core/ids.py)
```python
from typing import Tuple
import uuid

class NamespacedIDManager:
    @staticmethod
    def create_id(namespace: str, source_id: str = None) -> str:
        """Create namespaced ID: namespace:source_id"""
        if source_id is None:
            source_id = str(uuid.uuid4())
        return f"{namespace}:{source_id}"
    
    @staticmethod
    def parse_id(namespaced_id: str) -> Tuple[str, str]:
        """Parse namespaced ID into (namespace, source_id)"""
        parts = namespaced_id.split(':', 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid namespaced ID: {namespaced_id}")
        return parts[0], parts[1]
    
    @staticmethod
    def get_namespace(namespaced_id: str) -> str:
        """Extract namespace from namespaced ID"""
        return namespaced_id.split(':', 1)[0]
```

### 2.2 Database Service (core/database.py)
```python
import sqlite3
import json
from typing import List, Dict, Optional, Any
from contextlib import contextmanager

class DatabaseService:
    def __init__(self, db_path: str = "kiss.db"):
        self.db_path = db_path
        self._init_database()
    
    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def store_data_item(self, id: str, namespace: str, source_id: str, 
                       content: str, metadata: Dict = None):
        """Store data item with namespaced ID"""
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO data_items 
                (id, namespace, source_id, content, metadata, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (id, namespace, source_id, content, 
                  json.dumps(metadata) if metadata else None))
            conn.commit()
    
    def get_data_items_by_ids(self, ids: List[str]) -> List[Dict]:
        """Batch fetch data items by namespaced IDs"""
        if not ids:
            return []
        
        placeholders = ','.join('?' * len(ids))
        with self.get_connection() as conn:
            cursor = conn.execute(f"""
                SELECT id, namespace, source_id, content, metadata
                FROM data_items 
                WHERE id IN ({placeholders})
            """, ids)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get database-backed setting"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT value FROM system_settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return json.loads(row['value']) if row else default
    
    def set_setting(self, key: str, value: Any):
        """Set database-backed setting"""
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO system_settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (key, json.dumps(value)))
            conn.commit()
```

### 2.3 Vector Store Service (core/vector_store.py)
```python
import faiss
import numpy as np
import json
import os
from typing import List, Tuple, Dict
import threading

class VectorStoreService:
    def __init__(self, index_path: str = "vector_store/index.faiss",
                 id_map_path: str = "vector_store/id_map.json"):
        self.index_path = index_path
        self.id_map_path = id_map_path
        self.index = None
        self.id_to_vector_id = {}  # namespaced_id -> vector_id
        self.vector_id_to_id = {}  # vector_id -> namespaced_id
        self.next_vector_id = 0
        self.operation_count = 0
        self.lock = threading.Lock()
        self._load_or_create_index()
    
    def add_vector(self, namespaced_id: str, vector: np.ndarray):
        """Add vector with namespaced ID"""
        with self.lock:
            vector_id = self.next_vector_id
            self.id_to_vector_id[namespaced_id] = vector_id
            self.vector_id_to_id[vector_id] = namespaced_id
            self.next_vector_id += 1
            
            # Add to FAISS index
            self.index.add(vector.reshape(1, -1))
            self.operation_count += 1
            
            # Auto-save based on activity
            if self.operation_count >= 100:  # Configurable threshold
                self.save_index()
                self.operation_count = 0
    
    def search(self, query_vector: np.ndarray, k: int = 10, 
               namespace_filter: List[str] = None) -> List[Tuple[str, float]]:
        """Search vectors and return namespaced IDs with scores"""
        with self.lock:
            distances, indices = self.index.search(query_vector.reshape(1, -1), k)
            
            results = []
            for i, (distance, vector_id) in enumerate(zip(distances[0], indices[0])):
                if vector_id == -1:  # No more results
                    break
                
                namespaced_id = self.vector_id_to_id.get(vector_id)
                if namespaced_id:
                    # Apply namespace filter if specified
                    if namespace_filter:
                        namespace = namespaced_id.split(':', 1)[0]
                        if namespace not in namespace_filter:
                            continue
                    
                    similarity = 1.0 / (1.0 + distance)  # Convert distance to similarity
                    results.append((namespaced_id, similarity))
            
            return results
    
    def save_index(self):
        """Save FAISS index and ID mappings to disk"""
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
        faiss.write_index(self.index, self.index_path)
        
        with open(self.id_map_path, 'w') as f:
            json.dump({
                'id_to_vector_id': self.id_to_vector_id,
                'vector_id_to_id': self.vector_id_to_id,
                'next_vector_id': self.next_vector_id
            }, f)
```

## Phase 3: Source Abstraction (Week 3)

### 3.1 Source Base Classes (sources/base.py)
```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class DataItem(BaseModel):
    source_id: str
    content: str
    metadata: Optional[Dict[str, Any]] = None

class SourceBase(ABC):
    def __init__(self, namespace: str):
        self.namespace = namespace
    
    @abstractmethod
    async def fetch_data(self) -> List[DataItem]:
        """Fetch data from this source"""
        pass
    
    @abstractmethod
    def get_source_info(self) -> Dict[str, Any]:
        """Return source metadata for progressive collection"""
        pass

class FileSource(SourceBase):
    def __init__(self, namespace: str, file_path: str):
        super().__init__(namespace)
        self.file_path = file_path
    
    async def fetch_data(self) -> List[DataItem]:
        # Implementation for file reading
        pass

class APISource(SourceBase):
    def __init__(self, namespace: str, api_config: Dict):
        super().__init__(namespace)
        self.api_config = api_config
    
    async def fetch_data(self) -> List[DataItem]:
        # Implementation for API calls
        pass
```

### 3.2 Source Registry (sources/registry.py)
```python
from typing import Dict, Type, List
import os
from .base import SourceBase, FileSource, APISource

class SourceRegistry:
    def __init__(self):
        self.source_types: Dict[str, Type[SourceBase]] = {}
        self.active_sources: Dict[str, SourceBase] = {}
        self._register_built_in_sources()
        self._auto_discover_sources()
    
    def _register_built_in_sources(self):
        """Register built-in source types"""
        self.source_types['file'] = FileSource
        self.source_types['api'] = APISource
    
    def _auto_discover_sources(self):
        """Auto-discover sources from environment variables"""
        # Look for patterns like MUSIC_SOURCE_ENABLED=true
        for key, value in os.environ.items():
            if key.endswith('_SOURCE_ENABLED') and value.lower() == 'true':
                namespace = key.replace('_SOURCE_ENABLED', '').lower()
                source_type = os.environ.get(f'{namespace.upper()}_SOURCE_TYPE', 'api')
                
                if source_type in self.source_types:
                    source_class = self.source_types[source_type]
                    # Create source instance based on config
                    self._create_source_instance(namespace, source_class)
    
    def get_active_sources(self) -> List[SourceBase]:
        """Get all active source instances"""
        return list(self.active_sources.values())
    
    def get_namespaces(self) -> List[str]:
        """Get all active namespaces"""
        return list(self.active_sources.keys())
```

## Phase 4: LLM Integration (Week 4)

### 4.1 Namespace Prediction Service (services/namespace_prediction.py)
```python
import json
from typing import List, Dict
import openai
from config.models import LLMConfig

class NamespacePredictionService:
    def __init__(self, llm_config: LLMConfig, available_namespaces: List[str]):
        self.llm_config = llm_config
        self.available_namespaces = available_namespaces
        self.client = openai.OpenAI(api_key=llm_config.api_key)
    
    async def predict_namespaces(self, query: str, max_retries: int = 3) -> Dict:
        """Predict relevant namespaces with priority for query"""
        prompt = self._build_prediction_prompt(query)
        
        for attempt in range(max_retries):
            try:
                response = await self._call_llm(prompt)
                return self._parse_response(response)
            except Exception as e:
                if attempt == max_retries - 1:
                    # Final fallback: all namespaces
                    return {
                        "namespaces": self.available_namespaces,
                        "priority": self.available_namespaces
                    }
                # Exponential backoff
                await asyncio.sleep(0.1 * (2 ** attempt))
        
    def _build_prediction_prompt(self, query: str) -> str:
        namespaces_str = ", ".join(self.available_namespaces)
        return f"""
Given this user query: "{query}"

Available data sources: {namespaces_str}

Determine which sources are relevant and return a JSON response with:
- "namespaces": list of relevant source names
- "priority": same sources ordered by importance for this query

Example: {{"namespaces": ["music", "limitless"], "priority": ["music", "limitless"]}}

Response:"""
    
    async def _call_llm(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.llm_config.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,  # Low temperature for consistent responses
            max_tokens=200
        )
        return response.choices[0].message.content
    
    def _parse_response(self, response: str) -> Dict:
        try:
            parsed = json.loads(response.strip())
            # Validate response structure
            if "namespaces" in parsed and "priority" in parsed:
                # Filter to only available namespaces
                valid_namespaces = [ns for ns in parsed["namespaces"] 
                                  if ns in self.available_namespaces]
                valid_priority = [ns for ns in parsed["priority"] 
                                if ns in self.available_namespaces]
                return {
                    "namespaces": valid_namespaces or self.available_namespaces,
                    "priority": valid_priority or self.available_namespaces
                }
        except:
            pass
        
        # Fallback to all namespaces
        return {
            "namespaces": self.available_namespaces,
            "priority": self.available_namespaces
        }
```

### 4.2 Main Search Service (services/search.py)
```python
from typing import List, Dict, Any
from core.database import DatabaseService
from core.vector_store import VectorStoreService
from core.embeddings import EmbeddingService
from services.namespace_prediction import NamespacePredictionService

class SearchService:
    def __init__(self, db_service: DatabaseService, 
                 vector_service: VectorStoreService,
                 embedding_service: EmbeddingService,
                 prediction_service: NamespacePredictionService):
        self.db = db_service
        self.vector_store = vector_service
        self.embeddings = embedding_service
        self.prediction = prediction_service
    
    async def search(self, query: str, top_k: int = 10) -> Dict[str, Any]:
        """Execute the 4-step search process"""
        
        # Step 1: Predict relevant namespaces
        namespace_prediction = await self.prediction.predict_namespaces(query)
        relevant_namespaces = namespace_prediction["namespaces"]
        priority_order = namespace_prediction["priority"]
        
        # Step 2: Embed query
        query_vector = await self.embeddings.embed_text(query)
        
        # Step 3: Search FAISS with namespace filter
        vector_results = self.vector_store.search(
            query_vector, 
            k=top_k,
            namespace_filter=relevant_namespaces
        )
        
        # Step 4: Fetch full data from SQLite
        result_ids = [result[0] for result in vector_results]
        full_data = self.db.get_data_items_by_ids(result_ids)
        
        # Step 5: Group by source with priority order
        grouped_results = self._group_by_source_priority(full_data, priority_order)
        
        return {
            "query": query,
            "predicted_sources": relevant_namespaces,
            "priority_order": priority_order,
            "results": grouped_results,
            "total_results": len(full_data)
        }
    
    def _group_by_source_priority(self, data_items: List[Dict], 
                                 priority_order: List[str]) -> Dict[str, List[Dict]]:
        """Group results by source according to priority order"""
        grouped = {}
        
        # Group by namespace
        for item in data_items:
            namespace = item['namespace']
            if namespace not in grouped:
                grouped[namespace] = []
            grouped[namespace].append(item)
        
        # Return in priority order
        ordered_results = {}
        for namespace in priority_order:
            if namespace in grouped:
                ordered_results[namespace] = grouped[namespace]
        
        return ordered_results
```

## Phase 5: Integration & Testing (Week 5)

### 5.1 Main Application (main.py)
```python
import asyncio
from config.factory import create_config
from core.database import DatabaseService
from core.vector_store import VectorStoreService
from core.embeddings import EmbeddingService
from sources.registry import SourceRegistry
from services.namespace_prediction import NamespacePredictionService
from services.search import SearchService
from services.ingestion import IngestionService
from services.scheduler import ReembeddingScheduler

class KISSApplication:
    def __init__(self):
        self.config = create_config()
        self._initialize_services()
    
    def _initialize_services(self):
        """Eager initialization of all services"""
        self.db = DatabaseService(self.config.database.path)
        self.vector_store = VectorStoreService(
            self.config.vector_store.index_path,
            self.config.vector_store.id_map_path
        )
        self.embeddings = EmbeddingService(self.config.embeddings)
        self.source_registry = SourceRegistry()
        
        self.prediction_service = NamespacePredictionService(
            self.config.llm.prediction,
            self.source_registry.get_namespaces()
        )
        
        self.search_service = SearchService(
            self.db, self.vector_store, self.embeddings, self.prediction_service
        )
        
        self.ingestion_service = IngestionService(
            self.db, self.vector_store, self.embeddings, self.source_registry
        )
        
        self.scheduler = ReembeddingScheduler(
            self.db, self.vector_store, self.embeddings
        )
    
    async def start(self):
        """Start the application"""
        print("Starting KISS Memory Chat Application...")
        
        # Start background scheduler
        await self.scheduler.start()
        
        # Example search
        results = await self.search_service.search("what bands were my favorites in 2023")
        print(f"Search completed: {results['total_results']} results found")
        
        return self

async def main():
    app = KISSApplication()
    await app.start()
    
    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")

if __name__ == "__main__":
    asyncio.run(main())
```

### 5.2 FastAPI Server (api/server.py)
```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from main import KISSApplication

app = FastAPI(title="KISS Memory Chat API")
kiss_app = None

@app.on_event("startup")
async def startup():
    global kiss_app
    kiss_app = await KISSApplication().start()

class SearchRequest(BaseModel):
    query: str
    top_k: int = 10

class SearchResponse(BaseModel):
    query: str
    predicted_sources: list
    priority_order: list
    results: dict
    total_results: int

@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    if not kiss_app:
        raise HTTPException(500, "Application not initialized")
    
    results = await kiss_app.search_service.search(request.query, request.top_k)
    return SearchResponse(**results)

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "KISS Memory Chat"}

@app.get("/sources")
async def get_sources():
    if not kiss_app:
        raise HTTPException(500, "Application not initialized")
    
    return {
        "active_sources": kiss_app.source_registry.get_namespaces(),
        "total_sources": len(kiss_app.source_registry.get_active_sources())
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## Implementation Guidelines

### Development Order:
1. **Week 1:** Set up project structure, database schema, basic configuration
2. **Week 2:** Implement core services (database, vector store, embedding, ID management)  
3. **Week 3:** Build source abstraction and registry system
4. **Week 4:** Add LLM integration and namespace prediction
5. **Week 5:** Create main application and API, add comprehensive testing

### Key Principles:
- **Start with interfaces/contracts first** - define clear APIs between components
- **Implement eager initialization** - fail fast if components can't start
- **Use dependency injection** - pass dependencies to constructors
- **Write tests alongside implementation** - don't defer testing
- **Keep components focused** - single responsibility principle
- **Database-first settings** - avoid .env complexity

### Testing Strategy:
- **Unit tests** for each service individually
- **Integration tests** for the complete search flow
- **Mock external services** (LLM calls, file system)
- **Performance tests** for vector search and database operations

### Configuration:
- Use Pydantic models for type safety
- Store runtime settings in database
- Environment variables only for deployment-specific values
- Fail fast on missing required configuration

This fresh build plan provides a complete roadmap for implementing the target architecture from scratch, with clean separation of concerns and modern Python practices throughout.