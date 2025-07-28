# Lifeboard

An interactive reflection space and AI-powered planning assistant that transforms daily digital history into a personal newspaper. Lifeboard seamlessly integrates conversations, activities, moods, and experiences with AI assistance for discovery and planning.

## Quick Start

### Installation
```bash
# Clone the repository
git clone <repository-url>
cd new_lifeboard

# Install dependencies
pip install -r requirements.txt
```

### Configuration
Create a `.env` file in the project root:
```env
# Essential setting - get your API key from Limitless AI
LIMITLESS_API_KEY=your_actual_api_key_here
```

### Run the Application
```bash
# Start the server
python3 -m api.server

# Access the chat interface
# Open http://localhost:8000/chat in your browser
# The actual port will be in the terminal and logs here
# =========================================
#           ACCESS INSTRUCTIONS
# =========================================
# The Lifeboard web UI is accessible at:
#  • http://localhost:8000

# If you need to use a different port, stop the service
# and run: python3 -m api.server --port [PORT_NUMBER]
# For example: python3 -m api.server --port 8555

```

The application will automatically sync your Limitless data and enable AI-powered search across your conversations and experiences.

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

### Limitless Search Configuration

#### `LIMITLESS__SEARCH_ENABLED`
- **Purpose**: Enable real-time Limitless API search for chat queries
- **Default**: `true`
- **Recommended**: `true` (for access to latest data not yet synced)
- **Example**: `LIMITLESS__SEARCH_ENABLED=true`

#### `LIMITLESS__SEARCH_WEIGHT`
- **Purpose**: Weight distribution for API search vs local search (0.0-1.0)
- **Default**: `0.75` (75% API search, 25% local search)
- **Recommended**: `0.5-0.8` (balance between fresh data and performance)
- **Example**: `LIMITLESS__SEARCH_WEIGHT=0.75`


### Global Settings

#### `TIME_ZONE`
- **Purpose**: User's timezone for displaying dates and times in local time
- **Default**: `UTC`
- **Recommended**: Set to your local timezone (e.g., `America/New_York`, `Europe/London`, `Asia/Tokyo`)
- **Example**: `TIME_ZONE=America/New_York`
- **Notes**: Used for news timestamps and fallback for other data sources. Limitless data uses its own timezone setting.

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

#### `EMBEDDING_STARTUP_BURST_ENABLED`
- **Purpose**: Enable startup embedding burst for immediate semantic search capability
- **Default**: `true`
- **Recommended**: `true` (provides instant semantic search for recent data)
- **Example**: `EMBEDDING_STARTUP_BURST_ENABLED=true`
- **Notes**: Processes recent unprocessed items on startup before background processing takes over

#### `EMBEDDING_STARTUP_BURST_LIMIT`
- **Purpose**: Maximum number of items to process during startup burst
- **Default**: `150`
- **Recommended**: `100-300` (balance between startup time and immediate search capability)
- **Example**: `EMBEDDING_STARTUP_BURST_LIMIT=150`
- **Notes**: Higher values provide better search coverage but increase startup time

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
TIME_ZONE=UTC
```

### Recommended Configuration
```env
# Core settings
LIMITLESS_API_KEY=your_actual_api_key_here
TIME_ZONE=America/New_York
AUTO_SYNC_ENABLED=true
LIMITLESS_SYNC_INTERVAL_HOURS=1

# Search Configuration
LIMITLESS__SEARCH_ENABLED=true
LIMITLESS__SEARCH_WEIGHT=0.75

# LLM Configuration
LLM_PROVIDER=ollama
OLLAMA_MODEL=mistral:latest

# Embedding Processing
EMBEDDING_PROCESSING_ENABLED=true
EMBEDDING_PROCESSING_INTERVAL_HOURS=6
EMBEDDING_STARTUP_BURST_ENABLED=true
EMBEDDING_STARTUP_BURST_LIMIT=150

# Logging
LOG_LEVEL=INFO
LOG_CONSOLE_LOGGING=true
```

### High-Performance Configuration
```env
# Core settings
LIMITLESS_API_KEY=your_actual_api_key_here
TIME_ZONE=Europe/London
LIMITLESS_SYNC_INTERVAL_HOURS=1

# Enhanced search for latest data
LIMITLESS__SEARCH_ENABLED=true
LIMITLESS__SEARCH_WEIGHT=0.6

# Use OpenAI for better responses
LLM_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4

# Faster embedding processing
EMBEDDING_PROCESSING_INTERVAL_HOURS=2
EMBEDDING_PROCESSING_BATCH_SIZE=200
EMBEDDING_MODEL=all-mpnet-base-v2
EMBEDDING_DEVICE=cuda  # If you have a GPU
EMBEDDING_STARTUP_BURST_ENABLED=true
EMBEDDING_STARTUP_BURST_LIMIT=300

# Enhanced chat
CHAT_CONTEXT_WINDOW=8000
OPENAI_MAX_TOKENS=2000
```

## Usage

### Chat Interface
Access the chat interface at `http://localhost:8000/chat` to ask questions about your personal data:

**Examples:**
- `"What did I discuss about work this week?"`
- `"Show me conversations about travel plans"`
- `"place bob recommended at dinner"` (semantic search)
- `"blue OR red"` (boolean keyword search)

### Search Capabilities
Lifeboard uses a 3-way hybrid search system:

1. **Limitless API Search** (75% by default): Real-time search of your latest data
2. **Local Vector Search** (12.5% by default): Semantic similarity using AI embeddings
3. **Local SQL Search** (12.5% by default): Keyword-based search of synced data

### API Endpoints
- `GET /health` - System health check
- `GET /api/sync/status` - View sync status for all sources
- `POST /api/sync/limitless` - Trigger immediate data sync
- `GET /chat` - Access web chat interface

## Architecture Notes

- **3-Way Hybrid Search**: Combines real-time Limitless API search, local semantic search, and keyword search for comprehensive results
- **Startup Embedding Burst**: Processes 150 most recent items on startup for immediate semantic search capability
- **Intelligent Fallback**: Chat works immediately with API + keyword search, enhanced by local vector search as embeddings are processed
- **Data Sync**: Runs independently from embedding processing for faster data ingestion
- **Progressive Enhancement**: System starts with API and keyword search, becomes more powerful as local embeddings are built
- **Resource Management**: Separate intervals allow balancing performance vs resource usage
- **Configurable Weights**: Adjust search distribution between API search (75% default) and local data sources (25% default)
- **Graceful Degradation**: If API search fails, automatically falls back to local vector + SQL search
- **Real-Time Access**: API search provides access to latest data not yet synced locally