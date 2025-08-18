# User Documents Feature Implementation Plan

## Overview
Implement a comprehensive document creation and editing system within Lifeboard using **Quill.js** as the rich text editor. Documents will be stored using Quill's Delta format + Markdown conversion and integrated with the existing unified data flow and vector search capabilities.

## Architecture Integration

**Core Strategy**: Leverage Lifeboard's existing unified data architecture (`data_items` table + vector store) by treating user documents as another data source with namespace `user_docs`.

**Editor Choice**: **Quill.js** - API-driven rich text editor with native Delta format support, perfect for our dual-storage approach.

**Navigation Enhancement**: Add single "Notes & Prompts" button to main navigation: `|Day|Calendar|Notes & Prompts|Settings`

## Implementation Phases

### Phase 1: Database Schema & Core Models
**Files to Create/Modify**:
- New migration: `core/migrations/versions/0009_add_user_documents.py`
- New models in `config/models.py` for document configuration
- New service: `services/document_service.py`

**Database Changes**:
- Add `user_documents` table for document metadata and content
- Add `document_type` field to distinguish between 'note' and 'prompt' documents
- Add FTS5 virtual table for keyword search
- Add document management methods to DatabaseService

### Phase 2: Document Service & API Layer
**Files to Create/Modify**:
- `services/document_service.py` - Core document management with Delta<->Markdown conversion
- `api/routes/documents.py` - REST API endpoints
- `sources/document_source.py` - DataItem integration for vector search

**API Endpoints**:
- `POST /api/documents` - Create document (accepts Delta format + type)
- `PUT /api/documents/{id}` - Update document (Delta format)
- `GET /api/documents` - List documents (with type filtering)
- `GET /api/documents/{id}` - Get specific document (returns Delta + metadata)
- `DELETE /api/documents/{id}` - Delete document
- `GET /api/documents/search` - Search documents (keyword + semantic)

### Phase 3: Frontend Navigation & Unified Document Page
**Files to Create/Modify**:
- `frontend/src/components/DateNavigation.tsx` - Add "Notes & Prompts" button
- `frontend/src/components/DocumentEditor.tsx` - Quill.js React integration
- `frontend/src/components/DocumentList.tsx` - Document management with type filtering
- `frontend/src/pages/DocumentsPage.tsx` - Unified Notes & Prompts page
- `frontend/src/hooks/useDocuments.ts` - Document API integration
- Update routing in `App.tsx` to handle new page

**Navigation Update**:
```typescript
// DateNavigation.tsx enhancement:
// Current: |Day|Calendar|Settings|
// Updated: |Day|Calendar|Notes & Prompts|Settings|
```

**Unified Page Structure**:
- **Single Page**: Combined Notes and Prompts management
- **Tab System**: Toggle between "Notes" and "Prompts" views within same page
- **Document Types**: Backend distinguishes between note/prompt documents
- **Shared Editor**: Same Quill.js editor for both document types

### Phase 4: Quill.js Editor Integration
**Files to Create/Modify**:
- Install Quill.js dependencies in `frontend/package.json`
- `frontend/src/components/QuillEditor.tsx` - Custom Quill wrapper
- `frontend/src/styles/` - Quill theme customization
- `frontend/src/utils/deltaUtils.ts` - Delta<->Markdown conversion

**Quill.js Integration**:
```typescript
// Key components:
- React-Quill wrapper component
- Delta format handling for save/load
- Custom toolbar configuration appropriate for both notes and prompts
- Auto-save with Delta change detection
- Document versioning via Delta operations
```

**Frontend Dependencies**:
- `react-quill` - Official React wrapper for Quill.js
- `quill-delta` - Delta format utilities
- Quill.js themes and modules

### Phase 5: Search Integration & Testing
**Files to Create/Modify**:
- Update `services/chat_service.py` to include document context
- Delta-to-Markdown conversion utilities
- Comprehensive test suite covering Delta operations
- Update documentation

**Integration Points**:
- Document content accessible via LLM chat interface using Markdown conversion
- Unified search across documents + other data sources
- Document mentions in conversation patterns

## Technical Specifications

### Navigation Flow
1. **Day View**: Current day overview (existing)
2. **Calendar View**: Month/week calendar (existing)
3. **Notes & Prompts View**: Unified document management interface (NEW)
4. **Settings View**: Configuration (existing)

### Document Types
- **Notes**: Personal documents, journal entries, thoughts
- **Prompts**: Template prompts, reusable content, AI interaction templates
- **Shared Storage**: Same table with `document_type` field to distinguish
- **Shared Interface**: Same editor and management UI with filtering

### Data Flow
1. **Document Creation/Edit**: User selects type → edits in Quill → Save Delta JSON + convert to Markdown → Store with type
2. **Document Loading**: Fetch Delta from database → Load into Quill editor
3. **Vector Integration**: Markdown content → Generate DataItem objects → Standard ingestion pipeline
4. **Search**: Keyword (FTS5) + Semantic (Vector) → Merge results → Filter by type if needed

### Storage Strategy
- **Primary Storage**: `user_documents.content_delta` (Quill Delta JSON)
- **Document Type**: `user_documents.document_type` ('note' | 'prompt')
- **Search Storage**: `user_documents.content_md` (Markdown) + FTS5 virtual table
- **Vector Storage**: Chunked Markdown in existing vector store
- **Metadata**: Document ID, user ID, title, type, timestamps, Delta version

### UI/UX Design
- **Single Button**: "Notes & Prompts" in navigation
- **Tabbed Interface**: Switch between Notes and Prompts within same page
- **Consistent Styling**: Match existing Lifeboard design patterns
- **Shared Editor**: Same Quill.js editor for both document types
- **Type-Specific Features**: Different templates/toolbars based on document type
- **Auto-save**: Real-time saving with visual feedback

## Dependencies
```json
{
  "react-quill": "^2.0.0",
  "quill": "^1.3.7",
  "quill-delta": "^5.1.0"
}
```

## File Structure
```
frontend/src/
├── pages/
│   └── DocumentsPage.tsx     # Unified Notes & Prompts page
├── components/
│   ├── DateNavigation.tsx    # Updated with "Notes & Prompts" button
│   ├── DocumentEditor.tsx    # Quill.js editor component
│   ├── DocumentList.tsx      # Document management with type filtering
│   └── QuillEditor.tsx       # Custom Quill wrapper
└── hooks/
    └── useDocuments.ts       # Document API integration
```

## Success Criteria
- Navigation includes single "Notes & Prompts" button in correct position
- Unified page allows users to create and manage both notes and prompts
- Document type filtering works seamlessly within the interface
- Rich text editing with Quill.js for both document types
- Documents stored in Delta format with Markdown conversion
- Both keyword and semantic search work across all document types
- Document content accessible to LLM for contextual assistance
- Performance targets: <200ms for document operations, <500ms for search

## Implementation Status

### ✅ Phase 0: Planning
- [x] Create comprehensive implementation plan
- [x] Define architecture and integration strategy
- [x] Document technical specifications

### 🔄 Phase 1: Database Schema & Core Models
- [ ] Create database migration for user documents
- [ ] Add document models to config
- [ ] Update DatabaseService with document methods

### ⏳ Phase 2: Document Service & API Layer
- [ ] Create document service
- [ ] Create documents API routes
- [ ] Implement DataItem integration

### ⏳ Phase 3: Frontend Navigation & Page
- [ ] Update DateNavigation with Notes & Prompts button
- [ ] Create unified DocumentsPage component
- [ ] Implement document management UI

### ⏳ Phase 4: Quill.js Integration
- [ ] Install Quill.js dependencies
- [ ] Create Quill editor components
- [ ] Implement Delta handling utilities

### ⏳ Phase 5: Search & Testing
- [ ] Integrate search functionality
- [ ] Add comprehensive test coverage
- [ ] Update chat service for document context