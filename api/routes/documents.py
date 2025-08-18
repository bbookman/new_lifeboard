"""
Documents API routes for Notes & Prompts feature

This module provides REST API endpoints for document management including
create, read, update, delete, and search operations.
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, validator
from fastapi import APIRouter, Depends, HTTPException, Query

from services.document_service import DocumentService, Document
from services.startup import StartupService
from core.exception_handling import handle_api_exceptions
from core.dependencies import get_startup_service_dependency

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])

def get_document_service_for_route(startup_service: StartupService = Depends(get_startup_service_dependency)) -> DocumentService:
    """Get the document service instance for route dependency injection"""
    if not startup_service.document_service:
        raise HTTPException(status_code=503, detail="Document service not available")
    return startup_service.document_service


# Pydantic models for API requests and responses
class CreateDocumentRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    document_type: str = Field(..., pattern="^(note|prompt)$")
    content_delta: Dict[str, Any] = Field(..., description="Quill Delta format content")
    user_id: Optional[str] = None

    @validator('title')
    def validate_title(cls, v):
        if not v.strip():
            raise ValueError("Title cannot be empty or whitespace only")
        return v.strip()


class UpdateDocumentRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content_delta: Optional[Dict[str, Any]] = Field(None, description="Quill Delta format content")
    user_id: Optional[str] = None

    @validator('title')
    def validate_title(cls, v):
        if v is not None and not v.strip():
            raise ValueError("Title cannot be empty or whitespace only")
        return v.strip() if v else v


class DocumentResponse(BaseModel):
    id: str
    user_id: str
    title: str
    document_type: str
    content_delta: Dict[str, Any]
    content_md: str
    created_at: str
    updated_at: str

    @classmethod
    def from_document(cls, document: Document) -> 'DocumentResponse':
        return cls(
            id=document.id,
            user_id=document.user_id,
            title=document.title,
            document_type=document.document_type,
            content_delta=document.content_delta,
            content_md=document.content_md,
            created_at=document.created_at.isoformat(),
            updated_at=document.updated_at.isoformat()
        )


class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]
    total: int
    limit: int
    offset: int


class DocumentSearchResult(BaseModel):
    document: DocumentResponse
    score: float


class DocumentSearchResponse(BaseModel):
    results: List[DocumentSearchResult]
    total: int
    query: str


# API Endpoints
@router.post("", response_model=DocumentResponse)
@handle_api_exceptions("Failed to create document", 500, include_details=True)
async def create_document(
    request: CreateDocumentRequest,
    document_service: DocumentService = Depends(get_document_service_for_route)
) -> DocumentResponse:
    """Create a new document"""
    try:
        document = await document_service.create_document(
            title=request.title,
            document_type=request.document_type,
            content_delta=request.content_delta,
            user_id=request.user_id
        )
        
        return DocumentResponse.from_document(document)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating document: {e}")
        raise HTTPException(status_code=500, detail="Failed to create document")


@router.get("/{document_id}", response_model=DocumentResponse)
@handle_api_exceptions("Failed to get document", 500, include_details=True)
async def get_document(
    document_id: str,
    user_id: Optional[str] = Query(None),
    document_service: DocumentService = Depends(get_document_service_for_route)
) -> DocumentResponse:
    """Get a specific document by ID"""
    try:
        document = document_service.get_document(document_id, user_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return DocumentResponse.from_document(document)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document {document_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get document")


@router.put("/{document_id}", response_model=DocumentResponse)
@handle_api_exceptions("Failed to update document", 500, include_details=True)
async def update_document(
    document_id: str,
    request: UpdateDocumentRequest,
    document_service: DocumentService = Depends(get_document_service_for_route)
) -> DocumentResponse:
    """Update an existing document"""
    try:
        document = await document_service.update_document(
            doc_id=document_id,
            title=request.title,
            content_delta=request.content_delta,
            user_id=request.user_id
        )
        
        return DocumentResponse.from_document(document)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating document {document_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update document")


@router.delete("/{document_id}")
@handle_api_exceptions("Failed to delete document", 500, include_details=True)
async def delete_document(
    document_id: str,
    user_id: Optional[str] = Query(None),
    document_service: DocumentService = Depends(get_document_service_for_route)
) -> Dict[str, str]:
    """Delete a document"""
    try:
        success = await document_service.delete_document(document_id, user_id)
        if not success:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return {"message": "Document deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document {document_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete document")


@router.get("", response_model=DocumentListResponse)
@handle_api_exceptions("Failed to list documents", 500, include_details=True)
async def list_documents(
    user_id: Optional[str] = Query(None),
    document_type: Optional[str] = Query(None, pattern="^(note|prompt)$"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    document_service: DocumentService = Depends(get_document_service_for_route)
) -> DocumentListResponse:
    """List documents with optional filtering"""
    try:
        documents = document_service.list_documents(
            user_id=user_id,
            document_type=document_type,
            limit=limit,
            offset=offset
        )
        
        # Get total count for pagination
        # For now, we'll use the returned count as total (could optimize with separate count query)
        total = len(documents)
        
        document_responses = [DocumentResponse.from_document(doc) for doc in documents]
        
        return DocumentListResponse(
            documents=document_responses,
            total=total,
            limit=limit,
            offset=offset
        )
        
    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        raise HTTPException(status_code=500, detail="Failed to list documents")


@router.get("/search", response_model=DocumentSearchResponse)
@handle_api_exceptions("Failed to search documents", 500, include_details=True)
async def search_documents(
    q: str = Query(..., min_length=1, description="Search query"),
    user_id: Optional[str] = Query(None),
    document_type: Optional[str] = Query(None, pattern="^(note|prompt)$"),
    limit: int = Query(20, ge=1, le=50),
    document_service: DocumentService = Depends(get_document_service_for_route)
) -> DocumentSearchResponse:
    """Search documents using full-text and semantic search"""
    try:
        search_results = document_service.search_documents(
            query=q,
            user_id=user_id,
            document_type=document_type,
            limit=limit
        )
        
        results = []
        for document, score in search_results:
            results.append(DocumentSearchResult(
                document=DocumentResponse.from_document(document),
                score=score
            ))
        
        return DocumentSearchResponse(
            results=results,
            total=len(results),
            query=q
        )
        
    except Exception as e:
        logger.error(f"Error searching documents: {e}")
        raise HTTPException(status_code=500, detail="Failed to search documents")


# Health endpoint
@router.get("/health", response_model=Dict[str, Any])
@handle_api_exceptions("Failed to get document service health", 500, include_details=True)
async def get_document_service_health(
    document_service: DocumentService = Depends(get_document_service_for_route)
) -> Dict[str, Any]:
    """Get document service health status"""
    try:
        health_info = await document_service._check_service_health()
        return health_info
        
    except Exception as e:
        logger.error(f"Error getting document service health: {e}")
        raise HTTPException(status_code=500, detail="Failed to get service health")