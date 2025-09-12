"""
Debug API routes for troubleshooting

Provides diagnostic endpoints for troubleshooting various system components
"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from core.dependencies import get_dependency_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/debug", tags=["debug"])

@router.get("/summary-status")
async def get_summary_status(registry = Depends(get_dependency_registry)) -> Dict[str, Any]:
    """Comprehensive summary system diagnostic"""
    try:
        startup_service = registry.get_startup_service()
        if not startup_service:
            raise HTTPException(status_code=503, detail="Startup service not available")
        
        # Check LLM service availability
        llm_service_available = startup_service.llm_service is not None
        llm_provider_available = False
        llm_provider_info = {}
        
        if llm_service_available and startup_service.llm_service:
            try:
                llm_provider = startup_service.llm_service.llm_provider
                llm_provider_available = llm_provider is not None
                if llm_provider:
                    llm_provider_info = {
                        "provider_name": getattr(llm_provider, 'provider_name', 'unknown'),
                        "available": True
                    }
            except Exception as e:
                llm_provider_info = {"error": str(e)}
        
        # Check prompt configuration
        prompt_configured = False
        prompt_info = {}
        
        if startup_service.database:
            try:
                with startup_service.database.get_connection() as conn:
                    cursor = conn.execute("""
                        SELECT ps.setting_key, ps.prompt_document_id, ud.title
                        FROM prompt_settings ps
                        LEFT JOIN user_documents ud ON ps.prompt_document_id = ud.id
                        WHERE ps.setting_key LIKE 'daily_summary_prompt_%' 
                        AND ps.is_active = TRUE
                        ORDER BY ps.updated_at DESC
                        LIMIT 1
                    """)
                    row = cursor.fetchone()
                    
                    if row:
                        prompt_configured = True
                        prompt_info = {
                            "setting_key": row['setting_key'],
                            "document_id": row['prompt_document_id'],
                            "document_title": row['title']
                        }
                    else:
                        # Check if any prompt documents exist
                        cursor = conn.execute("""
                            SELECT COUNT(*) as count FROM user_documents 
                            WHERE document_type = 'prompt'
                        """)
                        prompt_count = cursor.fetchone()['count']
                        prompt_info = {
                            "total_prompt_documents": prompt_count,
                            "configured": False
                        }
                        
            except Exception as e:
                prompt_info = {"database_error": str(e)}
        
        # Check document service
        document_service_available = startup_service.document_service is not None
        
        # Overall summary readiness
        summary_ready = (
            llm_service_available and 
            llm_provider_available and 
            prompt_configured and 
            document_service_available
        )
        
        return {
            "summary_ready": summary_ready,
            "components": {
                "llm_service": {
                    "available": llm_service_available,
                    "provider": llm_provider_info
                },
                "prompt": {
                    "configured": prompt_configured,
                    "details": prompt_info
                },
                "document_service": {
                    "available": document_service_available
                }
            },
            "recommendations": _get_recommendations(
                llm_service_available,
                llm_provider_available, 
                prompt_configured,
                document_service_available
            )
        }
        
    except Exception as e:
        logger.error(f"Error in summary status diagnostic: {e}")
        raise HTTPException(status_code=500, detail=f"Diagnostic failed: {str(e)}")

def _get_recommendations(llm_service: bool, llm_provider: bool, prompt: bool, document_service: bool) -> list:
    """Generate troubleshooting recommendations"""
    recommendations = []
    
    if not llm_service:
        recommendations.append("LLM service not initialized - check startup logs")
    
    if not llm_provider:
        recommendations.append("LLM provider not configured - check Ollama/OpenAI settings")
    
    if not prompt:
        recommendations.append("No summary prompt configured - create prompt document and set as summary prompt")
    
    if not document_service:
        recommendations.append("Document service not available - check service initialization")
    
    if llm_service and llm_provider and prompt and document_service:
        recommendations.append("All components ready - summary should be working!")
    
    return recommendations

@router.get("/prompt-settings")
async def get_prompt_settings_debug(registry = Depends(get_dependency_registry)) -> Dict[str, Any]:
    """Debug prompt_settings table contents"""
    try:
        startup_service = registry.get_startup_service()
        if not startup_service or not startup_service.database:
            raise HTTPException(status_code=503, detail="Database not available")
        
        with startup_service.database.get_connection() as conn:
            # Get all prompt settings
            cursor = conn.execute("""
                SELECT ps.*, ud.title as document_title
                FROM prompt_settings ps
                LEFT JOIN user_documents ud ON ps.prompt_document_id = ud.id
                ORDER BY ps.updated_at DESC
            """)
            settings = [dict(row) for row in cursor.fetchall()]
            
            # Get all prompt documents
            cursor = conn.execute("""
                SELECT id, title, created_at, updated_at 
                FROM user_documents 
                WHERE document_type = 'prompt'
                ORDER BY updated_at DESC
            """)
            documents = [dict(row) for row in cursor.fetchall()]
            
            return {
                "prompt_settings": settings,
                "prompt_documents": documents,
                "total_settings": len(settings),
                "total_documents": len(documents),
                "active_settings": len([s for s in settings if s.get('is_active')])
            }
            
    except Exception as e:
        logger.error(f"Error in prompt settings debug: {e}")
        raise HTTPException(status_code=500, detail=f"Debug failed: {str(e)}")