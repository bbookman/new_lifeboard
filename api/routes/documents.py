"""
Documents API routes for Notes & Prompts feature

This module provides REST API endpoints for document management including
create, read, update, delete, and search operations.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, validator

from core.dependencies import get_startup_service_dependency
from core.exception_handling import handle_api_exceptions
from services.document_service import Document, DocumentService
from services.startup import StartupService

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
    document_type: str = Field(..., pattern="^(note|prompt|folder|link)$")
    content_delta: Optional[Dict[str, Any]] = Field(None, description="Quill Delta format content")
    content_md: Optional[str] = Field(None, description="Markdown content (ignored, generated from delta)")
    path: str = Field("/", description="Virtual directory path")
    is_folder: Optional[bool] = Field(None, description="Whether this is a folder (ignored, determined by document_type)")
    url: Optional[str] = Field(None, description="URL for link documents")
    home_date: Optional[str] = Field(None, description="Home date (ignored, uses created_at)")

    @validator("title")
    def validate_title(cls, v):
        if not v.strip():
            raise ValueError("Title cannot be empty or whitespace only")
        return v.strip()


class CreateFolderRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    parent_path: str = Field("/", description="Parent directory path")

    @validator("name")
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError("Folder name cannot be empty or whitespace only")
        # Prevent path separators in folder names
        if "/" in v.strip():
            raise ValueError("Folder name cannot contain '/' characters")
        return v.strip()


class MoveItemRequest(BaseModel):
    new_parent_path: str = Field(..., description="New parent directory path")


class UpdateDocumentRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    document_type: Optional[str] = Field(None, pattern="^(note|prompt|link)$", description="Document type")
    content_delta: Optional[Dict[str, Any]] = Field(None, description="Quill Delta format content")
    content_md: Optional[str] = Field(None, description="Markdown content (ignored, generated from delta)")
    url: Optional[str] = Field(None, description="URL for link documents")
    home_date: Optional[str] = Field(None, description="Home date (ignored, uses updated_at)")

    @validator("title")
    def validate_title(cls, v):
        if v is not None and not v.strip():
            raise ValueError("Title cannot be empty or whitespace only")
        return v.strip() if v else v


class DocumentResponse(BaseModel):
    id: str
    title: str
    document_type: str
    content_delta: Dict[str, Any]
    content_md: str
    path: str
    is_folder: bool
    url: Optional[str] = None
    home_date: str  # Add home_date field
    created_at: str
    updated_at: str

    @classmethod
    def from_document(cls, document: Document) -> "DocumentResponse":
        return cls(
            id=document.id,
            title=document.title,
            document_type=document.document_type,
            content_delta=document.content_delta,
            content_md=document.content_md,
            path=document.path,
            is_folder=document.is_folder,
            url=getattr(document, "url", None),
            home_date=document.created_at.isoformat(),  # Use created_at as home_date
            created_at=document.created_at.isoformat(),
            updated_at=document.updated_at.isoformat(),
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


class ProcessTemplateRequest(BaseModel):
    content: str = Field(..., description="Content with template variables to process")
    target_date: Optional[str] = Field(None, description="Target date for template resolution (YYYY-MM-DD)")


class ProcessTemplateResponse(BaseModel):
    original_content: str
    resolved_content: str
    variables_resolved: int
    errors: List[str]


class ValidateTemplateResponse(BaseModel):
    is_valid: bool
    total_variables: int
    valid_variables: List[str]
    invalid_variables: List[str]
    supported_sources: List[str]
    supported_time_ranges: List[str]
    error: Optional[str] = None


# API Endpoints
@router.post("", response_model=DocumentResponse)
@handle_api_exceptions("Failed to create document", 500, include_details=True)
async def create_document(
    request: CreateDocumentRequest,
    document_service: DocumentService = Depends(get_document_service_for_route),
) -> DocumentResponse:
    """Create a new document or folder"""
    try:
        if request.document_type == "folder":
            # Handle folder creation
            document = await document_service.create_folder(
                name=request.title,
                parent_path=request.path,
            )
        else:
            # Handle regular document creation
            content_delta = request.content_delta or {"ops": [{"insert": "\n"}]}
            document = await document_service.create_document(
                title=request.title,
                document_type=request.document_type,
                content_delta=content_delta,
                path=request.path,
                url=request.url,
            )

        return DocumentResponse.from_document(document)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating document: {e}")
        raise HTTPException(status_code=500, detail="Failed to create document")



@router.get("/validate-title", response_model=Dict[str, bool])
@handle_api_exceptions("Failed to validate title", 500, include_details=True)
async def validate_document_title(
    title: str = Query(..., min_length=1, description="Title to validate"),
    document_type: str = Query(..., pattern="^(note|prompt|folder|link)$", description="Document type"),
    exclude_id: Optional[str] = Query(None, description="Document ID to exclude from validation"),
    document_service: DocumentService = Depends(get_document_service_for_route),
) -> Dict[str, bool]:
    """Fast title uniqueness validation"""
    try:
        exists = document_service.title_exists(title, document_type, exclude_id)
        return {"is_unique": not exists}

    except Exception as e:
        logger.error(f"Error validating title '{title}': {e}")
        raise HTTPException(status_code=500, detail="Failed to validate title")


@router.get("", response_model=DocumentListResponse)
@handle_api_exceptions("Failed to list documents", 500, include_details=True)
async def list_documents(
    document_type: Optional[str] = Query(None, pattern="^(note|prompt|folder|link)$"),
    folder_path: Optional[str] = Query(None, description="Filter by folder path"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    document_service: DocumentService = Depends(get_document_service_for_route),
) -> DocumentListResponse:
    """List documents with optional filtering"""
    try:
        if folder_path is not None:
            # Use folder contents listing when filtering by folder path
            documents = document_service.list_folder_contents(
                folder_path=folder_path,
                include_folders=(document_type == "folder" or document_type is None),
            )
            # Apply document_type filter if specified and not already handled
            if document_type and document_type != "folder":
                documents = [doc for doc in documents if doc.document_type == document_type]
            # Apply limit and offset manually
            documents = documents[offset:offset + limit]
        else:
            # Use regular list_documents for backward compatibility
            documents = document_service.list_documents(
                document_type=document_type,
                limit=limit,
                offset=offset,
            )

        # Get total count for pagination
        # For now, we'll use the returned count as total (could optimize with separate count query)
        total = len(documents)

        document_responses = [DocumentResponse.from_document(doc) for doc in documents]

        return DocumentListResponse(
            documents=document_responses,
            total=total,
            limit=limit,
            offset=offset,
        )

    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        raise HTTPException(status_code=500, detail="Failed to list documents")


@router.get("/search", response_model=DocumentSearchResponse)
@handle_api_exceptions("Failed to search documents", 500, include_details=True)
async def search_documents(
    q: str = Query(..., min_length=1, description="Search query"),
    document_type: Optional[str] = Query(None, pattern="^(note|prompt|link)$"),
    limit: int = Query(20, ge=1, le=50),
    document_service: DocumentService = Depends(get_document_service_for_route),
) -> DocumentSearchResponse:
    """Search documents using full-text and semantic search"""
    try:
        search_results = document_service.search_documents(
            query=q,
            document_type=document_type,
            limit=limit,
        )

        results = []
        for document, score in search_results:
            results.append(DocumentSearchResult(
                document=DocumentResponse.from_document(document),
                score=score,
            ))

        return DocumentSearchResponse(
            results=results,
            total=len(results),
            query=q,
        )

    except Exception as e:
        logger.error(f"Error searching documents: {e}")
        raise HTTPException(status_code=500, detail="Failed to search documents")


# Folder operations
@router.post("/folders", response_model=DocumentResponse)
@handle_api_exceptions("Failed to create folder", 500, include_details=True)
async def create_folder(
    request: CreateFolderRequest,
    document_service: DocumentService = Depends(get_document_service_for_route),
) -> DocumentResponse:
    """Create a new folder"""
    try:
        folder = await document_service.create_folder(
            name=request.name,
            parent_path=request.parent_path,
        )

        return DocumentResponse.from_document(folder)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating folder: {e}")
        raise HTTPException(status_code=500, detail="Failed to create folder")


@router.get("/folders/contents", response_model=DocumentListResponse)
@handle_api_exceptions("Failed to list folder contents", 500, include_details=True)
async def list_folder_contents(
    folder_path: str = Query("/", description="Folder path to list"),
    include_folders: bool = Query(True, description="Include folders in results"),
    document_service: DocumentService = Depends(get_document_service_for_route),
) -> DocumentListResponse:
    """List contents of a specific folder"""
    try:
        contents = document_service.list_folder_contents(
            folder_path=folder_path,
            include_folders=include_folders,
        )

        # Get total count for pagination
        total = len(contents)

        document_responses = [DocumentResponse.from_document(item) for item in contents]

        return DocumentListResponse(
            documents=document_responses,
            total=total,
            limit=len(contents),
            offset=0,
        )

    except Exception as e:
        logger.error(f"Error listing folder contents for {folder_path}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list folder contents")


@router.put("/{item_id}/move", response_model=Dict[str, str])
@handle_api_exceptions("Failed to move item", 500, include_details=True)
async def move_item(
    item_id: str,
    request: MoveItemRequest,
    document_service: DocumentService = Depends(get_document_service_for_route),
) -> Dict[str, str]:
    """Move a document or folder to a new location"""
    try:
        success = await document_service.move_item(
            item_id=item_id,
            new_parent_path=request.new_parent_path,
        )

        if not success:
            raise HTTPException(status_code=404, detail="Item not found or move failed")

        return {"message": "Item moved successfully"}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error moving item {item_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to move item")


@router.delete("/folders", response_model=Dict[str, str])
@handle_api_exceptions("Failed to delete folder", 500, include_details=True)
async def delete_folder(
    folder_path: str = Query(..., description="Folder path to delete"),
    recursive: bool = Query(False, description="Delete folder and all contents"),
    document_service: DocumentService = Depends(get_document_service_for_route),
) -> Dict[str, str]:
    """Delete a folder"""
    try:
        success = await document_service.delete_folder(
            folder_path=folder_path,
            recursive=recursive,
        )

        if not success:
            raise HTTPException(status_code=404, detail="Folder not found")

        return {"message": "Folder deleted successfully"}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting folder {folder_path}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete folder")


# Fast count endpoint for performance optimization
@router.get("/count", response_model=Dict[str, int])
@handle_api_exceptions("Failed to count documents", 500, include_details=True)
async def count_documents(
    document_type: Optional[str] = Query(None, pattern="^(note|prompt|folder|link)$"),
    folder_path: Optional[str] = Query(None, description="Count documents in specific folder"),
    document_service: DocumentService = Depends(get_document_service_for_route),
) -> Dict[str, int]:
    """Fast document count for performance optimization - returns count without loading full documents"""
    try:
        count = document_service.count_documents(
            document_type=document_type,
            folder_path=folder_path,
        )
        return {"count": count}

    except Exception as e:
        logger.error(f"Error counting documents: {e}")
        raise HTTPException(status_code=500, detail="Failed to count documents")


# Health endpoint
@router.get("/health", response_model=Dict[str, Any])
@handle_api_exceptions("Failed to get document service health", 500, include_details=True)
async def get_document_service_health(
    document_service: DocumentService = Depends(get_document_service_for_route),
) -> Dict[str, Any]:
    """Get document service health status"""
    try:
        health_info = await document_service._check_service_health()
        return health_info

    except Exception as e:
        logger.error(f"Error getting document service health: {e}")
        raise HTTPException(status_code=500, detail="Failed to get service health")


# Template Processing Routes
@router.post("/process-template", response_model=ProcessTemplateResponse)
@handle_api_exceptions("Failed to process template", 500, include_details=True)
async def process_template(
    request: ProcessTemplateRequest,
    document_service: DocumentService = Depends(get_document_service_for_route),
) -> ProcessTemplateResponse:
    """Process template variables in content"""
    try:
        resolved_content = document_service.process_template(
            content=request.content,
            target_date=request.target_date,
        )

        # Count resolved variables (simple heuristic)
        import re
        original_vars = len(re.findall(r"\{\{[A-Z_]+\}\}", request.content))
        remaining_vars = len(re.findall(r"\{\{[A-Z_]+\}\}", resolved_content))
        variables_resolved = original_vars - remaining_vars

        return ProcessTemplateResponse(
            original_content=request.content,
            resolved_content=resolved_content,
            variables_resolved=variables_resolved,
            errors=[],  # Errors are logged, not exposed in API for security
        )

    except Exception as e:
        logger.error(f"Error processing template: {e}")
        raise HTTPException(status_code=500, detail="Failed to process template")


@router.post("/validate-template", response_model=ValidateTemplateResponse)
@handle_api_exceptions("Failed to validate template", 500, include_details=True)
async def validate_template(
    request: ProcessTemplateRequest,
    document_service: DocumentService = Depends(get_document_service_for_route),
) -> ValidateTemplateResponse:
    """Validate template variables in content"""
    try:
        validation_result = document_service.validate_template(request.content)

        return ValidateTemplateResponse(
            is_valid=validation_result["is_valid"],
            total_variables=validation_result["total_variables"],
            valid_variables=validation_result["valid_variables"],
            invalid_variables=validation_result["invalid_variables"],
            supported_sources=validation_result.get("supported_sources", []),
            supported_time_ranges=validation_result.get("supported_time_ranges", []),
            error=validation_result.get("error"),
        )

    except Exception as e:
        logger.error(f"Error validating template: {e}")
        raise HTTPException(status_code=500, detail="Failed to validate template")


@router.post("/{document_id}/process-template", response_model=ProcessTemplateResponse)
@handle_api_exceptions("Failed to process document template", 500, include_details=True)
async def process_document_template(
    document_id: str,
    target_date: Optional[str] = None,
    document_service: DocumentService = Depends(get_document_service_for_route),
) -> ProcessTemplateResponse:
    """Process template variables in a specific document"""
    try:
        # Get the document
        document = document_service.get_document(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        # Process template in markdown content
        resolved_content = document_service.process_template(
            content=document.content_md,
            target_date=target_date,
        )

        # Count resolved variables
        import re
        original_vars = len(re.findall(r"\{\{[A-Z_]+\}\}", document.content_md))
        remaining_vars = len(re.findall(r"\{\{[A-Z_]+\}\}", resolved_content))
        variables_resolved = original_vars - remaining_vars

        return ProcessTemplateResponse(
            original_content=document.content_md,
            resolved_content=resolved_content,
            variables_resolved=variables_resolved,
            errors=[],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing document template {document_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to process document template")


# Document ID routes - MUST BE LAST to avoid conflicts with named routes
@router.get("/{document_id}", response_model=DocumentResponse)
@handle_api_exceptions("Failed to get document", 500, include_details=True)
async def get_document(
    document_id: str,
    document_service: DocumentService = Depends(get_document_service_for_route),
) -> DocumentResponse:
    """Get a specific document by ID"""
    try:
        document = document_service.get_document(document_id)
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
    document_service: DocumentService = Depends(get_document_service_for_route),
) -> DocumentResponse:
    """Update an existing document"""
    try:
        document = await document_service.update_document(
            doc_id=document_id,
            title=request.title,
            document_type=request.document_type,
            content_delta=request.content_delta,
            url=request.url,
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
    document_service: DocumentService = Depends(get_document_service_for_route),
) -> Dict[str, str]:
    """Delete a document"""
    try:
        success = await document_service.delete_document(document_id)
        if not success:
            raise HTTPException(status_code=404, detail="Document not found")

        return {"message": "Document deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document {document_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete document")
