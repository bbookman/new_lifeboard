# Lifeboard Database Schema

This document lists the SQL statements used to create every table in the Lifeboard database, including all columns and constraints, as defined in all migrations.

---

## Table: system_settings
```sql
CREATE TABLE IF NOT EXISTS system_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Table: migrations
```sql
CREATE TABLE IF NOT EXISTS migrations (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Table: data_sources
```sql
CREATE TABLE IF NOT EXISTS data_sources (
    namespace TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    metadata TEXT,
    item_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    last_synced TIMESTAMP,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Table: data_items
```sql
CREATE TABLE IF NOT EXISTS data_items (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    source_id TEXT NOT NULL,
    content TEXT,
    metadata TEXT,
    embedding_status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    days_date TEXT NOT NULL,
    semantic_status TEXT DEFAULT 'pending' CHECK (semantic_status IN ('pending', 'processing', 'completed', 'failed')),
    semantic_processed_at TIMESTAMP,
    processing_priority INTEGER DEFAULT 1,
    ingestion_status TEXT DEFAULT 'complete' CHECK (ingestion_status IN ('partial', 'complete', 'failed'))
);
```

---

## Table: chat_messages
```sql
CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_message TEXT NOT NULL,
    assistant_response TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Table: weather
```sql
CREATE TABLE IF NOT EXISTS weather (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    days_date TEXT NOT NULL,
    response_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Table: news
```sql
CREATE TABLE IF NOT EXISTS news (
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
```

---

## Table: limitless
```sql
CREATE TABLE IF NOT EXISTS limitless (
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
```

---

## Table: semantic_clusters
```sql
CREATE TABLE IF NOT EXISTS semantic_clusters (
    id TEXT PRIMARY KEY,
    theme TEXT NOT NULL,
    canonical_line TEXT NOT NULL,
    confidence_score REAL NOT NULL CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
    frequency_count INTEGER NOT NULL CHECK (frequency_count > 0),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Table: line_cluster_mapping
```sql
CREATE TABLE IF NOT EXISTS line_cluster_mapping (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data_item_id TEXT NOT NULL,
    line_content TEXT NOT NULL,
    cluster_id TEXT NOT NULL,
    similarity_score REAL NOT NULL CHECK (similarity_score >= 0.0 AND similarity_score <= 1.0),
    speaker TEXT,
    line_timestamp TEXT,
    is_canonical BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (data_item_id) REFERENCES data_items(id) ON DELETE CASCADE,
    FOREIGN KEY (cluster_id) REFERENCES semantic_clusters(id) ON DELETE CASCADE
);
```

---

## Table: user_documents
```sql
CREATE TABLE IF NOT EXISTS user_documents (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    document_type TEXT NOT NULL CHECK (document_type IN ('note', 'prompt', 'folder', 'link')),
    content_delta TEXT NOT NULL,  -- Quill Delta JSON format
    content_md TEXT NOT NULL,     -- Markdown version for search/LLM
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    path VARCHAR(500) DEFAULT '/' NOT NULL,
    is_folder BOOLEAN DEFAULT FALSE NOT NULL,
    url TEXT  -- URL for link documents
);
```

---

## Table: user_documents_fts (Full-Text Search)
```sql
CREATE VIRTUAL TABLE IF NOT EXISTS user_documents_fts USING fts5(
    title,
    content_md,
    content=user_documents,
    content_rowid=id
);
```

---

## Table: prompt_settings
```sql
CREATE TABLE IF NOT EXISTS prompt_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    setting_key TEXT NOT NULL UNIQUE,  -- e.g., 'daily_summary_prompt'
    prompt_document_id TEXT,           -- References user_documents.id
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (prompt_document_id) REFERENCES user_documents(id) ON DELETE SET NULL
);
```

---

## Table: generated_summaries
```sql
CREATE TABLE IF NOT EXISTS generated_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    days_date TEXT NOT NULL,
    content TEXT NOT NULL,
    prompt_used TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Table: template_cache
```sql
CREATE TABLE template_cache (
    id TEXT PRIMARY KEY,
    template_hash TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    target_date TEXT NOT NULL,
    resolved_content TEXT NOT NULL,
    variables_resolved INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);
```

---

This document covers all tables as defined in the migration scripts and bootstrap schema. Indexes and triggers are not included here, but are present in the codebase for performance and data integrity.
