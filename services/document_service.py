"""
Document Service for Notes & Prompts feature

This service handles document creation, editing, and management with support for
Quill.js Delta format and Markdown conversion for search and LLM integration.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import re

from core.base_service import BaseService
from core.database import DatabaseService
from core.vector_store import VectorStoreService
from core.embeddings import EmbeddingService
from core.ids import NamespacedIDManager
from sources.base import DataItem
from config.models import AppConfig

logger = logging.getLogger(__name__)


@dataclass
class Document:
    """Document data structure"""
    id: str
    user_id: str
    title: str
    document_type: str  # 'note', 'prompt', 'folder', or 'link'
    content_delta: Dict[str, Any]  # Quill Delta format
    content_md: str  # Markdown version
    path: str  # Virtual directory path
    is_folder: bool  # True if this is a folder
    url: Optional[str] = None  # URL for link documents
    created_at: datetime = None
    updated_at: datetime = None


class DocumentService(BaseService):
    """Service for managing user documents"""
    
    def __init__(self,
                 database: DatabaseService,
                 vector_store: VectorStoreService,
                 embedding_service: EmbeddingService,
                 config: AppConfig):
        super().__init__(service_name="DocumentService", config=config)
        self.database = database
        self.vector_store = vector_store
        self.embedding_service = embedding_service
        self.config = config
        
        # Add dependencies and capabilities
        self.add_dependency("DatabaseService")
        self.add_dependency("VectorStoreService") 
        self.add_dependency("EmbeddingService")
        self.add_capability("document_management")
        self.add_capability("rich_text_editing")
        self.add_capability("document_search")
        self.add_capability("vector_integration")
    
    async def create_document(self,
                            title: str,
                            document_type: str,
                            content_delta: Dict[str, Any],
                            user_id: Optional[str] = None,
                            path: str = "/",
                            url: Optional[str] = None) -> Document:
        """Create a new document"""
        if document_type not in ['note', 'prompt', 'link']:
            raise ValueError("Document type must be 'note', 'prompt', or 'link'")
        
        if user_id is None:
            user_id = self.config.documents.default_user_id
        
        # Validate title length
        if len(title) > self.config.documents.max_title_length:
            raise ValueError(f"Title too long (max {self.config.documents.max_title_length} characters)")
        
        # Generate document ID
        doc_id = str(uuid.uuid4())
        
        # Convert Delta to Markdown
        content_md = self._delta_to_markdown(content_delta)
        
        # Validate content length
        if len(content_md) > self.config.documents.max_content_length:
            raise ValueError(f"Content too long (max {self.config.documents.max_content_length} characters)")
        
        # Ensure path formatting is correct
        if not path.startswith('/'):
            path = '/' + path
        if not path.endswith('/') and path != '/':
            path += '/'
        
        # Create full document path
        document_path = path + title if path != '/' else '/' + title
        
        # Create document
        now = datetime.now(timezone.utc)
        document = Document(
            id=doc_id,
            user_id=user_id,
            title=title,
            document_type=document_type,
            content_delta=content_delta,
            content_md=content_md,
            path=document_path,
            is_folder=False,
            url=url,
            created_at=now,
            updated_at=now
        )
        
        # Store in database
        self._store_document(document)
        
        # Create vector embeddings if content is not empty
        if content_md.strip():
            await self._create_document_embeddings(document)
        
        logger.info(f"Created {document_type} document: {doc_id} - {title}")
        return document
    
    async def update_document(self,
                            doc_id: str,
                            title: Optional[str] = None,
                            document_type: Optional[str] = None,  # Added parameter
                            content_delta: Optional[Dict[str, Any]] = None,
                            user_id: Optional[str] = None,
                            url: Optional[str] = None) -> Document:
        """Update an existing document"""
        if user_id is None:
            user_id = self.config.documents.default_user_id
        
        # DIAGNOSTIC LOG: Check what's being requested
        logger.info(f"[DEBUG] update_document called with: doc_id={doc_id}, title={title}, document_type={document_type}")
        
        # Get existing document
        document = self.get_document(doc_id, user_id)
        if not document:
            raise ValueError(f"Document {doc_id} not found")
        
        # DIAGNOSTIC LOG: Check current document type
        logger.info(f"[DEBUG] Current document type: {document.document_type}")
        
        # Update fields
        if title is not None:
            if len(title) > self.config.documents.max_title_length:
                raise ValueError(f"Title too long (max {self.config.documents.max_title_length} characters)")
            document.title = title
        
        # Update document type if provided
        if document_type is not None:
            if document_type not in ['note', 'prompt', 'link']:
                raise ValueError("Document type must be 'note', 'prompt', or 'link'")
            logger.info(f"[DEBUG] Updating document type from {document.document_type} to {document_type}")
            document.document_type = document_type
        
        if content_delta is not None:
            # Convert Delta to Markdown
            content_md = self._delta_to_markdown(content_delta)
            
            # Validate content length
            if len(content_md) > self.config.documents.max_content_length:
                raise ValueError(f"Content too long (max {self.config.documents.max_content_length} characters)")
            
            document.content_delta = content_delta
            document.content_md = content_md
        
        # Update URL if provided (for link documents)
        if url is not None:
            document.url = url
        
        document.updated_at = datetime.now(timezone.utc)
        
        # DIAGNOSTIC LOG: Check document before storing
        logger.info(f"[DEBUG] Document before storing: type={document.document_type}, title={document.title}")
        
        # Update in database
        self._store_document(document)
        
        # Update vector embeddings if content changed
        if content_delta is not None:
            await self._update_document_embeddings(document)
        
        logger.info(f"Updated document: {doc_id} - {document.title} (type: {document.document_type})")
        return document
    
    def get_document(self, doc_id: str, user_id: Optional[str] = None) -> Optional[Document]:
        """Get a document by ID"""
        if user_id is None:
            user_id = self.config.documents.default_user_id
        
        try:
            with self.database.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT id, user_id, title, document_type, content_delta, content_md,
                           path, is_folder, url, created_at, updated_at
                    FROM user_documents 
                    WHERE id = ? AND user_id = ?
                """, (doc_id, user_id))
                
                row = cursor.fetchone()
                if not row:
                    return None
                
                return self._row_to_document(row)
            
        except Exception as e:
            logger.error(f"Error getting document {doc_id}: {e}")
            return None
    
    def list_documents(self,
                      user_id: Optional[str] = None,
                      document_type: Optional[str] = None,
                      limit: int = 50,
                      offset: int = 0) -> List[Document]:
        """List documents with optional filtering"""
        if user_id is None:
            user_id = self.config.documents.default_user_id
        
        try:
            # Build query
            query = """
                SELECT id, user_id, title, document_type, content_delta, content_md,
                       path, is_folder, url, created_at, updated_at
                FROM user_documents 
                WHERE user_id = ?
            """
            params = [user_id]
            
            if document_type:
                query += " AND document_type = ?"
                params.append(document_type)
            
            query += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            with self.database.get_connection() as conn:
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
                
                return [self._row_to_document(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Error listing documents: {e}")
            return []
    
    async def delete_document(self, doc_id: str, user_id: Optional[str] = None) -> bool:
        """Delete a document"""
        if user_id is None:
            user_id = self.config.documents.default_user_id
        
        try:
            # Remove from vector store first
            await self._remove_document_embeddings(doc_id)
            
            # Remove from database (FTS5 will be updated by triggers)
            with self.database.get_connection() as conn:
                cursor = conn.execute("""
                    DELETE FROM user_documents 
                    WHERE id = ? AND user_id = ?
                """, (doc_id, user_id))
                
                if cursor.rowcount > 0:
                    conn.commit()
                    logger.info(f"Deleted document: {doc_id}")
                    return True
                else:
                    logger.warning(f"Document {doc_id} not found for deletion")
                    return False
                
        except Exception as e:
            logger.error(f"Error deleting document {doc_id}: {e}")
            return False
    
    def search_documents(self,
                        query: str,
                        user_id: Optional[str] = None,
                        document_type: Optional[str] = None,
                        limit: int = 20) -> List[Tuple[Document, float]]:
        """Search documents using FTS5 and vector similarity"""
        if user_id is None:
            user_id = self.config.documents.default_user_id
        
        results = []
        
        # 1. FTS5 text search
        fts_results = self._search_documents_fts(query, user_id, document_type, limit)
        
        # 2. Vector similarity search
        vector_results = self._search_documents_vector(query, user_id, document_type, limit)
        
        # 3. Merge and deduplicate results
        doc_scores = {}
        
        # Add FTS results with boosted scores
        for doc, score in fts_results:
            doc_scores[doc.id] = (doc, score * 1.2)  # Boost FTS scores
        
        # Add vector results, combining scores if document already found
        for doc, score in vector_results:
            if doc.id in doc_scores:
                existing_doc, existing_score = doc_scores[doc.id]
                combined_score = (existing_score + score) / 2
                doc_scores[doc.id] = (existing_doc, combined_score)
            else:
                doc_scores[doc.id] = (doc, score)
        
        # Sort by combined score and return top results
        results = list(doc_scores.values())
        results.sort(key=lambda x: x[1], reverse=True)
        
        return results[:limit]
    
    async def create_folder(self,
                           name: str,
                           parent_path: str = "/",
                           user_id: Optional[str] = None) -> Document:
        """Create a new folder"""
        if user_id is None:
            user_id = self.config.documents.default_user_id
        
        # Validate folder name
        if not name or not name.strip():
            raise ValueError("Folder name cannot be empty")
        
        # Ensure parent path formatting
        if not parent_path.startswith('/'):
            parent_path = '/' + parent_path
        if not parent_path.endswith('/'):
            parent_path += '/'
        
        # Create folder path
        folder_path = parent_path + name + "/"
        
        # Check if folder already exists
        if self._path_exists(folder_path, user_id):
            raise ValueError(f"Folder already exists: {folder_path}")
        
        # Generate folder ID
        folder_id = str(uuid.uuid4())
        
        # Create folder document
        now = datetime.now(timezone.utc)
        folder = Document(
            id=folder_id,
            user_id=user_id,
            title=name,
            document_type="folder",
            content_delta={"ops": [{"insert": "\n"}]},  # Empty content
            content_md="",
            path=folder_path,
            is_folder=True,
            created_at=now,
            updated_at=now
        )
        
        # Store in database
        self._store_document(folder)
        
        logger.info(f"Created folder: {folder_path}")
        return folder
    
    def list_folder_contents(self,
                           folder_path: str = "/",
                           user_id: Optional[str] = None,
                           include_folders: bool = True) -> List[Document]:
        """List immediate contents of a folder"""
        if user_id is None:
            user_id = self.config.documents.default_user_id
        
        # Ensure path formatting
        if not folder_path.startswith('/'):
            folder_path = '/' + folder_path
        if not folder_path.endswith('/'):
            folder_path += '/'
        
        try:
            with self.database.get_connection() as conn:
                # Simplified approach: find items whose parent directory matches folder_path
                # Extract parent directory from path and compare
                
                if folder_path == '/':
                    # Root folder: find items with no subdirectories
                    query = """
                        SELECT id, user_id, title, document_type, content_delta, content_md,
                               path, is_folder, url, created_at, updated_at
                        FROM user_documents 
                        WHERE user_id = ? 
                        AND (
                            -- Documents in root: path like '/name' (count slashes = 1, ends without slash)
                            (LENGTH(path) - LENGTH(REPLACE(path, '/', '')) = 1 AND NOT path LIKE '%/' AND is_folder = FALSE)
                            OR
                            -- Folders in root: path like '/name/' (count slashes = 2, ends with slash)  
                            (LENGTH(path) - LENGTH(REPLACE(path, '/', '')) = 2 AND path LIKE '%/' AND is_folder = TRUE)
                        )
                    """
                    params = [user_id]
                else:
                    # Non-root folder: find items whose path starts with folder_path
                    # and has exactly one more level
                    query = """
                        SELECT id, user_id, title, document_type, content_delta, content_md,
                               path, is_folder, url, created_at, updated_at
                        FROM user_documents 
                        WHERE user_id = ? AND path LIKE ?
                        AND (
                            -- Documents: path starts with folder_path, no additional slashes
                            (path NOT LIKE ? AND is_folder = FALSE)
                            OR
                            -- Folders: path starts with folder_path, exactly one more slash at end
                            (path LIKE ? AND path NOT LIKE ? AND is_folder = TRUE)
                        )
                    """
                    like_pattern = folder_path + "%"
                    # For documents: no additional slashes after the folder path
                    doc_not_like = folder_path + "%/%"  
                    # For folders: ends with slash
                    folder_like = folder_path + "%/"
                    # But not nested folders (no slashes between folder_path and final slash)
                    folder_not_like = folder_path + "%/%/"
                    params = [user_id, like_pattern, doc_not_like, folder_like, folder_not_like]
                
                if not include_folders:
                    query += " AND is_folder = FALSE"
                
                query += " ORDER BY is_folder DESC, title ASC"
                
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
                
                return [self._row_to_document(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Error listing folder contents {folder_path}: {e}")
            return []
    
    async def move_item(self,
                       item_id: str,
                       new_parent_path: str,
                       user_id: Optional[str] = None) -> bool:
        """Move a document or folder to a new location"""
        if user_id is None:
            user_id = self.config.documents.default_user_id
        
        # Get the item to move
        item = self.get_document(item_id, user_id)
        if not item:
            raise ValueError(f"Item {item_id} not found")
        
        # Ensure new parent path formatting
        if not new_parent_path.startswith('/'):
            new_parent_path = '/' + new_parent_path
        if not new_parent_path.endswith('/'):
            new_parent_path += '/'
        
        try:
            # Calculate new path
            if item.is_folder:
                new_path = new_parent_path + item.title + "/"
            else:
                new_path = new_parent_path + item.title
            
            # Check for conflicts
            if self._path_exists(new_path, user_id):
                raise ValueError(f"Item already exists at destination: {new_path}")
            
            with self.database.get_connection() as conn:
                if item.is_folder:
                    # Move folder and all its contents
                    old_path_prefix = item.path
                    new_path_prefix = new_path
                    
                    # Update all items in the folder
                    conn.execute("""
                        UPDATE user_documents 
                        SET path = REPLACE(path, ?, ?), updated_at = CURRENT_TIMESTAMP
                        WHERE user_id = ? AND path LIKE ?
                    """, (old_path_prefix, new_path_prefix, user_id, old_path_prefix + "%"))
                else:
                    # Move single document
                    conn.execute("""
                        UPDATE user_documents 
                        SET path = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ? AND user_id = ?
                    """, (new_path, item_id, user_id))
                
                conn.commit()
                logger.info(f"Moved item {item_id} from {item.path} to {new_path}")
                return True
                
        except Exception as e:
            logger.error(f"Error moving item {item_id}: {e}")
            return False
    
    async def delete_folder(self,
                           folder_path: str,
                           user_id: Optional[str] = None,
                           recursive: bool = False) -> bool:
        """Delete a folder and optionally its contents"""
        if user_id is None:
            user_id = self.config.documents.default_user_id
        
        # Ensure path formatting
        if not folder_path.startswith('/'):
            folder_path = '/' + folder_path
        if not folder_path.endswith('/'):
            folder_path += '/'
        
        try:
            with self.database.get_connection() as conn:
                if recursive:
                    # Delete folder and all contents
                    cursor = conn.execute("""
                        DELETE FROM user_documents 
                        WHERE user_id = ? AND path LIKE ?
                    """, (user_id, folder_path + "%"))
                else:
                    # Check if folder is empty
                    cursor = conn.execute("""
                        SELECT COUNT(*) as count FROM user_documents 
                        WHERE user_id = ? AND path LIKE ? AND path != ?
                    """, (user_id, folder_path + "%", folder_path))
                    
                    if cursor.fetchone()['count'] > 0:
                        raise ValueError("Cannot delete non-empty folder. Use recursive=True")
                    
                    # Delete empty folder
                    cursor = conn.execute("""
                        DELETE FROM user_documents 
                        WHERE user_id = ? AND path = ? AND is_folder = TRUE
                    """, (user_id, folder_path))
                
                conn.commit()
                logger.info(f"Deleted folder: {folder_path}")
                return cursor.rowcount > 0
                
        except Exception as e:
            logger.error(f"Error deleting folder {folder_path}: {e}")
            return False
    
    def _path_exists(self, path: str, user_id: str) -> bool:
        """Check if a path already exists"""
        try:
            with self.database.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT COUNT(*) as count FROM user_documents 
                    WHERE user_id = ? AND path = ?
                """, (user_id, path))
                
                return cursor.fetchone()['count'] > 0
        except Exception as e:
            logger.error(f"Error checking path existence {path}: {e}")
            return False
    
    def _store_document(self, document: Document):
        """Store document in database"""
        try:
            with self.database.get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO user_documents 
                    (id, user_id, title, document_type, content_delta, content_md, path, is_folder, url, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    document.id,
                    document.user_id,
                    document.title,
                    document.document_type,
                    json.dumps(document.content_delta),
                    document.content_md,
                    document.path,
                    document.is_folder,
                    document.url,
                    document.created_at.isoformat(),
                    document.updated_at.isoformat()
                ))
                conn.commit()
            
        except Exception as e:
            logger.error(f"Error storing document {document.id}: {e}")
            raise
    
    def _row_to_document(self, row) -> Document:
        """Convert database row to Document object"""
        return Document(
            id=row['id'],
            user_id=row['user_id'],
            title=row['title'],
            document_type=row['document_type'],
            content_delta=json.loads(row['content_delta']),
            content_md=row['content_md'],
            path=row['path'] if 'path' in row.keys() else '/',  # Default to root if not present
            is_folder=bool(row['is_folder']) if 'is_folder' in row.keys() else False,  # Default to False if not present
            url=row['url'] if 'url' in row.keys() else None,  # Default to None if not present
            created_at=datetime.fromisoformat(row['created_at']),
            updated_at=datetime.fromisoformat(row['updated_at'])
        )
    
    def _delta_to_markdown(self, delta: Dict[str, Any]) -> str:
        """Convert Quill Delta format to Markdown"""
        if not delta or 'ops' not in delta:
            return ""
        
        markdown_parts = []
        
        for op in delta['ops']:
            if 'insert' not in op:
                continue
            
            text = op['insert']
            if isinstance(text, str):
                # Handle text with attributes
                attributes = op.get('attributes', {})
                
                # Apply formatting
                if attributes.get('bold'):
                    text = f"**{text}**"
                if attributes.get('italic'):
                    text = f"*{text}*"
                if attributes.get('code'):
                    text = f"`{text}`"
                if attributes.get('link'):
                    text = f"[{text}]({attributes['link']})"
                
                # Handle headers
                header = attributes.get('header')
                if header:
                    text = f"{'#' * int(header)} {text}"
                
                # Handle lists
                if attributes.get('list') == 'ordered':
                    text = f"1. {text}"
                elif attributes.get('list') == 'bullet':
                    text = f"- {text}"
                
                markdown_parts.append(text)
            
            elif isinstance(text, dict):
                # Handle embeds (images, etc.)
                if 'image' in text:
                    markdown_parts.append(f"![Image]({text['image']})")
                elif 'video' in text:
                    markdown_parts.append(f"[Video]({text['video']})")
        
        return ''.join(markdown_parts)
    
    async def _create_document_embeddings(self, document: Document):
        """Create vector embeddings for document"""
        if not self.config.documents.chunking_enabled:
            return
        
        try:
            # Create chunks if content is long enough
            chunks = self._chunk_content(document.content_md)
            
            for i, chunk in enumerate(chunks):
                if chunk.strip():  # Only process non-empty chunks
                    # Create DataItem for vector store integration
                    data_item = DataItem(
                        namespace="user_docs",
                        source_id=f"{document.id}:chunk_{i}",
                        content=chunk,
                        metadata={
                            "document_id": document.id,
                            "document_title": document.title,
                            "document_type": document.document_type,
                            "user_id": document.user_id,
                            "chunk_index": i,
                            "total_chunks": len(chunks)
                        },
                        created_at=document.created_at,
                        updated_at=document.updated_at
                    )
                    
                    # Generate embedding and store in vector store
                    embedding = await self.embedding_service.embed_text(chunk)
                    namespaced_id = NamespacedIDManager.create_id("user_docs", data_item.source_id)
                    self.vector_store.add_vector(namespaced_id, embedding)
            
            logger.debug(f"Created {len(chunks)} embeddings for document {document.id}")
            
        except Exception as e:
            logger.error(f"Error creating embeddings for document {document.id}: {e}")
    
    async def _update_document_embeddings(self, document: Document):
        """Update vector embeddings for document"""
        # Remove old embeddings
        await self._remove_document_embeddings(document.id)
        
        # Create new embeddings
        await self._create_document_embeddings(document)
    
    async def _remove_document_embeddings(self, doc_id: str):
        """Remove all vector embeddings for a document"""
        try:
            # Find all vector IDs for this document
            stats = self.vector_store.get_stats()
            if 'total_vectors' not in stats or stats['total_vectors'] == 0:
                return
            
            # Search for vectors with this document ID prefix
            vectors_to_remove = []
            for vector_id in self.vector_store.vectors.keys():
                if vector_id.startswith(f"user_docs:{doc_id}:"):
                    vectors_to_remove.append(vector_id)
            
            # Remove vectors
            for vector_id in vectors_to_remove:
                self.vector_store.remove_vector(vector_id)
            
            logger.debug(f"Removed {len(vectors_to_remove)} embeddings for document {doc_id}")
            
        except Exception as e:
            logger.error(f"Error removing embeddings for document {doc_id}: {e}")
    
    def _chunk_content(self, content: str) -> List[str]:
        """Split content into chunks for vector indexing"""
        if len(content) <= self.config.documents.chunk_size:
            return [content]
        
        chunks = []
        chunk_size = self.config.documents.chunk_size
        overlap = self.config.documents.chunk_overlap
        
        start = 0
        while start < len(content):
            end = start + chunk_size
            
            # Try to break at sentence boundaries
            if end < len(content):
                # Look for sentence end within overlap region
                search_start = max(end - overlap, start + chunk_size // 2)
                sentence_end = content.rfind('.', search_start, end + overlap)
                if sentence_end > start:
                    end = sentence_end + 1
            
            chunk = content[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - overlap if end < len(content) else end
        
        return chunks
    
    def _search_documents_fts(self,
                             query: str,
                             user_id: str,
                             document_type: Optional[str],
                             limit: int) -> List[Tuple[Document, float]]:
        """Search documents using FTS5"""
        try:
            # Build FTS query
            fts_query = query.replace("'", "''")  # Escape single quotes
            
            sql = """
                SELECT d.id, d.user_id, d.title, d.document_type, d.content_delta, 
                       d.content_md, d.path, d.is_folder, d.created_at, d.updated_at, 
                       bm25(fts) as score
                FROM user_documents_fts fts
                JOIN user_documents d ON d.rowid = fts.rowid
                WHERE fts MATCH ? AND d.user_id = ?
            """
            params = [fts_query, user_id]
            
            if document_type:
                sql += " AND d.document_type = ?"
                params.append(document_type)
            
            sql += " ORDER BY score LIMIT ?"
            params.append(limit)
            
            with self.database.get_connection() as conn:
                cursor = conn.execute(sql, params)
                rows = cursor.fetchall()
                
                results = []
                for row in rows:
                    document = self._row_to_document(row)
                    score = abs(row['score']) if row['score'] else 0.0  # BM25 scores can be negative
                    results.append((document, score))
            
            return results
            
        except Exception as e:
            logger.error(f"Error in FTS search: {e}")
            return []
    
    def _search_documents_vector(self,
                                query: str,
                                user_id: str,
                                document_type: Optional[str],
                                limit: int) -> List[Tuple[Document, float]]:
        """Search documents using vector similarity"""
        try:
            # Generate query embedding
            import asyncio
            loop = asyncio.get_event_loop()
            query_embedding = loop.run_until_complete(self.embedding_service.embed_text(query))
            
            # Search vector store with namespace filter
            vector_results = self.vector_store.search(
                query_embedding,
                k=limit * 2,  # Get more results to filter
                namespace_filter=["user_docs"]
            )
            
            # Group results by document and get best score per document
            doc_scores = {}
            for vector_id, similarity in vector_results:
                # Extract document ID from vector ID: user_docs:doc_id:chunk_N
                parts = vector_id.split(':')
                if len(parts) >= 2:
                    doc_id = parts[1]
                    if doc_id not in doc_scores or similarity > doc_scores[doc_id]:
                        doc_scores[doc_id] = similarity
            
            # Get documents and apply filters
            results = []
            for doc_id, score in doc_scores.items():
                document = self.get_document(doc_id, user_id)
                if document and (not document_type or document.document_type == document_type):
                    results.append((document, score))
            
            # Sort by score and return top results
            results.sort(key=lambda x: x[1], reverse=True)
            return results[:limit]
            
        except Exception as e:
            logger.error(f"Error in vector search: {e}")
            return []
    
    async def _initialize_service(self) -> bool:
        """Initialize the document service"""
        try:
            # Ensure dependencies are ready
            if not self.database or not self.vector_store or not self.embedding_service:
                self.logger.error("Missing required dependencies for DocumentService")
                return False
            
            self.logger.info("DocumentService initialized successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize DocumentService: {e}")
            return False
    
    async def _shutdown_service(self) -> bool:
        """Shutdown the document service"""
        try:
            self.logger.info("DocumentService shutdown successfully")
            return True
        except Exception as e:
            self.logger.error(f"Error during DocumentService shutdown: {e}")
            return False
    
    async def _check_service_health(self) -> Dict[str, Any]:
        """Check service health"""
        health_info = {
            "healthy": True,
            "documents_enabled": self.config.documents.enabled
        }
        
        try:
            # Check database connectivity
            test_query = "SELECT COUNT(*) as count FROM user_documents"
            with self.database.get_connection() as conn:
                cursor = conn.execute(test_query)
                result = cursor.fetchone()
                health_info["total_documents"] = result['count'] if result else 0
                health_info["database_available"] = True
            
            # Check vector store
            vs_stats = self.vector_store.get_stats()
            health_info["vector_store_available"] = True
            health_info["total_vectors"] = vs_stats.get("total_vectors", 0)
            
        except Exception as e:
            health_info["healthy"] = False
            health_info["error"] = str(e)
        
        return health_info