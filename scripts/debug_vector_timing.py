#!/usr/bin/env python3
"""Debug script to analyze vector timing issues."""

import sys
import os
import sqlite3
import asyncio
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import DatabaseService
from core.vector_store import VectorStoreService
from core.embeddings import EmbeddingService
from services.ingestion import IngestionService
from core.logger import Logger

logger = Logger(__name__)

async def diagnose_vector_timing_issue():
    """Comprehensive diagnosis of vector timing issues."""
    
    print("🔍 VECTOR TIMING DIAGNOSTIC ANALYSIS")
    print("=" * 50)
    
    # Check 1: Database Schema Analysis
    print("\n📊 STEP 1: Database Schema Analysis")
    print("-" * 35)
    
    try:
        db_path = "data/lifeboard.db"
        if not os.path.exists(db_path):
            print("❌ CRITICAL: Database file does not exist!")
            print(f"   Expected path: {os.path.abspath(db_path)}")
            return False
            
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check data_items schema
        cursor.execute("PRAGMA table_info(data_items)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        print(f"✓ Database exists: {db_path}")
        print(f"✓ data_items columns: {len(column_names)}")
        
        # Check for new schema fields
        required_new_fields = [
            'summary_content', 'named_entities', 'content_classification', 
            'temporal_context', 'conversation_turns', 'content_quality_score',
            'semantic_density', 'preprocessing_status'
        ]
        
        missing_fields = [field for field in required_new_fields if field not in column_names]
        
        if missing_fields:
            print("❌ SCHEMA ISSUE FOUND:")
            print(f"   Missing fields: {missing_fields}")
            print("   🔥 ROOT CAUSE: Database migration not completed!")
            return False
        else:
            print("✅ Enhanced schema fields present")
            
        # Check data distribution
        cursor.execute("SELECT COUNT(*) FROM data_items")
        total_items = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM data_items WHERE embedding_status = 'pending'")
        pending_embeddings = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM data_items WHERE embedding_status = 'completed'")
        completed_embeddings = cursor.fetchone()[0]
        
        print(f"✓ Total data items: {total_items}")
        print(f"✓ Pending embeddings: {pending_embeddings}")
        print(f"✓ Completed embeddings: {completed_embeddings}")
        
        if total_items > 0 and completed_embeddings == 0:
            print("❌ VECTOR ISSUE FOUND:")
            print("   Data exists but NO completed embeddings!")
            print("   🔥 ROOT CAUSE: Embedding generation pipeline failed!")
            
        conn.close()
        
    except Exception as e:
        print(f"❌ Database analysis failed: {e}")
        return False
    
    # Check 2: Vector Store Analysis
    print("\n🗂️  STEP 2: Vector Store Analysis") 
    print("-" * 32)
    
    try:
        from config.models import AppConfig
        config = AppConfig()
        
        vector_store = VectorStoreService(config.vector_store)
        stats = vector_store.get_stats()
        
        print(f"✓ Vector store loaded")
        print(f"✓ Total vectors: {stats['total_vectors']}")
        print(f"✓ Dimension: {stats['dimension']}")
        print(f"✓ Index path: {stats['index_path']}")
        print(f"✓ ID map path: {stats['id_map_path']}")
        
        # Check if files exist
        index_exists = os.path.exists(stats['index_path'])
        id_map_exists = os.path.exists(stats['id_map_path'])
        
        print(f"✓ Index file exists: {index_exists}")
        print(f"✓ ID map file exists: {id_map_exists}")
        
        if stats['total_vectors'] == 0:
            print("❌ VECTOR STORE ISSUE:")
            print("   Vector store is empty!")
            
            if not index_exists or not id_map_exists:
                print("   🔥 ROOT CAUSE: Vector store files missing!")
            else:
                print("   🔥 ROOT CAUSE: Vectors not generated or not added to store!")
                
    except Exception as e:
        print(f"❌ Vector store analysis failed: {e}")
        return False
    
    # Check 3: Embedding Service Analysis
    print("\n🧠 STEP 3: Embedding Service Analysis")
    print("-" * 36)
    
    try:
        from config.models import AppConfig
        config = AppConfig()
        
        embedding_service = EmbeddingService(config.embedding)
        await embedding_service.initialize()
        
        if embedding_service.is_initialized:
            print("✅ Embedding service initialized successfully")
            
            # Test embedding generation
            test_embedding = await embedding_service.embed_text("test")
            if test_embedding is not None and len(test_embedding) > 0:
                print(f"✅ Test embedding generated: dimension {len(test_embedding)}")
            else:
                print("❌ EMBEDDING SERVICE ISSUE:")
                print("   Failed to generate test embedding!")
                print("   🔥 ROOT CAUSE: Embedding service malfunction!")
                return False
        else:
            print("❌ EMBEDDING SERVICE ISSUE:")
            print("   Embedding service failed to initialize!")
            print("   🔥 ROOT CAUSE: Embedding service initialization failed!")
            return False
            
    except Exception as e:
        print(f"❌ Embedding service analysis failed: {e}")
        print(f"   🔥 ROOT CAUSE: Embedding service error: {e}")
        return False
    
    # Check 4: Ingestion Pipeline Analysis
    print("\n⚡ STEP 4: Ingestion Pipeline Analysis")
    print("-" * 38)
    
    try:
        from config.models import AppConfig
        config = AppConfig()
        
        database = DatabaseService()
        vector_store = VectorStoreService(config.vector_store)
        embedding_service = EmbeddingService(config.embedding)
        await embedding_service.initialize()
        
        ingestion = IngestionService(database, vector_store, embedding_service, config)
        
        # Check for pending embeddings
        pending_result = await ingestion.process_pending_embeddings(batch_size=5)
        
        print(f"✓ Ingestion service initialized")
        print(f"✓ Pending embeddings processed: {pending_result['processed']}")
        print(f"✓ Successful embeddings: {pending_result['successful']}")
        print(f"✓ Failed embeddings: {pending_result['failed']}")
        
        if pending_result['errors']:
            print("❌ INGESTION PIPELINE ISSUES:")
            for error in pending_result['errors'][:3]:
                print(f"   - {error}")
            print("   🔥 ROOT CAUSE: Embedding pipeline failures!")
            
        return True
        
    except Exception as e:
        print(f"❌ Ingestion pipeline analysis failed: {e}")
        print(f"   🔥 ROOT CAUSE: Ingestion pipeline error: {e}")
        return False
    
    print("\n✅ DIAGNOSTIC ANALYSIS COMPLETED")
    return True

async def main():
    """Main diagnostic function."""
    try:
        success = await diagnose_vector_timing_issue()
        
        if success:
            print("\n🎯 RECOMMENDATIONS:")
            print("1. Run database migration: python scripts/migrate_database.py")
            print("2. Manually trigger embedding generation: check ingestion service")
            print("3. Verify vector store file permissions and paths")
        else:
            print("\n❌ CRITICAL ISSUES FOUND - See analysis above")
            
    except Exception as e:
        print(f"❌ Diagnostic failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())