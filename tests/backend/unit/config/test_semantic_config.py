#!/usr/bin/env python3
"""
Test semantic deduplication configuration
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.async_database import AsyncDatabaseService
from core.embeddings import EmbeddingService
from services.ingestion import IngestionService

def test_semantic_config():
    """Test that semantic deduplication is properly configured"""
    try:
        print("Testing semantic deduplication configuration...")
        
        # Initialize services
        database_service = AsyncDatabaseService()
        embedding_service = EmbeddingService()
        
        # Initialize ingestion service with semantic deduplication enabled
        ingestion_service = IngestionService(database_service, None, embedding_service)
        
        # Check LimitlessProcessor configuration
        limitless_processor = ingestion_service.processors.get("limitless")
        if limitless_processor:
            print(f"✅ LimitlessProcessor found")
            print(f"✅ Semantic deduplication enabled: {limitless_processor.enable_semantic_deduplication}")
            
            if limitless_processor.enable_semantic_deduplication:
                print(f"✅ Semantic processor initialized: {hasattr(limitless_processor, 'semantic_processor')}")
                
                # Get pipeline info
                pipeline_info = limitless_processor.get_pipeline_info()
                print(f"✅ Pipeline version: {pipeline_info['pipeline_version']}")
                print(f"✅ Semantic deduplication enabled: {pipeline_info['semantic_deduplication_enabled']}")
                print(f"✅ Supports batch processing: {pipeline_info['supports_batch_processing']}")
                print(f"✅ Processors: {pipeline_info['processors']}")
                
                print("\n🎉 Semantic deduplication is properly configured!")
                return True
            else:
                print("❌ Semantic deduplication is disabled")
                return False
        else:
            print("❌ LimitlessProcessor not found")
            return False
            
    except Exception as e:
        print(f"❌ Error testing configuration: {e}")
        return False

if __name__ == "__main__":
    success = test_semantic_config()
    sys.exit(0 if success else 1)