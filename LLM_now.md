# LLM Daily Summary Integration

## Overview

This document describes the integration of LLM-generated content into Lifeboard's top news card. The system allows users to select custom prompts for generating daily summaries using local or remote LLM providers.

## Architecture

### Components

1. **Prompt Management System**
   - Uses existing DocumentService for prompt storage and management
   - Prompts are stored as documents with `document_type="prompt"`
   - Rich text editing via existing Quill.js integration

2. **Settings Management**
   - New `prompt_settings` table tracks selected prompts
   - Settings API endpoints for prompt selection persistence
   - UI in SettingsView for prompt selection

3. **LLM Service Layer**
   - New `LLMService` wraps existing Ollama provider
   - Handles prompt fetching, context building, and generation
   - Supports multiple LLM providers (Ollama/Mistral as test case)

4. **UI Integration**
   - Top news card displays generated content
   - Real-time updates via WebSocket
   - Loading states and error handling

## Data Flow

```
User Workflow:
1. User creates prompts in Documents → stored as prompt-type documents
2. User selects prompt in Settings → saved to prompt_settings table
3. System triggers daily generation → fetches prompt → calls LLM → displays result

Technical Flow:
Settings → Document Service → LLM Service → News Card Display
    ↓              ↓              ↓              ↓
prompt_settings  user_documents  Ollama API    Frontend UI
```

## Database Schema

### New Table: prompt_settings
```sql
CREATE TABLE prompt_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    setting_key TEXT NOT NULL UNIQUE, -- e.g., 'daily_summary_prompt'
    prompt_document_id TEXT, -- References user_documents.id
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (prompt_document_id) REFERENCES user_documents(id) ON DELETE SET NULL
);
```

**Note:** This is a test database environment, so migration rollbacks are not implemented. The database can be recreated as needed during development.

### Relationships
- `prompt_settings.prompt_document_id` → `user_documents.id`
- `user_documents.document_type` = "prompt" for prompt documents

## API Endpoints

### Document Service
- `GET /api/documents?document_type=prompt` - List available prompts
- Existing endpoints for prompt creation/editing

### Settings API
- `GET /api/settings/prompt-selection` - Get current prompt selection
- `POST /api/settings/prompt-selection` - Save prompt selection
- Body: `{"prompt_document_id": "uuid"}`

### LLM Generation
- `POST /api/llm/generate-summary` - Generate daily summary
- Uses selected prompt + daily data as context
- Returns generated content for display

## Frontend Components

### SettingsView Enhancement
- Add prompt selection dropdown below Twitter upload
- Populate with prompts from DocumentService
- Save button persists selection via settings API

### NewsSection Top Card
- Display LLM-generated content instead of sample news
- Loading spinner during generation
- Error handling for LLM failures
- Real-time updates via WebSocket

## Implementation Details

### Prompt Selection Flow
1. SettingsView fetches available prompts from DocumentService
2. User selects prompt from dropdown
3. Save button calls settings API to persist choice
4. System uses selected prompt for future generations

### Content Generation Flow
1. System fetches selected prompt from prompt_settings
2. Builds context from daily data (news, weather, activities)
3. Calls LLM service with prompt + context
4. Stores/caches generated content
5. Sends update via WebSocket to frontend
6. Top card displays generated summary

### Error Handling
- LLM service unavailable → show fallback message
- No prompt selected → show configuration prompt
- Generation timeout → show retry option
- Network errors → graceful degradation

## Configuration

### Environment Variables
- Existing Ollama configuration used
- `OLLAMA_BASE_URL` - Ollama server URL (default: http://localhost:11434)
- `OLLAMA_MODEL` - Model name (default: mistral)

### Default Settings
- No prompt selected initially
- User must configure via Settings
- Graceful fallback when unconfigured

## Future Extensions

The `prompt_settings` table is designed to support multiple prompt applications:

- `daily_summary_prompt` - Current implementation
- `weather_commentary_prompt` - Future weather section enhancement
- `activity_insights_prompt` - Future activity analysis
- `weekly_reflection_prompt` - Future weekly summaries

Each prompt type can be independently configured and applied to different UI locations.

## Testing

### Test Cases
1. Prompt creation and selection via UI
2. LLM generation with various prompt types
3. Error handling (LLM down, no prompt selected)
4. Real-time updates via WebSocket
5. Settings persistence across sessions

### Test Data
- Sample prompts for daily summary generation
- Mock LLM responses for frontend testing
- Error scenarios for resilience testing

## Security Considerations

- Prompt content is user-controlled (stored in user_documents)
- LLM responses should be sanitized before display
- Rate limiting on LLM generation endpoints
- Prompt selection restricted to user's own documents

## Performance

- LLM generation is async and cached
- WebSocket updates prevent UI blocking
- Graceful degradation when LLM unavailable
- Configurable timeout for LLM requests