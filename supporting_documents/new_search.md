# Title-Only Document Search Design

## Problem Statement

The current document search functionality searches both document titles and content, causing unexpected results. For example, when searching "DEFAULT", all documents appear instead of just "DEFAULT SUMMARY" because the search includes content-based semantic matching.

**User Requirements:**
- Search only document titles/names (not content)
- Real-time filtering: matching results appear, non-matching disappear
- Support all document types: Folder (name), Note title, Prompt title, Link title
- Future-proof for new document types with title/name fields

## Current Implementation Analysis

### Existing Search Flow
1. **Frontend**: DocumentsView.tsx calls `/api/documents/search` API
2. **Backend**: document_service.py combines FTS + vector similarity search
3. **Database**: Searches both `title` and `content_md` fields via FTS5
4. **Result**: Returns documents matching title OR content

### Why Current Search Fails User Expectations
```sql
-- Current FTS5 table includes both fields
CREATE VIRTUAL TABLE user_documents_fts USING fts5(
    title,
    content_md,  -- ← This causes content matching
    content=user_documents,
    content_rowid=id
)
```

The search finds "DEFAULT" in document content, not just titles.

## Solution Design

### Approach 1: Client-Side Real-Time Filtering (Recommended)

**Benefits:**
- Instant visual feedback (no API latency)
- Simple implementation
- Works with existing document data
- Perfect for current dataset sizes

**Implementation:**
```typescript
// Core filtering function
const filterDocumentsByTitle = (documents: Document[], query: string): Document[] => {
  if (!query.trim()) return documents;
  
  const lowerQuery = query.toLowerCase();
  return documents.filter(doc => {
    const searchField = getDocumentSearchableTitle(doc);
    return searchField.toLowerCase().includes(lowerQuery);
  });
};

// Future-proof document type handling
const getDocumentSearchableTitle = (doc: Document): string => {
  switch (doc.document_type) {
    case 'folder': return doc.title; // folder name
    case 'note': return doc.title;   // note title  
    case 'prompt': return doc.title; // prompt title
    case 'link': return doc.title;   // link title
    default: return doc.title;       // future document types
  }
};

// Updated search handler
const handleSearch = useMemo(
  () => debounce(() => {
    if (!searchQuery.trim()) {
      setDocuments(allDocuments);
      return;
    }
    
    const filtered = filterDocumentsByTitle(allDocuments, searchQuery);
    setDocuments(filtered);
  }, 150),
  [allDocuments, searchQuery]
);
```

### Approach 2: Backend Title-Only API (Future Enhancement)

**Purpose:** Handle large datasets (>100 documents) where client-side filtering becomes slow

**New Endpoint:** `GET /api/documents/search/titles`
```typescript
// Request parameters
interface TitleSearchParams {
  q: string;                    // search query
  document_type?: string;       // filter by type
  limit?: number;              // pagination
  offset?: number;             // pagination
}

// Response format
interface TitleSearchResponse {
  results: Document[];
  total: number;
  query: string;
}
```

**Backend Implementation:**
```python
async def search_documents_by_title(
    self, 
    query: str, 
    document_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> List[Document]:
    """Search documents by title only (no content matching)"""
    
    # Prepare SQL with title-only search
    sql_conditions = ["title LIKE ?"]
    params = [f"%{query}%"]
    
    if document_type:
        sql_conditions.append("document_type = ?")
        params.append(document_type)
    
    # Prioritize exact matches, then partial matches
    sql = f"""
        SELECT * FROM user_documents 
        WHERE {' AND '.join(sql_conditions)}
        ORDER BY 
            CASE 
                WHEN LOWER(title) = LOWER(?) THEN 0
                WHEN LOWER(title) LIKE LOWER(?) THEN 1 
                ELSE 2 
            END,
            title
        LIMIT ? OFFSET ?
    """
    
    # Add exact match parameters for sorting
    params.extend([query, f"{query}%", limit, offset])
    
    # Execute query and return documents
    # ... implementation details
```

### Approach 3: Hybrid Solution (Optimal)

**Strategy:** Start with client-side, scale to server-side
```typescript
const useSmartSearch = (documents: Document[], query: string) => {
  const [searchResults, setSearchResults] = useState<Document[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  
  useEffect(() => {
    if (!query.trim()) {
      setSearchResults(documents);
      return;
    }
    
    // Small dataset: client-side filtering
    if (documents.length <= 100) {
      const filtered = filterDocumentsByTitle(documents, query);
      setSearchResults(filtered);
    } 
    // Large dataset: server-side API
    else {
      setIsLoading(true);
      searchTitlesAPI(query).then(results => {
        setSearchResults(results);
        setIsLoading(false);
      });
    }
  }, [documents, query]);
  
  return { searchResults, isLoading };
};
```

## Implementation Plan

### Phase 1: Core Client-Side Implementation
1. **Update DocumentsView.tsx**
   - Replace API-based search with client-side filtering
   - Implement `filterDocumentsByTitle` function
   - Add `getDocumentSearchableTitle` helper
   - Maintain existing debounce behavior (300ms)
   - Preserve document type filtering

2. **Test Implementation**
   - Verify "DEFAULT" only shows "DEFAULT SUMMARY"
   - Test with user's documents: "scot", "fred", "DEFAULT SUMMARY"
   - Confirm all document types work correctly

### Phase 2: Backend API Enhancement (Future)
1. **Add Title-Only Search Endpoint**
   - Create `/api/documents/search/titles` route
   - Implement SQL-only title search in document service
   - Add exact match prioritization
   - Include pagination support

2. **API Integration**
   - Add server-side search option to frontend
   - Implement dataset size detection
   - Create seamless fallback mechanism

### Phase 3: Optimization & Polish
1. **Performance Enhancements**
   - Add search result highlighting
   - Implement search analytics
   - Optimize for large datasets

2. **Future-Proofing**
   - Create extensible document type configuration
   - Add support for custom search fields
   - Implement search preferences

## Expected User Experience

### Before (Current Behavior)
```
User types: "DEFAULT"
Result: Shows all documents (fred, scot, DEFAULT SUMMARY)
Reason: Content matching finds "DEFAULT" in document text
```

### After (New Behavior)  
```
User types: "DEFAULT"
Result: Shows only "DEFAULT SUMMARY"
Reason: Title-only matching finds exact title match

User types: "sco"
Result: Shows only "scot"
Reason: Partial title matching

User types: "xyz"  
Result: Shows no documents
Reason: No titles contain "xyz"
```

## Technical Specifications

### Frontend Changes
- **File**: `frontend/src/components/DocumentsView.tsx`
- **Changes**: Replace `handleSearch` function, add filtering utilities
- **Dependencies**: No new dependencies required
- **Testing**: Manual testing with user's specific documents

### Backend Changes (Future)
- **Files**: `services/document_service.py`, `api/routes/documents.py`
- **Changes**: Add title-only search methods and API endpoints
- **Dependencies**: No new dependencies required
- **Testing**: Unit tests for title-only search functionality

### Database Considerations
- **Current**: No schema changes required
- **Future**: Consider adding title-specific indexes for performance
- **Migration**: None required for Phase 1

## Success Criteria

1. **Functional Requirements**
   - ✅ Search "DEFAULT" shows only "DEFAULT SUMMARY"
   - ✅ Search "sco" shows only "scot" 
   - ✅ Search "fred" shows only "fred"
   - ✅ Works for all document types (folder, note, prompt, link)

2. **Performance Requirements**
   - ✅ Instant visual feedback (client-side filtering)
   - ✅ Debounced search input (150-300ms)
   - ✅ No API calls for basic filtering

3. **Future-Proofing Requirements**
   - ✅ Extensible for new document types
   - ✅ Scalable to server-side search when needed
   - ✅ Maintainable code structure

## Risks & Mitigations

### Risk: Large Dataset Performance
**Mitigation:** Hybrid approach with server-side fallback

### Risk: User Expectations Change  
**Mitigation:** Make search mode configurable (title vs full-content)

### Risk: Complex Document Types
**Mitigation:** Extensible document type configuration system

## Conclusion

This design provides a simple, effective solution to the user's immediate need while building a foundation for future enhancements. The client-side filtering approach offers instant feedback and perfect user experience for current dataset sizes, with clear upgrade paths for scalability.