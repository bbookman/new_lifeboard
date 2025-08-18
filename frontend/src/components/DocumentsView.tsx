import { useState, useEffect, useRef } from 'react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from './ui/dialog';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from './ui/alert-dialog';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Plus, Search, FileText, Edit3, Trash2, File, ScrollText, MoreVertical, ChevronDown, ChevronRight } from 'lucide-react';
import ReactQuill from 'react-quill';
import 'react-quill/dist/quill.snow.css';
import './quill-theme.css';

interface Document {
  id: string;
  user_id: string;
  title: string;
  document_type: 'note' | 'prompt';
  content_delta: any;
  content_md: string;
  created_at: string;
  updated_at: string;
  selected?: boolean;
}

interface DocumentListResponse {
  documents: Document[];
  total: number;
  limit: number;
  offset: number;
}

export const DocumentsView = () => {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedType, setSelectedType] = useState<'all' | 'note' | 'prompt'>('all');
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [showDeleteSelectedDialog, setShowDeleteSelectedDialog] = useState(false);
  const [viewMode, setViewMode] = useState<'list' | 'document'>('list');
  const [openDocument, setOpenDocument] = useState<Document | null>(null);
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(null);
  const [sortBy, setSortBy] = useState<'name' | 'type' | 'modified'>('modified');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [isEditing, setIsEditing] = useState(false);
  const [allSelected, setAllSelected] = useState(false);
  const [hasSelectedDocuments, setHasSelectedDocuments] = useState(false);
  const [createForm, setCreateForm] = useState({
    title: '',
    document_type: 'note' as 'note' | 'prompt',
    content: ''
  });
  const [createFormDelta, setCreateFormDelta] = useState<any>(null);
  const createQuillRef = useRef<ReactQuill>(null);
  const [editForm, setEditForm] = useState({
    title: '',
    document_type: 'note' as 'note' | 'prompt',
    content: ''
  });
  const [editFormDelta, setEditFormDelta] = useState<any>(null);
  const quillRef = useRef<ReactQuill>(null);

  // Quill configuration for Markdown-compatible editing
  const quillModules = {
    toolbar: [
      [{ 'header': [1, 2, 3, false] }],
      ['bold', 'italic', 'code'],
      [{ 'list': 'ordered'}, { 'list': 'bullet' }],
      ['blockquote', 'code-block'],
      ['link'],
      ['clean']
    ],
  };

  const quillFormats = [
    'header', 'bold', 'italic', 'code',
    'list', 'bullet', 'ordered',
    'blockquote', 'code-block', 'link'
  ];

  useEffect(() => {
    fetchDocuments();
  }, [selectedType]);

  useEffect(() => {
    setHasSelectedDocuments(documents.some(doc => doc.selected));
  }, [documents]);

  const fetchDocuments = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const params = new URLSearchParams();
      if (selectedType !== 'all') {
        params.append('document_type', selectedType);
      }
      params.append('limit', '50');
      
      const response = await fetch(`http://localhost:8000/api/documents?${params}`);
      if (!response.ok) {
        throw new Error('Failed to fetch documents');
      }
      
      const data: DocumentListResponse = await response.json();
      setDocuments(data.documents.map(doc => ({ ...doc, selected: false })));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load documents');
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      fetchDocuments();
      return;
    }

    try {
      setLoading(true);
      setError(null);
      
      const params = new URLSearchParams();
      params.append('q', searchQuery);
      if (selectedType !== 'all') {
        params.append('document_type', selectedType);
      }
      params.append('limit', '20');
      
      const response = await fetch(`http://localhost:8000/api/documents/search?${params}`);
      if (!response.ok) {
        throw new Error('Search failed');
      }
      
      const data = await response.json();
      setDocuments(data.results.map((result: any) => ({ ...result.document, selected: false })));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed');
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const getTypeColor = (type: string) => {
    return type === 'note' ? 'bg-blue-100 text-blue-800' : 'bg-purple-100 text-purple-800';
  };

  const getPreviewText = (content: string) => {
    return content.length > 150 ? content.substring(0, 150) + '...' : content;
  };

  const getFileIcon = (type: string) => {
    return type === 'note' ? <File className="h-4 w-4 text-blue-600" /> : <ScrollText className="h-4 w-4 text-purple-600" />;
  };

  const getFileSize = (content: string) => {
    const bytes = new Blob([content]).size;
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const sortedDocuments = [...documents].sort((a, b) => {
    let comparison = 0;
    
    switch (sortBy) {
      case 'name':
        comparison = a.title.localeCompare(b.title);
        break;
      case 'type':
        comparison = a.document_type.localeCompare(b.document_type);
        break;
      case 'modified':
        comparison = new Date(a.updated_at).getTime() - new Date(b.updated_at).getTime();
        break;
      case 'created':
        comparison = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
        break;
    }
    
    return sortOrder === 'asc' ? comparison : -comparison;
  });

  const handleSort = (column: 'name' | 'type' | 'modified' | 'created') => {
    if (sortBy === column) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(column);
      setSortOrder('asc');
    }
  };

  const handleSelectAll = (event: React.ChangeEvent<HTMLInputElement>) => {
    const checked = event.target.checked;
    setAllSelected(checked);
    setDocuments(prev => prev.map(doc => ({ ...doc, selected: checked })));
  };

  const handleSelectDocument = (id: string, event: React.ChangeEvent<HTMLInputElement>) => {
    const checked = event.target.checked;
    setDocuments(prev => prev.map(doc =>
      doc.id === id ? { ...doc, selected: checked } : doc
    ));
    // Update allSelected state based on whether all documents are now selected
    setAllSelected(documents.every(doc => doc.id === id ? checked : doc.selected));
  };

  const handleDeleteSelected = () => {
    setShowDeleteSelectedDialog(true);
  };

  const handleDocumentClick = (document: Document) => {
    // Open document in full-screen view
    setOpenDocument(document);
    setViewMode('document');
    
    // Set up both Delta and plain text content for editing
    let plainTextContent = '';
    if (document.content_delta?.ops) {
      plainTextContent = document.content_delta.ops
        .map((op: any) => typeof op.insert === 'string' ? op.insert : '')
        .join('')
        .replace(/\n$/, ''); // Remove trailing newline
    }
    
    setEditForm({
      title: document.title,
      document_type: document.document_type,
      content: plainTextContent
    });
    setEditFormDelta(document.content_delta);
    setIsEditing(true); // Start in edit mode when clicking on document
  };

  const handleBackToList = () => {
    setViewMode('list');
    setOpenDocument(null);
    setIsEditing(false);
    setEditForm({ title: '', document_type: 'note', content: '' });
    setError(null);
  };

  const handleStartEdit = () => {
    if (openDocument) {
      // Convert Delta content back to plain text for editing
      let plainTextContent = '';
      if (openDocument.content_delta?.ops) {
        plainTextContent = openDocument.content_delta.ops
          .map((op: any) => typeof op.insert === 'string' ? op.insert : '')
          .join('')
          .replace(/\n$/, ''); // Remove trailing newline
      }
      
      setEditForm({
        title: openDocument.title,
        document_type: openDocument.document_type,
        content: plainTextContent
      });
      setIsEditing(true);
    }
  };

  const handleCancelEdit = () => {
    // Always go back to document list when clicking cancel
    handleBackToList();
  };

  const handleQuillChange = (content: string, delta: any, source: string, editor: any) => {
    setEditFormDelta(editor.getContents());
  };

  const handleCreateQuillChange = (content: string, delta: any, source: string, editor: any) => {
    setCreateFormDelta(editor.getContents());
  };

  const handleSaveEdit = async () => {
    if (!openDocument || !editForm.title.trim()) {
      setError('Title is required');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      // Get the current Delta content from Quill editor
      const quillEditor = quillRef.current?.getEditor();
      const deltaContent = quillEditor ? quillEditor.getContents() : editFormDelta;

      if (!deltaContent) {
        setError('Unable to save content');
        return;
      }

      const response = await fetch(`http://localhost:8000/api/documents/${openDocument.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          title: editForm.title,
          content_delta: deltaContent
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to update document');
      }

      const updatedDocument: Document = await response.json();
      setDocuments(prev => prev.map(doc => 
        doc.id === openDocument.id ? updatedDocument : doc
      ));
      setOpenDocument(updatedDocument); // Update the open document with latest data
      setIsEditing(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update document');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateFromFullView = async () => {
    if (!editForm.title.trim()) {
      setError('Title is required');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      // Get the current Delta content from Quill editor
      const quillEditor = quillRef.current?.getEditor();
      const deltaContent = quillEditor ? quillEditor.getContents() : editFormDelta || {
        ops: [{ insert: '\n' }]
      };

      const response = await fetch('http://localhost:8000/api/documents', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          title: editForm.title,
          document_type: editForm.document_type,
          content_delta: deltaContent
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to create document');
      }

      const newDocument: Document = await response.json();
      setDocuments(prev => [newDocument, ...prev]);
      
      // Switch to viewing the newly created document
      setOpenDocument(newDocument);
      setIsEditing(false);
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create document');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateDocument = async () => {
    if (!createForm.title.trim()) {
      setError('Title is required');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      // Get the current Delta content from Create Quill editor
      const createQuillEditor = createQuillRef.current?.getEditor();
      const deltaContent = createQuillEditor ? createQuillEditor.getContents() : createFormDelta || {
        ops: [{ insert: '\n' }]
      };

      const response = await fetch('http://localhost:8000/api/documents', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          title: createForm.title,
          document_type: createForm.document_type,
          content_delta: deltaContent
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to create document');
      }

      const newDocument: Document = await response.json();
      setDocuments(prev => [newDocument, ...prev]);
      setShowCreateDialog(false);
      setCreateForm({ title: '', document_type: 'note', content: '' });
      setCreateFormDelta(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create document');
    } finally {
      setLoading(false);
    }
  };

  const openCreateDialog = () => {
    // Instead of showing dialog, open full editor for new document
    setViewMode('document');
    setOpenDocument(null); // No existing document
    setIsEditing(true);
    setEditForm({
      title: '',
      document_type: 'note',
      content: ''
    });
    setEditFormDelta(null);
    setError(null);
  };


  const openDeleteDialog = (document: Document) => {
    setSelectedDocument(document);
    setShowDeleteDialog(true);
    setError(null);
  };


  const handleDeleteDocument = async () => {
    if (!selectedDocument) return;

    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`http://localhost:8000/api/documents/${selectedDocument.id}`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error('Failed to delete document');
      }

      setDocuments(prev => prev.filter(doc => doc.id !== selectedDocument.id));
      setShowDeleteDialog(false);
      setSelectedDocument(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete document');
    } finally {
      setLoading(false);
    }
  };

  const confirmDeleteSelectedDocuments = async () => {
    const selectedDocumentIds = documents.filter(doc => doc.selected).map(doc => doc.id);
    if (selectedDocumentIds.length === 0) return;

    try {
      setLoading(true);
      setError(null);

      await Promise.all(selectedDocumentIds.map(id =>
        fetch(`http://localhost:8000/api/documents/${id}`, {
          method: 'DELETE',
          headers: {
            'Content-Type': 'application/json',
          },
        })
      ));

      setDocuments(prev => prev.filter(doc => !doc.selected));
      setAllSelected(false);
      setHasSelectedDocuments(false);
      setShowDeleteSelectedDialog(false); // Close the modal after deletion

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete selected documents');
    } finally {
      setLoading(false);
    }
  };

  // Render full-screen document view (both edit existing and create new)
  if (viewMode === 'document') {
    return (
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Document Header */}
        <div className="flex justify-between items-start">
          <div className="flex items-center gap-4">
            <Button onClick={handleBackToList} variant="outline" size="sm">
              ← Back to Documents
            </Button>
          </div>
          <div className="flex items-center gap-2">
            {!isEditing ? (
              <>
                <Button onClick={handleStartEdit} variant="outline" size="sm">
                  <Edit3 className="h-4 w-4 mr-1" />
                  Edit
                </Button>
                {openDocument && (
                  <Button 
                    onClick={(e) => {
                      e.stopPropagation();
                      openDeleteDialog(openDocument);
                    }}
                    variant="outline" 
                    size="sm"
                    className="text-destructive hover:text-destructive"
                  >
                    <Trash2 className="h-4 w-4 mr-1" />
                    Delete
                  </Button>
                )}
              </>
            ) : (
              <>
                <Button onClick={handleCancelEdit} variant="outline" size="sm">
                  Cancel
                </Button>
                <Button 
                  onClick={openDocument ? handleSaveEdit : handleCreateFromFullView}
                  disabled={!editForm.title.trim()}
                  size="sm"
                  className="bg-primary text-primary-foreground hover:bg-primary/90"
                >
                  Save
                </Button>
                {openDocument && (
                  <Button 
                    onClick={(e) => {
                      e.stopPropagation();
                      openDeleteDialog(openDocument);
                    }}
                    variant="outline" 
                    size="sm"
                    className="text-destructive hover:text-destructive"
                  >
                    <Trash2 className="h-4 w-4 mr-1" />
                    Delete
                  </Button>
                )}
              </>
            )}
          </div>
        </div>

        {/* Error Display */}
        {error && (
          <div className="bg-destructive/15 border border-destructive/20 rounded-lg p-4">
            <p className="text-destructive">{error}</p>
          </div>
        )}

        {/* Document Content */}
        <div className="border rounded-lg bg-card">
          {!isEditing ? (
            // Read-only WYSIWYG view
            <div className="p-6">
              <div className="prose prose-slate max-w-none">
                <h1 className="text-3xl font-bold tracking-tight mb-6">{openDocument?.title}</h1>
                <ReactQuill
                  value={openDocument?.content_delta || { ops: [{ insert: '\n' }] }}
                  readOnly={true}
                  modules={{ toolbar: false }}
                  theme="bubble"
                  className="quill-readonly"
                />
              </div>
            </div>
          ) : (
            // Edit mode - Full editing interface
            <div className="p-6 space-y-6">
              {/* Title and Type Section */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="md:col-span-3">
                  <Label htmlFor="doc-title" className="text-base font-semibold mb-2 block">
                    Document Title
                  </Label>
                  <Input
                    id="doc-title"
                    value={editForm.title}
                    onChange={(e) => setEditForm(prev => ({ ...prev, title: e.target.value }))}
                    className="text-lg p-3"
                    placeholder="Enter document title..."
                  />
                </div>
                
              </div>
              
              {/* Content Section */}
              <div className="flex-1">
                <Label className="text-base font-semibold mb-2 block">
                  Content
                </Label>
                <div className="border rounded-lg overflow-hidden">
                  <ReactQuill
                    ref={quillRef}
                    value={editFormDelta}
                    onChange={handleQuillChange}
                    modules={quillModules}
                    formats={quillFormats}
                    placeholder="Start writing your content here..."
                    style={{ minHeight: '400px' }}
                    theme="snow"
                  />
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Loading indicator for save operations */}
        {loading && (
          <div className="text-center py-4">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary mx-auto"></div>
            <p className="mt-2 text-sm text-muted-foreground">Saving...</p>
          </div>
        )}
      </div>
    );
  }

  // Render list view
  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <Button onClick={openCreateDialog} className="flex items-center gap-2">
          <Plus className="h-4 w-4" />
          New Document
        </Button>
      </div>

      {/* Search and Filters */}
      <div className="flex gap-4 items-center">
        <div className="flex-1 flex gap-2">
          <Input
            placeholder="Search documents..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
            className="flex-1"
          />
          <Button onClick={handleSearch} variant="outline" size="icon">
            <Search className="h-4 w-4" />
          </Button>
        </div>
        
        
      </div>

      {/* Loading State */}
      {loading && (
        <div className="text-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto"></div>
          <p className="mt-2 text-muted-foreground">Loading documents...</p>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="bg-destructive/15 border border-destructive/20 rounded-lg p-4">
          <p className="text-destructive">{error}</p>
          <Button onClick={fetchDocuments} variant="outline" size="sm" className="mt-2">
            Try Again
          </Button>
        </div>
      )}

      

      {/* File System Style List View */}
      {!loading && !error && documents.length > 0 && (
        <div className="space-y-6">
          {/* File List Header */}
          <div className="border rounded-lg bg-card">
            <div className="grid grid-cols-12 gap-4 p-3 border-b bg-muted/50 text-sm font-medium text-muted-foreground">
              <div className="col-span-1 flex items-center gap-2">
                <input
                  type="checkbox"
                  className="form-checkbox h-4 w-4 text-primary rounded"
                  checked={allSelected}
                  onChange={handleSelectAll}
                />
                <Button
                  variant="ghost"
                  size="sm"
                  className="p-0 h-auto w-auto"
                  disabled={!hasSelectedDocuments}
                  onClick={handleDeleteSelected}
                >
                  <Trash2 className="h-4 w-4 text-muted-foreground" />
                </Button>
              </div>
              <div className="col-span-4 flex items-center gap-2 cursor-pointer hover:text-foreground" onClick={() => handleSort('name')}>
                Name
                {sortBy === 'name' && (sortOrder === 'asc' ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />)}
              </div>
              <div className="col-span-2 cursor-pointer hover:text-foreground" onClick={() => handleSort('type')}>
                Type
                {sortBy === 'type' && (sortOrder === 'asc' ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />)}
              </div>
              <div className="col-span-2 cursor-pointer hover:text-foreground" onClick={() => handleSort('created')}>
                Created
                {sortBy === 'created' && (sortOrder === 'asc' ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />)}
              </div>
              <div className="col-span-2 cursor-pointer hover:text-foreground" onClick={() => handleSort('modified')}>
                Modified
                {sortBy === 'modified' && (sortOrder === 'asc' ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />)}
              </div>
              <div className="col-span-1"></div>
            </div>
            
            {/* File List Items */}
            {sortedDocuments.map((doc) => (
              <div key={doc.id} className="border-b last:border-b-0">
                <div 
                  className="grid grid-cols-12 gap-4 p-3 hover:bg-muted/50 cursor-pointer transition-colors"
                  onClick={() => handleDocumentClick(doc)}
                >
                  <div className="col-span-1 flex items-center">
                    <input
                      type="checkbox"
                      className="form-checkbox h-4 w-4 text-primary rounded"
                      checked={doc.selected || false}
                      onChange={(e) => handleSelectDocument(doc.id, e)}
                      onClick={(e) => e.stopPropagation()} // Prevent document click when checkbox is clicked
                    />
                  </div>
                  <div className="col-span-4 flex items-center gap-2 min-w-0">
                    {getFileIcon(doc.document_type)}
                    <span className="truncate font-medium">{doc.title}</span>
                  </div>
                  <div className="col-span-2 flex items-center">
                    <Badge variant="outline" className={getTypeColor(doc.document_type)}>
                      {doc.document_type}
                    </Badge>
                  </div>
                  <div className="col-span-2 flex items-center text-sm text-muted-foreground">
                    {formatDate(doc.created_at)}
                  </div>
                  <div className="col-span-2 flex items-center text-sm text-muted-foreground">
                    {formatDate(doc.updated_at)}
                  </div>
                  
                  <div className="col-span-1 flex items-center justify-end">
                    <Button 
                      variant="ghost" 
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        openDeleteDialog(doc);
                      }}
                      title="Delete document"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Create Document Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent className="sm:max-w-[525px]">
          <DialogHeader>
            <DialogTitle>Create New Document</DialogTitle>
            <DialogDescription>
              Create a new note or prompt document.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="title" className="text-right">
                Title
              </Label>
              <Input
                id="title"
                value={createForm.title}
                onChange={(e) => setCreateForm(prev => ({ ...prev, title: e.target.value }))}
                className="col-span-3"
                placeholder="Enter document title..."
              />
            </div>
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="type" className="text-right">
                Type
              </Label>
              <Select
                value={createForm.document_type}
                onValueChange={(value: 'note' | 'prompt') => 
                  setCreateForm(prev => ({ ...prev, document_type: value }))
                }
              >
                <SelectTrigger className="col-span-3">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="note">Note</SelectItem>
                  <SelectItem value="prompt">Prompt</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-4 items-start gap-4">
              <Label className="text-right pt-2">
                Content
              </Label>
              <div className="col-span-3 border rounded-lg overflow-hidden">
                <ReactQuill
                  ref={createQuillRef}
                  value={createFormDelta}
                  onChange={handleCreateQuillChange}
                  modules={quillModules}
                  formats={quillFormats}
                  placeholder="Enter document content..."
                  style={{ minHeight: '200px' }}
                  theme="snow"
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setShowCreateDialog(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              onClick={handleCreateDocument}
              disabled={!createForm.title.trim()}
            >
              Create Document
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>


      {/* Delete Document Confirmation Dialog */}
      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Document</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{selectedDocument?.title}"? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel 
              onClick={() => {
                setShowDeleteDialog(false);
                setSelectedDocument(null);
              }}
            >
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteDocument}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Delete Selected Documents Confirmation Dialog */}
      <AlertDialog open={showDeleteSelectedDialog} onOpenChange={setShowDeleteSelectedDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Documents</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete these documents? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel 
              onClick={() => {
                setShowDeleteSelectedDialog(false);
              }}
            >
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDeleteSelectedDocuments}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};