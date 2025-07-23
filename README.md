# Lifeboard

An interactive reflection space and AI-powered planning assistant that transforms daily digital history into a personal newspaper. Lifeboard seamlessly integrates conversations, activities, moods, and experiences with AI assistance for discovery and planning.

## Configuration (.env Settings)

Lifeboard uses environment variables for configuration. Create a `.env` file in the project root with the following settings:

### Core Data Source (Required)

#### `LIMITLESS_API_KEY`
- **Purpose**: Your Limitless AI API key for accessing lifelog data
- **Required**: Yes
- **Example**: `LIMITLESS_API_KEY=your_actual_api_key_here`
- **Notes**: Without this, the system cannot sync your personal data

### Data Synchronization

#### `AUTO_SYNC_ENABLED`
- **Purpose**: Enable automatic data synchronization from Limitless
- **Default**: `true`
- **Recommended**: `true`
- **Example**: `AUTO_SYNC_ENABLED=true`

#### `LIMITLESS_SYNC_INTERVAL_HOURS`
- **Purpose**: Hours between automatic data syncs (how often to fetch new data)
- **Default**: `6`
- **Recommended**: `1-2` (frequent syncing for fresh data)
- **Range**: `1-168` hours
- **Example**: `LIMITLESS_SYNC_INTERVAL_HOURS=1`

### LLM Provider Configuration

#### `LLM_PROVIDER`
- **Purpose**: Choose between local (Ollama) or cloud (OpenAI) LLM
- **Default**: `ollama`
- **Options**: `ollama`, `openai`
- **Recommended**: `ollama` for privacy, `openai` for convenience
- **Example**: `LLM_PROVIDER=ollama`

### Ollama Configuration (Local LLM)

#### `OLLAMA_BASE_URL`
- **Purpose**: Local Ollama server URL
- **Default**: `http://localhost:11434`
- **Example**: `OLLAMA_BASE_URL=http://localhost:11434`

#### `OLLAMA_MODEL`
- **Purpose**: Ollama model name to use
- **Default**: `llama2`
- **Recommended**: `mistral:latest`, `llama2`, `codellama`
- **Example**: `OLLAMA_MODEL=mistral:latest`

#### `OLLAMA_TIMEOUT`
- **Purpose**: Request timeout in seconds
- **Default**: `60.0`
- **Recommended**: `30-120` depending on model size
- **Example**: `OLLAMA_TIMEOUT=60.0`

#### `OLLAMA_MAX_RETRIES`
- **Purpose**: Maximum retry attempts for failed requests
- **Default**: `3`
- **Example**: `OLLAMA_MAX_RETRIES=3`

### OpenAI Configuration (Cloud LLM)

#### `OPENAI_API_KEY`
- **Purpose**: OpenAI API key
- **Required**: Only if using `LLM_PROVIDER=openai`
- **Example**: `OPENAI_API_KEY=your_openai_api_key_here`

#### `OPENAI_MODEL`
- **Purpose**: OpenAI model to use
- **Default**: `gpt-3.5-turbo`
- **Options**: `gpt-3.5-turbo`, `gpt-4`, `gpt-4-turbo`
- **Example**: `OPENAI_MODEL=gpt-3.5-turbo`

#### `OPENAI_MAX_TOKENS`
- **Purpose**: Maximum tokens per response
- **Default**: `1000`
- **Recommended**: `500-2000`
- **Example**: `OPENAI_MAX_TOKENS=1000`

#### `OPENAI_TEMPERATURE`
- **Purpose**: Response creativity (0.0-2.0, lower = more focused)
- **Default**: `0.7`
- **Recommended**: `0.3-0.9`
- **Example**: `OPENAI_TEMPERATURE=0.7`

### Embedding Processing (Semantic Search)

#### `EMBEDDING_PROCESSING_ENABLED`
- **Purpose**: Enable background embedding generation for semantic search
- **Default**: `true`
- **Recommended**: `true`
- **Example**: `EMBEDDING_PROCESSING_ENABLED=true`

#### `EMBEDDING_PROCESSING_INTERVAL_HOURS`
- **Purpose**: Hours between embedding processing runs
- **Default**: `6`
- **Recommended**: `6-24` (less frequent than data sync)
- **Example**: `EMBEDDING_PROCESSING_INTERVAL_HOURS=6`

#### `EMBEDDING_PROCESSING_BATCH_SIZE`
- **Purpose**: Number of items to process per embedding batch
- **Default**: `100`
- **Recommended**: `50-200` (larger = faster but more memory)
- **Example**: `EMBEDDING_PROCESSING_BATCH_SIZE=100`

#### `EMBEDDING_MODEL`
- **Purpose**: Sentence transformer model for embeddings
- **Default**: `all-MiniLM-L6-v2`
- **Options**: `all-MiniLM-L6-v2` (fast), `all-mpnet-base-v2` (better quality)
- **Example**: `EMBEDDING_MODEL=all-MiniLM-L6-v2`

#### `EMBEDDING_DEVICE`
- **Purpose**: Processing device for embeddings
- **Default**: `cpu`
- **Options**: `cpu`, `cuda` (with GPU), `mps` (Apple Silicon)
- **Example**: `EMBEDDING_DEVICE=cpu`

### Chat Interface

#### `CHAT_ENABLED`
- **Purpose**: Enable the web chat interface
- **Default**: `true`
- **Example**: `CHAT_ENABLED=true`

#### `CHAT_HISTORY_LIMIT`
- **Purpose**: Maximum stored chat messages
- **Default**: `1000`
- **Example**: `CHAT_HISTORY_LIMIT=1000`

#### `CHAT_CONTEXT_WINDOW`
- **Purpose**: Maximum context size for LLM (characters)
- **Default**: `4000`
- **Example**: `CHAT_CONTEXT_WINDOW=4000`

#### `CHAT_RESPONSE_TIMEOUT`
- **Purpose**: Chat response timeout in seconds
- **Default**: `30.0`
- **Example**: `CHAT_RESPONSE_TIMEOUT=30.0`

### Logging

#### `LOG_LEVEL`
- **Purpose**: Logging verbosity
- **Default**: `INFO`
- **Options**: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- **Recommended**: `INFO` for normal use, `DEBUG` for troubleshooting
- **Example**: `LOG_LEVEL=INFO`

#### `LOG_FILE_PATH`
- **Purpose**: Path to log file
- **Default**: `logs/lifeboard.log`
- **Example**: `LOG_FILE_PATH=logs/lifeboard.log`

#### `LOG_CONSOLE_LOGGING`
- **Purpose**: Enable console output for logs
- **Default**: `true`
- **Example**: `LOG_CONSOLE_LOGGING=true`

## Example Configuration Files

### Minimal Configuration (Required Settings Only)
```env
# Essential settings
LIMITLESS_API_KEY=your_actual_api_key_here
```

### Recommended Configuration
```env
# Core settings
LIMITLESS_API_KEY=your_actual_api_key_here
AUTO_SYNC_ENABLED=true
LIMITLESS_SYNC_INTERVAL_HOURS=1

# LLM Configuration
LLM_PROVIDER=ollama
OLLAMA_MODEL=mistral:latest

# Embedding Processing
EMBEDDING_PROCESSING_ENABLED=true
EMBEDDING_PROCESSING_INTERVAL_HOURS=6

# Logging
LOG_LEVEL=INFO
LOG_CONSOLE_LOGGING=true
```

### High-Performance Configuration
```env
# Core settings
LIMITLESS_API_KEY=your_actual_api_key_here
LIMITLESS_SYNC_INTERVAL_HOURS=1

# Use OpenAI for better responses
LLM_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4

# Faster embedding processing
EMBEDDING_PROCESSING_INTERVAL_HOURS=2
EMBEDDING_PROCESSING_BATCH_SIZE=200
EMBEDDING_MODEL=all-mpnet-base-v2
EMBEDDING_DEVICE=cuda  # If you have a GPU

# Enhanced chat
CHAT_CONTEXT_WINDOW=8000
OPENAI_MAX_TOKENS=2000
```

## Architecture Notes

- **Data Sync**: Runs independently from embedding processing for faster data ingestion
- **Search Fallback**: Chat works immediately with keyword search, improves as embeddings are processed
- **Progressive Enhancement**: System becomes more capable as background processing completes
- **Resource Management**: Separate intervals allow balancing performance vs resource usage