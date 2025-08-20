import { useState, useEffect, useRef } from 'react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from './ui/dialog';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from './ui/alert-dialog';
import { Label } from './ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { RadioGroup, RadioGroupItem } from './ui/radio-group';
import { Popover, PopoverContent, PopoverTrigger } from './ui/popover';
import { Calendar } from './ui/calendar';
import { CalendarIcon } from 'lucide-react';
import { Plus, Search, Edit3, Trash2, File, ScrollText, ChevronDown, ChevronRight, Folder, Link } from 'lucide-react';
import ReactQuill from 'react-quill';
import 'react-quill/dist/quill.snow.css';
import './quill-theme.css';

interface Document {
  id: string;
  title: string;
  document_type: 'note' | 'prompt' | 'folder' | 'link';
  content_delta: any;
  content_md: string;
  path: string;
  is_folder: boolean;
  home_date: string;
  created_at: string;
  updated_at: string;
  url?: string; // For link documents
  selected?: boolean;
}

interface DocumentListResponse {
  documents: Document[];
  total: number;
  limit: number;
  offset: number;
}

interface DocumentsViewProps {
  initialFilter?: 'all' | 'note' | 'prompt' | 'folder' | 'link';
}

export const DocumentsView = ({ initialFilter = 'all' }: DocumentsViewProps) => {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [allDocuments, setAllDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedType, setSelectedType] = useState<'all' | 'note' | 'prompt' | 'link' | 'home_date' | 'none'>(initialFilter);
  const [currentFolderPath, setCurrentFolderPath] = useState<string>('/');
  const [showCreateFolderDialog, setShowCreateFolderDialog] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showDocumentTypeDialog, setShowDocumentTypeDialog] = useState(false);
  const [showLinkUrlDialog, setShowLinkUrlDialog] = useState(false);
  const [selectedDocumentType, setSelectedDocumentType] = useState<'folder' | 'note' | 'prompt' | 'link'>('folder');
  const [linkUrl, setLinkUrl] = useState('');
  const [linkTitle, setLinkTitle] = useState('');
  const [linkHomeDate, setLinkHomeDate] = useState<Date>(new Date());
  const [showEditLinkDialog, setShowEditLinkDialog] = useState(false);
  const [editingLink, setEditingLink] = useState<Document | null>(null);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [showDeleteSelectedDialog, setShowDeleteSelectedDialog] = useState(false);
  const [showUniqueNameDialog, setShowUniqueNameDialog] = useState(false);
  const [viewMode, setViewMode] = useState<'list' | 'document'>('list');
  const [openDocument, setOpenDocument] = useState<Document | null>(null);
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(null);
  const [sortBy, setSortBy] = useState<'name' | 'type' | 'modified' | 'home_date' | 'created'>('modified');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [isEditing, setIsEditing] = useState(false);
  const [allSelected, setAllSelected] = useState(false);
  const [hasSelectedDocuments, setHasSelectedDocuments] = useState(false);
  const [createForm, setCreateForm] = useState({
    title: '',
    document_type: 'note' as 'note' | 'prompt' | 'link',
    content: '',
    url: '',
    home_date: new Date()
  });
  const [createFormDelta, setCreateFormDelta] = useState<any>(null);
  const createQuillRef = useRef<ReactQuill>(null);
  const [editForm, setEditForm] = useState({
    title: '',
    document_type: 'note' as 'note' | 'prompt' | 'link',
    content: '',
    url: '',
    home_date: new Date()
  });
  const [editFormDelta, setEditFormDelta] = useState<any>(null);
  const quillRef = useRef<ReactQuill>(null);

  // Quill configuration for Markdown-compatible editing
  const quillModules = {
    toolbar: [
      [{ 'header': [1, 2, 3, false] }],
      ['bold', 'italic', 'code'],
      [{ 'list': 'ordered' }, { 'list': 'bullet' }],
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
  }, [currentFolderPath]);

  useEffect(() => {
    let filtered = allDocuments;

    // Filter by type
    if (selectedType === 'home_date') {
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      filtered = filtered.filter(doc => {
        if (!doc.home_date) return false;
        const docDate = new Date(doc.home_date);
        docDate.setHours(0, 0, 0, 0);
        return docDate.getTime() === today.getTime();
      });
    } else if (selectedType === 'notes') {
        filtered = filtered.filter(doc => doc.document_type === 'note');
    } else if (selectedType === 'prompts') {
        filtered = filtered.filter(doc => doc.document_type === 'prompt');
    } else if (selectedType === 'links') {
        filtered = filtered.filter(doc => doc.document_type === 'link');
    }

    // Filter by search query
    if (searchQuery.trim()) {
      filtered = filtered.filter(doc =>
        doc.title.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }

    setDocuments(filtered);
  }, [selectedType, allDocuments, searchQuery]);

  useEffect(() => {
    setHasSelectedDocuments(documents.some(doc => doc.selected));
  }, [documents]);

  // Listen for navigation events to force list view
  useEffect(() => {
    const handleForceList = () => {
      setViewMode('list');
      setOpenDocument(null);
      setIsEditing(false);
      setEditForm({ title: '', document_type: 'note', content: '', url: '', home_date: new Date() });
      setError(null);
    };

    window.addEventListener('forceDocumentsList', handleForceList);
    return () => window.removeEventListener('forceDocumentsList', handleForceList);
  }, []);

  // Debug useEffect to monitor delete dialog state
  useEffect(() => {
    console.log('🗑️ Delete dialog state changed:', {
      showDeleteDialog,
      selectedDocument: selectedDocument?.title || 'none'
    });
  }, [showDeleteDialog, selectedDocument]);

  // Debug useEffect to monitor unique name dialog state
  useEffect(() => {
    console.log('🚨 Unique name dialog state changed:', {
      showUniqueNameDialog,
      timestamp: new Date().toISOString()
    });
    
    // Check if modal gets reset immediately
    if (showUniqueNameDialog) {
      setTimeout(() => {
        console.log('⏰ Modal state after 100ms:', showUniqueNameDialog);
      }, 100);
      
      setTimeout(() => {
        console.log('⏰ Modal state after 500ms:', showUniqueNameDialog);
      }, 500);
    }
  }, [showUniqueNameDialog]);

  const checkUniqueTitle = async (title: string, documentType: string, excludeId?: string) => {
    console.log('🔍 checkUniqueTitle called with:', { title, documentType, excludeId });
    
    try {
      const params = new URLSearchParams();
      params.append('title', title);
      params.append('document_type', documentType);
      if (excludeId) {
        params.append('exclude_id', excludeId);
      }
      
      const response = await fetch(`http://localhost:8000/api/documents/validate-title?${params}`);
      if (!response.ok) {
        throw new Error('Failed to validate title');
      }

      const data = await response.json();
      console.log('📝 Title validation result:', data.is_unique ? 'UNIQUE' : 'DUPLICATE FOUND');
      
      return data.is_unique;
    } catch (err) {
      console.error('❌ Error checking unique title:', err);
      // If we can't check, allow the operation and let the server handle it
      return true;
    }
  };

  const fetchDocuments = async () => {
    try {
      setLoading(true);
      setError(null);

      const startTime = performance.now();

      // Performance optimization: Check count first for fast empty state detection
      const countParams = new URLSearchParams();
      countParams.append('folder_path', currentFolderPath);

      const countStart = performance.now();
      const countResponse = await fetch(`http://localhost:8000/api/documents/count?${countParams}`);
      if (!countResponse.ok) {
        throw new Error('Failed to check document count');
      }

      const countData = await countResponse.json();
      const countTime = performance.now() - countStart;
      
      // Early exit if no documents - much faster than loading full list
      if (countData.count === 0) {
        const totalTime = performance.now() - startTime;
        console.log(`📈 Fast empty detection: ${countTime.toFixed(1)}ms count, ${totalTime.toFixed(1)}ms total`);
        setAllDocuments([]);
        return;
      }

      // If documents exist, fetch the full list
      const listParams = new URLSearchParams();
      listParams.append('folder_path', currentFolderPath);
      listParams.append('limit', '50');

      const listStart = performance.now();
      const listResponse = await fetch(`http://localhost:8000/api/documents?${listParams}`);
      if (!listResponse.ok) {
        throw new Error('Failed to fetch documents');
      }

      const listData: DocumentListResponse = await listResponse.json();
      const listTime = performance.now() - listStart;
      const totalTime = performance.now() - startTime;
      
      console.log(`📊 Document loading: ${countTime.toFixed(1)}ms count, ${listTime.toFixed(1)}ms list, ${totalTime.toFixed(1)}ms total (${listData.documents.length} docs)`);
      setAllDocuments(listData.documents.map(doc => ({ ...doc, selected: false })));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load documents');
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = () => {
    // The actual filtering is now done in the useEffect hook
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const getTypeColor = (type: string) => {
    switch (type) {
      case 'note':
        return 'bg-blue-100 text-blue-800';
      case 'prompt':
        return 'bg-purple-100 text-purple-800';
      case 'link':
        return 'bg-green-100 text-green-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getPreviewText = (content: string) => {
    return content.length > 150 ? content.substring(0, 150) + '...' : content;
  };

  const getFileIcon = (type: string) => {
    switch (type) {
      case 'folder':
        return <Folder className="h-4 w-4 text-yellow-600" />;
      case 'note':
        return <File className="h-4 w-4 text-blue-600" />;
      case 'prompt':
        return <ScrollText className="h-4 w-4 text-purple-600" />;
      case 'link':
        return <Link className="h-4 w-4 text-green-600" />;
      default:
        return <File className="h-4 w-4 text-gray-600" />;
    }
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
      case 'home_date':
        comparison = new Date(a.home_date).getTime() - new Date(b.home_date).getTime();
        break;
    }

    return sortOrder === 'asc' ? comparison : -comparison;
  });

  const handleSort = (column: 'name' | 'type' | 'modified' | 'home_date' | 'created') => {
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
    console.log('📄 handleDocumentClick called with document:', document);

    if (document.is_folder) {
      // Navigate into folder
      setCurrentFolderPath(document.path);
      return;
    }

    if (document.document_type === 'link' && document.url) {
      // Open link in new tab
      window.open(document.url, '_blank');
      return;
    }

    // Open document in full-screen view
    console.log('📄 Setting openDocument to:', document.id, document.title);
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
      document_type: document.document_type as 'note' | 'prompt' | 'link',
      content: plainTextContent,
      url: document.url || '',
      home_date: new Date(document.home_date)
    });
    setEditFormDelta(document.content_delta);
    setIsEditing(true); // Start in edit mode when clicking on document
  };

  const handleBackToList = () => {
    console.log('🔙 handleBackToList called - clearing delete dialog');
    setViewMode('list');
    console.log('🔙 Setting openDocument to NULL in handleBackToList');
    setOpenDocument(null);
    setIsEditing(false);
    setEditForm({ title: '', document_type: 'note', content: '', url: '', home_date: new Date() });
    setError(null);
    // Clear any open dialogs when navigating back
    setShowDeleteDialog(false);
    setSelectedDocument(null);
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
        document_type: openDocument.document_type === 'folder' ? 'note' : openDocument.document_type,
        content: plainTextContent,
        url: openDocument.url || '',
        home_date: new Date(openDocument.home_date)
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
    try {
      console.log('🔥 SAVE BUTTON CLICKED - handleSaveEdit function started');
      console.log('💾 handleSaveEdit called with title:', editForm.title);
      
      if (!openDocument || !editForm.title.trim()) {
        console.log('❌ Validation failed: missing document or title');
        setError('Title is required');
        return;
      }

      console.log('🔍 Checking unique title for:', editForm.title, 'type:', editForm.document_type, 'excludeId:', openDocument.id);
      
      // Check for unique title
      const isUnique = await checkUniqueTitle(editForm.title, editForm.document_type, openDocument.id);
      console.log('✅ Unique check result:', isUnique);
      
      if (!isUnique) {
        console.log('🚨 Duplicate found, showing unique name dialog');
        console.log('📱 Current showUniqueNameDialog state before setting:', showUniqueNameDialog);
        setShowUniqueNameDialog(true);
        console.log('📱 setShowUniqueNameDialog(true) called');
        return;
      }
      
      console.log('✅ Title is unique, proceeding with save...');
    } catch (error) {
      console.error('💥 FATAL ERROR in handleSaveEdit:', error);
      setError('An unexpected error occurred while saving');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      // Get the current Delta content from Quill editor
      const quillEditor = quillRef.current?.getEditor();
      let deltaContent = quillEditor ? quillEditor.getContents() : editFormDelta;

      // Ensure we have a valid Delta object
      if (!deltaContent || !deltaContent.ops) {
        deltaContent = { ops: [{ insert: '\n' }] };
      }

      // Convert Delta to plain object to ensure proper serialization
      const serializedDelta = {
        ops: deltaContent.ops || [{ insert: '\n' }]
      };

      const response = await fetch(`http://localhost:8000/api/documents/${openDocument.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          title: editForm.title,
          document_type: editForm.document_type,
          content_delta: serializedDelta,
          home_date: editForm.home_date.toISOString(),
          ...(editForm.document_type === 'link' && { url: editForm.url })
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

    // Check for unique title
    const isUnique = await checkUniqueTitle(editForm.title, editForm.document_type);
    if (!isUnique) {
      setShowUniqueNameDialog(true);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      // Get the current Delta content from Quill editor
      const quillEditor = quillRef.current?.getEditor();
      let deltaContent = quillEditor ? quillEditor.getContents() : editFormDelta;

      // Ensure we have a valid Delta object
      if (!deltaContent || !deltaContent.ops) {
        deltaContent = { ops: [{ insert: '\n' }] };
      }

      // Convert Delta to plain object to ensure proper serialization
      const serializedDelta = {
        ops: deltaContent.ops || [{ insert: '\n' }]
      };

      // Prepare the request payload with all potentially required fields
      const payload = {
        title: editForm.title,
        document_type: editForm.document_type,
        content_delta: serializedDelta,
        content_md: '', // Add empty markdown content as fallback
        path: currentFolderPath,
        is_folder: false, // Explicitly set as not a folder
        home_date: editForm.home_date.toISOString(),
        ...(editForm.document_type === 'link' && { url: editForm.url })
      };

      console.log('🚀 Creating document with payload:', payload);

      const response = await fetch('http://localhost:8000/api/documents', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error('❌ Server error response:', errorText);
        throw new Error(`Failed to create document: ${response.status} ${response.statusText}`);
      }

      const newDocument: Document = await response.json();
      setDocuments(prev => [newDocument, ...prev]);

      // Switch to viewing the newly created document
      setOpenDocument(newDocument);
      setIsEditing(false);

    } catch (err) {
      console.error('❌ Error in handleCreateFromFullView:', err);
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

    // Check for unique title
    const isUnique = await checkUniqueTitle(createForm.title, createForm.document_type);
    if (!isUnique) {
      setShowUniqueNameDialog(true);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      // Get the current Delta content from Create Quill editor
      const createQuillEditor = createQuillRef.current?.getEditor();
      let deltaContent = createQuillEditor ? createQuillEditor.getContents() : createFormDelta;

      // Ensure we have a valid Delta object
      if (!deltaContent || !deltaContent.ops) {
        deltaContent = { ops: [{ insert: '\n' }] };
      }

      // Convert Delta to plain object to ensure proper serialization
      const serializedDelta = {
        ops: deltaContent.ops || [{ insert: '\n' }]
      };

      const payload = {
        title: createForm.title,
        document_type: createForm.document_type,
        content_delta: serializedDelta,
        content_md: '', // Add empty markdown content as fallback
        path: currentFolderPath,
        is_folder: false, // Explicitly set as not a folder
        home_date: createForm.home_date.toISOString(),
        ...(createForm.document_type === 'link' && { url: createForm.url })
      };

      console.log('🚀 Creating document with payload:', payload);

      const response = await fetch('http://localhost:8000/api/documents', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error('❌ Server error response:', errorText);
        throw new Error(`Failed to create document: ${response.status} ${response.statusText}`);
      }

      const newDocument: Document = await response.json();
      setDocuments(prev => [newDocument, ...prev]);
      setShowCreateDialog(false);
      setCreateForm({ title: '', document_type: 'note', content: '', url: '', home_date: new Date() });
      setCreateFormDelta(null);
    } catch (err) {
      console.error('❌ Error in handleCreateDocument:', err);
      setError(err instanceof Error ? err.message : 'Failed to create document');
    } finally {
      setLoading(false);
    }
  };

  const openCreateDialog = () => {
    console.log('➕ openCreateDialog called - showing document type selection');
    setShowDocumentTypeDialog(true);
    setSelectedDocumentType('folder');
    setError(null);
    // Clear any open dialogs when creating new document
    setShowDeleteDialog(false);
    setSelectedDocument(null);
  };

  const handleDocumentTypeSelection = () => {
    setShowDocumentTypeDialog(false);

    if (selectedDocumentType === 'folder') {
      // Show folder creation dialog
      setShowCreateFolderDialog(true);
      setNewFolderName('');
    } else if (selectedDocumentType === 'link') {
      // Show link URL input dialog
      setShowLinkUrlDialog(true);
      setLinkUrl('');
      setLinkTitle('');
      setLinkHomeDate(new Date());
    } else {
      // Open full editor for note/prompt
      setViewMode('document');
      console.log('📝 Setting openDocument to NULL in handleDocumentTypeSelection (creating new document)');
      setOpenDocument(null); // No existing document
      setIsEditing(true);
      setEditForm({
        title: '',
        document_type: selectedDocumentType,
        content: '',
        url: '',
        home_date: new Date()
      });
      setEditFormDelta(null);
    }
  };

  const handleCreateLink = async () => {
    if (!linkTitle.trim() || !linkUrl.trim()) {
      setError('Both title and URL are required');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const payload = {
        title: linkTitle,
        document_type: 'link',
        url: linkUrl,
        content_delta: { ops: [{ insert: '\n' }] },
        content_md: '', // Add empty markdown content as fallback
        path: currentFolderPath,
        is_folder: false, // Explicitly set as not a folder
        home_date: linkHomeDate.toISOString()
      };

      console.log('🚀 Creating link with payload:', payload);

      const response = await fetch('http://localhost:8000/api/documents', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error('❌ Server error response:', errorText);
        throw new Error(`Failed to create link: ${response.status} ${response.statusText}`);
      }

      const newLink: Document = await response.json();
      setDocuments(prev => [newLink, ...prev]);
      setShowLinkUrlDialog(false);
      setLinkUrl('');
      setLinkTitle('');
      setLinkHomeDate(new Date());
    } catch (err) {
      console.error('❌ Error in handleCreateLink:', err);
      setError(err instanceof Error ? err.message : 'Failed to create link');
    } finally {
      setLoading(false);
    }
  };

  const openEditLinkDialog = (link: Document) => {
    setEditingLink(link);
    setLinkTitle(link.title);
    setLinkUrl(link.url || '');
    setLinkHomeDate(new Date(link.home_date));
    setShowEditLinkDialog(true);
    setError(null);
  };

  const handleEditLink = async () => {
    if (!editingLink || !linkTitle.trim() || !linkUrl.trim()) {
      setError('Both title and URL are required');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const payload = {
        title: linkTitle,
        document_type: 'link',
        url: linkUrl,
        content_delta: { ops: [{ insert: '\n' }] },
        content_md: '',
        home_date: linkHomeDate.toISOString()
      };

      console.log('🚀 Updating link with payload:', payload);

      const response = await fetch(`http://localhost:8000/api/documents/${editingLink.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error('❌ Server error response:', errorText);
        throw new Error(`Failed to update link: ${response.status} ${response.statusText}`);
      }

      const updatedLink: Document = await response.json();
      setDocuments(prev => prev.map(doc => doc.id === editingLink.id ? updatedLink : doc));
      setShowEditLinkDialog(false);
      setEditingLink(null);
      setLinkUrl('');
      setLinkTitle('');
      setLinkHomeDate(new Date());
    } catch (err) {
      console.error('❌ Error in handleEditLink:', err);
      setError(err instanceof Error ? err.message : 'Failed to update link');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateFolder = async () => {
    if (!newFolderName.trim()) {
      setError('Folder name is required');
      return;
    }

    // Check for unique title
    const isUnique = await checkUniqueTitle(newFolderName, 'folder');
    if (!isUnique) {
      setShowUniqueNameDialog(true);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const payload = {
        title: newFolderName,
        document_type: 'folder',
        path: currentFolderPath,
        content_delta: { ops: [{ insert: '\n' }] },
        content_md: '', // Add empty markdown content as fallback
        is_folder: true, // Explicitly set as folder
        home_date: new Date().toISOString()
      };

      console.log('🚀 Creating folder with payload:', payload);

      const response = await fetch('http://localhost:8000/api/documents', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error('❌ Server error response:', errorText);
        throw new Error(`Failed to create folder: ${response.status} ${response.statusText}`);
      }

      const newFolder: Document = await response.json();
      setDocuments(prev => [newFolder, ...prev]);
      setShowCreateFolderDialog(false);
      setNewFolderName('');
    } catch (err) {
      console.error('❌ Error in handleCreateFolder:', err);
      setError(err instanceof Error ? err.message : 'Failed to create folder');
    } finally {
      setLoading(false);
    }
  };

  const getBreadcrumbs = () => {
    if (currentFolderPath === '/') {
      return [{ name: 'Root', path: '/' }];
    }

    const parts = currentFolderPath.split('/').filter(part => part);
    const breadcrumbs = [{ name: 'Root', path: '/' }];

    let currentPath = '';
    for (const part of parts) {
      currentPath += `/${part}`;
      breadcrumbs.push({ name: part, path: currentPath === '/' ? '/' : currentPath });
    }

    return breadcrumbs;
  };

  const navigateToFolder = (folderPath: string) => {
    setCurrentFolderPath(folderPath);
  };


  const openDeleteDialog = (document: Document) => {
    console.log('🗑️ openDeleteDialog called with document:', document);
    setSelectedDocument(document);
    setShowDeleteDialog(true);
    setError(null);
  };


  const handleDeleteDocumentDirect = async (document: Document) => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`http://localhost:8000/api/documents/${document.id}`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error('Failed to delete document');
      }

      setDocuments(prev => prev.filter(doc => doc.id !== document.id));

      // If we're viewing this document, go back to list
      if (openDocument?.id === document.id) {
        handleBackToList();
      }

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete document');
    } finally {
      setLoading(false);
    }
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

      // If we're viewing this document, go back to list
      if (openDocument?.id === selectedDocument.id) {
        handleBackToList();
      }

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
      <>
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
                        console.log('🗑️ Delete button clicked (view mode)', e);
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
                    onClick={() => {
                      console.log('💾 SAVE BUTTON CLICKED - openDocument:', openDocument ? 'EXISTS' : 'NULL');
                      console.log('💾 SAVE BUTTON - will call:', openDocument ? 'handleSaveEdit' : 'handleCreateFromFullView');
                      if (openDocument) {
                        handleSaveEdit();
                      } else {
                        handleCreateFromFullView();
                      }
                    }}
                    disabled={!editForm.title.trim()}
                    size="sm"
                    className="bg-primary text-primary-foreground hover:bg-primary/90"
                  >
                    Save
                  </Button>
                  {openDocument && (
                    <Button
                      onClick={(e) => {
                        console.log('🗑️ Delete button clicked (edit mode)', e);
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
                    <div className="flex items-center gap-2">
                      <Input
                        id="doc-title"
                        value={editForm.title}
                        onChange={(e) => setEditForm(prev => ({ ...prev, title: e.target.value }))}
                        className="text-lg p-3"
                        placeholder="Enter document title..."
                      />
                      <Select
                        value={editForm.document_type}
                        onValueChange={(value: 'note' | 'prompt' | 'link') =>
                          setEditForm(prev => ({ ...prev, document_type: value }))
                        }
                      >
                        <SelectTrigger className="w-[120px]">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="note">Note</SelectItem>
                          <SelectItem value="prompt">Prompt</SelectItem>
                          <SelectItem value="link">Link</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  <div className="md:col-span-1 flex justify-end">
                    <div className="flex flex-col">
                      <Label className="text-base font-semibold mb-2 block text-right">
                        Home Date
                      </Label>
                      <Popover>
                        <PopoverTrigger asChild>
                          <Button
                            variant="outline"
                            className="w-[160px] justify-start text-left font-normal"
                          >
                            <CalendarIcon className="mr-2 h-4 w-4" />
                            {editForm.home_date ? (
                              editForm.home_date.toLocaleDateString()
                            ) : (
                              <span>Pick a date</span>
                            )}
                          </Button>
                        </PopoverTrigger>
                        <PopoverContent className="w-auto p-0" align="end">
                          <Calendar
                            mode="single"
                            selected={editForm.home_date}
                            onSelect={(date) => date && setEditForm(prev => ({ ...prev, home_date: date }))}
                            initialFocus
                          />
                        </PopoverContent>
                      </Popover>
                    </div>
                  </div>
                </div>

                {/* URL Section for links */}
                {editForm.document_type === 'link' && (
                  <div>
                    <Label htmlFor="edit-url" className="text-base font-semibold mb-2 block">
                      URL
                    </Label>
                    <Input
                      id="edit-url"
                      value={editForm.url}
                      onChange={(e) => setEditForm(prev => ({ ...prev, url: e.target.value }))}
                      className="text-lg p-3"
                      placeholder="https://example.com"
                      type="url"
                    />
                  </div>
                )}

                {/* Content Section */}
                {editForm.document_type !== 'link' && (
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
                )}
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

        {/* Delete Document Confirmation Dialog - Available in document view */}
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
                  console.log('🗑️ Cancel button clicked');
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

        {/* Unique Name Validation Dialog - Available in document view */}
        {console.log('🎭 Rendering Unique Name Dialog in DOCUMENT VIEW with state:', showUniqueNameDialog)}
        <AlertDialog 
          open={showUniqueNameDialog} 
          onOpenChange={(open) => {
            console.log('🎭 AlertDialog onOpenChange called with:', open);
            setShowUniqueNameDialog(open);
          }}
        >
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Name Already Exists</AlertDialogTitle>
              <AlertDialogDescription>
                A document with this name already exists. Please choose a unique name for your folder, note, or prompt.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogAction
                onClick={() => {
                  console.log('✅ Unique name dialog OK button clicked');
                  setShowUniqueNameDialog(false);
                }}
                className="bg-primary text-primary-foreground hover:bg-primary/90"
              >
                OK
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </>
    );
  }

  // Render list view
  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div className="flex items-center">
          {/* Left Side Controls */}
          <div className="flex items-center">
            <Button onClick={openCreateDialog} className="flex items-center gap-2">
              <Plus className="h-4 w-4" />
              New
            </Button>
          </div>

          {/* Spacer */}
          <div className="mx-4 h-6 w-px bg-border/50"></div>

          {/* Filter Dropdown */}
          <div className="flex items-center">
            <Select
              defaultValue="none"
              onValueChange={(value) => setSelectedType(value as 'all' | 'note' | 'prompt' | 'link' | 'home_date' | 'none')}
            >
              <SelectTrigger className="w-[180px] focus-visible:ring-0 focus-visible:ring-offset-0">
                <SelectValue placeholder="Filter by..." />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">None</SelectItem>
                <SelectItem value="home_date">Home Date</SelectItem>
                <SelectItem value="notes">Notes</SelectItem>
                
                <SelectItem value="links">Links</SelectItem>
                <SelectItem value="prompts">Prompts</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      {/* Breadcrumb Navigation */}
      <div className="flex items-center space-x-2 text-sm text-muted-foreground bg-muted/30 p-3 rounded-lg">
        {getBreadcrumbs().map((breadcrumb, index) => (
          <div key={breadcrumb.path} className="flex items-center">
            {index > 0 && <span className="mx-2">/</span>}
            <button
              onClick={() => navigateToFolder(breadcrumb.path)}
              className={`hover:text-foreground transition-colors ${breadcrumb.path === currentFolderPath ? 'text-foreground font-medium' : ''
                }`}
            >
              {breadcrumb.name}
            </button>
          </div>
        ))}
      </div>

      {/* Search Bar */}
      <div className="flex items-center gap-4">
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
      {loading && documents.length === 0 && (
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



      {/* No Documents State */}
      {!loading && !error && documents.length === 0 && (
        <div className="text-center py-12">
          <div className="text-muted-foreground mb-4">
            <ScrollText className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p className="text-lg">No documents found</p>
            <p className="text-sm">Create your first document to get started</p>
          </div>
          <Button onClick={openCreateDialog} className="mt-4">
            <Plus className="h-4 w-4 mr-2" />
            Create Document
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
              <div className="col-span-3 flex items-center gap-2 cursor-pointer hover:text-foreground" onClick={() => handleSort('name')}>
                Name
                {sortBy === 'name' && (sortOrder === 'asc' ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />)}
              </div>
              <div className="col-span-1">
                {/* Edit column for links */}
              </div>
              <div className="col-span-2 cursor-pointer hover:text-foreground" onClick={() => handleSort('home_date')}>
                Home Date
                {sortBy === 'home_date' && (sortOrder === 'asc' ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />)}
              </div>
              <div className="col-span-2 cursor-pointer hover:text-foreground" onClick={() => handleSort('created')}>
                Created
                {sortBy === 'created' && (sortOrder === 'asc' ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />)}
              </div>
              <div className="col-span-3 cursor-pointer hover:text-foreground" onClick={() => handleSort('modified')}>
                Modified
                {sortBy === 'modified' && (sortOrder === 'asc' ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />)}
              </div>
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
                  <div className="col-span-3 flex items-center gap-2 min-w-0">
                    {getFileIcon(doc.document_type)}
                    <span className="truncate font-medium">{doc.title}</span>
                  </div>
                  <div className="col-span-1 flex items-center justify-center">
                    {doc.document_type === 'link' && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          openEditLinkDialog(doc);
                        }}
                        title="Edit link"
                        className="p-1 h-auto w-auto hover:bg-muted"
                      >
                        <Edit3 className="h-3 w-3" />
                      </Button>
                    )}
                  </div>
                  <div className="col-span-2 flex items-center text-sm text-muted-foreground">
                    {formatDate(doc.home_date)}
                  </div>
                  <div className="col-span-2 flex items-center text-sm text-muted-foreground">
                    {formatDate(doc.created_at)}
                  </div>
                  <div className="col-span-3 flex items-center justify-between text-sm text-muted-foreground">
                    <span>{formatDate(doc.updated_at)}</span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={(e) => {
                        console.log('🗑️ Delete button clicked (list view)', e, doc);
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

      {/* Document Type Selection Dialog */}
      <Dialog open={showDocumentTypeDialog} onOpenChange={setShowDocumentTypeDialog}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Create New</DialogTitle>
          </DialogHeader>
          <div className="grid gap-6 py-4">
            <RadioGroup
              value={selectedDocumentType}
              onValueChange={(value: 'folder' | 'note' | 'prompt' | 'link') => setSelectedDocumentType(value)}
              className="grid gap-4"
            >
              <div className="flex items-center space-x-3 p-3 border rounded-lg hover:bg-muted/50 cursor-pointer">
                <RadioGroupItem value="folder" id="folder" />
                <Label htmlFor="folder" className="flex items-center gap-2 cursor-pointer flex-1">
                  <Folder className="h-4 w-4 text-yellow-600" />
                  <div>
                    <div className="font-medium">Folder</div>
                    <div className="text-sm text-muted-foreground">Create a new folder</div>
                  </div>
                </Label>
              </div>
              <div className="flex items-center space-x-3 p-3 border rounded-lg hover:bg-muted/50 cursor-pointer">
                <RadioGroupItem value="note" id="note" />
                <Label htmlFor="note" className="flex items-center gap-2 cursor-pointer flex-1">
                  <File className="h-4 w-4 text-blue-600" />
                  <div>
                    <div className="font-medium">Note</div>
                    <div className="text-sm text-muted-foreground">Create a rich text document</div>
                  </div>
                </Label>
              </div>
              <div className="flex items-center space-x-3 p-3 border rounded-lg hover:bg-muted/50 cursor-pointer">
                <RadioGroupItem value="prompt" id="prompt" />
                <Label htmlFor="prompt" className="flex items-center gap-2 cursor-pointer flex-1">
                  <ScrollText className="h-4 w-4 text-purple-600" />
                  <div>
                    <div className="font-medium">Prompt</div>
                    <div className="text-sm text-muted-foreground">Create an AI prompt template</div>
                  </div>
                </Label>
              </div>
              <div className="flex items-center space-x-3 p-3 border rounded-lg hover:bg-muted/50 cursor-pointer">
                <RadioGroupItem value="link" id="link" />
                <Label htmlFor="link" className="flex items-center gap-2 cursor-pointer flex-1">
                  <Link className="h-4 w-4 text-green-600" />
                  <div>
                    <div className="font-medium">Link</div>
                    <div className="text-sm text-muted-foreground">Save a web link bookmark</div>
                  </div>
                </Label>
              </div>
            </RadioGroup>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setShowDocumentTypeDialog(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              onClick={handleDocumentTypeSelection}
            >
              Continue
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Link URL Input Dialog */}
      <Dialog open={showLinkUrlDialog} onOpenChange={setShowLinkUrlDialog}>
        <DialogContent className="sm:max-w-[525px]">
          <DialogHeader>
            <DialogTitle>Create Link</DialogTitle>
            <DialogDescription>
              Enter the URL and title for your link bookmark.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="link-title" className="text-right">
                Title
              </Label>
              <Input
                id="link-title"
                value={linkTitle}
                onChange={(e) => setLinkTitle(e.target.value)}
                className="col-span-3"
                placeholder="Enter link title..."
              />
            </div>
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="link-url" className="text-right">
                URL
              </Label>
              <Input
                id="link-url"
                value={linkUrl}
                onChange={(e) => setLinkUrl(e.target.value)}
                className="col-span-3"
                placeholder="https://example.com"
                type="url"
              />
            </div>
            <div className="grid grid-cols-4 items-center gap-4">
              <Label className="text-right">
                Home Date
              </Label>
              <div className="col-span-3">
                <Popover>
                  <PopoverTrigger asChild>
                    <Button
                      variant="outline"
                      className="w-full justify-start text-left font-normal"
                    >
                      <CalendarIcon className="mr-2 h-4 w-4" />
                      {linkHomeDate ? (
                        linkHomeDate.toLocaleDateString()
                      ) : (
                        <span>Pick a date</span>
                      )}
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-auto p-0" align="start">
                    <Calendar
                      mode="single"
                      selected={linkHomeDate}
                      onSelect={(date) => date && setLinkHomeDate(date)}
                      initialFocus
                    />
                  </PopoverContent>
                </Popover>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setShowLinkUrlDialog(false);
                setLinkUrl('');
                setLinkTitle('');
                setLinkHomeDate(new Date());
              }}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              onClick={handleCreateLink}
              disabled={!linkTitle.trim() || !linkUrl.trim()}
            >
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Link Dialog */}
      <Dialog open={showEditLinkDialog} onOpenChange={setShowEditLinkDialog}>
        <DialogContent className="sm:max-w-[525px]">
          <DialogHeader>
            <DialogTitle>Edit Link</DialogTitle>
            <DialogDescription>
              Update the URL, title, and home date for your link bookmark.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="edit-link-title" className="text-right">
                Title
              </Label>
              <Input
                id="edit-link-title"
                value={linkTitle}
                onChange={(e) => setLinkTitle(e.target.value)}
                className="col-span-3"
                placeholder="Enter link title..."
              />
            </div>
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="edit-link-url" className="text-right">
                URL
              </Label>
              <Input
                id="edit-link-url"
                value={linkUrl}
                onChange={(e) => setLinkUrl(e.target.value)}
                className="col-span-3"
                placeholder="https://example.com"
                type="url"
              />
            </div>
            <div className="grid grid-cols-4 items-center gap-4">
              <Label className="text-right">
                Home Date
              </Label>
              <div className="col-span-3">
                <Popover>
                  <PopoverTrigger asChild>
                    <Button
                      variant="outline"
                      className="w-full justify-start text-left font-normal"
                    >
                      <CalendarIcon className="mr-2 h-4 w-4" />
                      {linkHomeDate ? (
                        linkHomeDate.toLocaleDateString()
                      ) : (
                        <span>Pick a date</span>
                      )}
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-auto p-0" align="start">
                    <Calendar
                      mode="single"
                      selected={linkHomeDate}
                      onSelect={(date) => date && setLinkHomeDate(date)}
                      initialFocus
                    />
                  </PopoverContent>
                </Popover>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setShowEditLinkDialog(false);
                setEditingLink(null);
                setLinkUrl('');
                setLinkTitle('');
                setLinkHomeDate(new Date());
              }}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              onClick={handleEditLink}
              disabled={!linkTitle.trim() || !linkUrl.trim()}
            >
              Update
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

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
                onValueChange={(value: 'note' | 'prompt' | 'link') =>
                  setCreateForm(prev => ({ ...prev, document_type: value }))
                }
              >
                <SelectTrigger className="col-span-3">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="note">Note</SelectItem>
                  <SelectItem value="prompt">Prompt</SelectItem>
                  <SelectItem value="link">Link</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {createForm.document_type === 'link' && (
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="url" className="text-right">
                  URL
                </Label>
                <Input
                  id="url"
                  value={createForm.url}
                  onChange={(e) => setCreateForm(prev => ({ ...prev, url: e.target.value }))}
                  className="col-span-3"
                  placeholder="https://example.com"
                  type="url"
                />
              </div>
            )}
            {createForm.document_type !== 'link' && (
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
            )}
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
      {console.log('🗑️ Rendering delete modal - showDeleteDialog:', showDeleteDialog, 'selectedDocument:', selectedDocument)}
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
                console.log('🗑️ Cancel button clicked');
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

      {/* Create Folder Dialog */}
      <Dialog open={showCreateFolderDialog} onOpenChange={setShowCreateFolderDialog}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Create New Folder</DialogTitle>
            <DialogDescription>
              Create a new folder in {currentFolderPath === '/' ? 'Root' : currentFolderPath}.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="folder-name" className="text-right">
                Name
              </Label>
              <Input
                id="folder-name"
                value={newFolderName}
                onChange={(e) => setNewFolderName(e.target.value)}
                className="col-span-3"
                placeholder="Enter folder name..."
                onKeyPress={(e) => e.key === 'Enter' && handleCreateFolder()}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setShowCreateFolderDialog(false);
                setNewFolderName('');
              }}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              onClick={handleCreateFolder}
              disabled={!newFolderName.trim()}
            >
              Create Folder
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Unique Name Validation Dialog */}
      <AlertDialog 
        open={showUniqueNameDialog} 
        onOpenChange={(open) => {
          console.log('🎭 AlertDialog onOpenChange called with:', open);
          setShowUniqueNameDialog(open);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Name Already Exists</AlertDialogTitle>
            <AlertDialogDescription>
              A document with this name already exists. Please choose a unique name for your folder, note, or prompt.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogAction
              onClick={() => {
                console.log('✅ Unique name dialog OK button clicked');
                setShowUniqueNameDialog(false);
              }}
              className="bg-primary text-primary-foreground hover:bg-primary/90"
            >
              OK
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default DocumentsView;
