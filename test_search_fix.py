#!/usr/bin/env python3
"""
Test script to verify the document search functionality fix
"""

import asyncio
import sqlite3
import sys
import os
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from services.document_service import DocumentService
from core.database import DatabaseService
from core.vector_store import VectorStoreService
from core.embeddings import EmbeddingService
from config.models import AppConfig
from config.factory import ConfigFactory

async def test_search_functionality():
    """Test the enhanced search functionality"""
    print("🔍 Testing Document Search Functionality Fix")
    print("=" * 50)
    
    try:
        # Load configuration
        config = ConfigFactory.create_config()
        
        # Initialize services (mock for testing)
        db_service = DatabaseService(config.database)
        vector_service = VectorStoreService(config.vector_store)
        embedding_service = EmbeddingService(config.embeddings)
        
        # Initialize document service
        doc_service = DocumentService(
            database=db_service,
            vector_store=vector_service,
            embedding_service=embedding_service,
            config=config
        )
        
        print("✅ Services initialized successfully")
        
        # Test cases for the search functionality
        test_cases = [
            {
                "name": "Case-insensitive search",
                "query": "default",
                "expected": "Should find 'DEFAULT SUMMARY'"
            },
            {
                "name": "Partial word matching", 
                "query": "summ",
                "expected": "Should find documents with 'summary' in title/content"
            },
            {
                "name": "Multi-word search",
                "query": "default summary", 
                "expected": "Should find documents containing both words"
            },
            {
                "name": "Mixed case search",
                "query": "Default",
                "expected": "Should find 'DEFAULT SUMMARY' and 'default settings'"
            }
        ]
        
        print("\n🧪 Running Test Cases:")
        print("-" * 30)
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\nTest {i}: {test_case['name']}")
            print(f"Query: '{test_case['query']}'")
            print(f"Expected: {test_case['expected']}")
            
            # Test FTS5 search method directly
            try:
                results = await doc_service._try_fts5_search(test_case['query'], None, 10)
                print(f"FTS5 Results: {len(results)} documents found")
                
                if results:
                    for doc, score in results[:3]:  # Show top 3 results
                        print(f"  - {doc.title} (score: {score:.2f})")
                else:
                    # Test fallback LIKE search
                    fallback_results = await doc_service._try_like_search(test_case['query'], None, 10)
                    print(f"LIKE Fallback Results: {len(fallback_results)} documents found")
                    
                    for doc, score in fallback_results[:3]:
                        print(f"  - {doc.title} (score: {score:.2f})")
                
            except Exception as e:
                print(f"❌ Test failed: {e}")
        
        print("\n" + "=" * 50)
        print("✅ Search functionality test completed!")
        
    except Exception as e:
        print(f"❌ Test setup failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Check if we can run the test
    if not os.path.exists("lifeboard.db"):
        print("⚠️  Database file not found. Please ensure the application has been run at least once.")
        print("   This test requires existing documents in the database to verify search functionality.")
        sys.exit(1)
    
    # Run the test
    try:
        asyncio.run(test_search_functionality())
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()