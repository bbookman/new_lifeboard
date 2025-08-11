#!/usr/bin/env python3
"""
Batch process existing conversations with semantic deduplication
"""
import sys
import os
import json
import asyncio
import logging
from typing import List, Dict, Any
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import DatabaseService
from core.embeddings import EmbeddingService
from sources.limitless_processor import LimitlessProcessor
from sources.base import DataItem
from config.factory import ConfigFactory
from core.logging_config import setup_application_logging

async def process_conversations_batch():
    """Process existing conversations with semantic deduplication"""
    # Set up logging
    setup_application_logging()
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("Starting batch processing of existing conversations...")
        
        # Initialize services
        config = ConfigFactory.create_config()
        database_service = DatabaseService()
        embedding_service = EmbeddingService(config.embeddings)
        
        # Initialize embedding model
        logger.info("Loading embedding model...")
        await embedding_service._initialize_service()
        logger.info(f"Embedding model loaded: {embedding_service.model_name}")
        
        # Initialize processor with semantic deduplication enabled
        processor = LimitlessProcessor(
            enable_segmentation=True,
            enable_markdown_generation=True,
            enable_semantic_deduplication=True,
            embedding_service=embedding_service
        )
        
        # Get pending conversations from database
        logger.info("Fetching conversations pending semantic processing...")
        
        with database_service.get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, namespace, source_id, content, metadata, days_date, created_at, updated_at
                FROM data_items 
                WHERE namespace = 'limitless' 
                AND semantic_status = 'pending'
                ORDER BY processing_priority DESC, days_date DESC
                LIMIT 100
            """)
            rows = cursor.fetchall()
        
        if not rows:
            logger.info("No conversations found pending semantic processing")
            return True
        
        logger.info(f"Found {len(rows)} conversations to process")
        
        # Convert database rows to DataItem objects
        conversations = []
        for row in rows:
            # Parse metadata
            metadata = json.loads(row['metadata']) if row['metadata'] else {}
            
            # Create DataItem
            item = DataItem(
                namespace=row['namespace'],
                source_id=row['source_id'],
                content=row['content'] or '',
                created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else datetime.now(),
                updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else datetime.now(),
                metadata=metadata
            )
            conversations.append((row['id'], item))
        
        # Process conversations in batches
        logger.info(f"Processing {len(conversations)} conversations with semantic deduplication...")
        
        # Extract just the DataItems for batch processing
        items_to_process = [item for _, item in conversations]
        
        # Process through semantic deduplication
        processed_items = await processor.process_batch(items_to_process)
        
        # Update database with processed results
        logger.info("Updating database with processed results...")
        
        with database_service.get_connection() as conn:
            updated_count = 0
            
            for i, processed_item in enumerate(processed_items):
                item_id = conversations[i][0]  # Get the original ID
                
                try:
                    # Update the record with new metadata and status
                    conn.execute("""
                        UPDATE data_items 
                        SET metadata = ?, 
                            semantic_status = 'completed',
                            semantic_processed_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (json.dumps(processed_item.metadata), item_id))
                    
                    updated_count += 1
                    
                    if updated_count % 10 == 0:
                        logger.info(f"Updated {updated_count}/{len(processed_items)} conversations...")
                        
                except Exception as e:
                    logger.error(f"Error updating conversation {item_id}: {e}")
                    continue
            
            conn.commit()
            logger.info(f"Successfully updated {updated_count} conversations in database")
        
        # Verify results
        logger.info("Verifying semantic processing results...")
        
        with database_service.get_connection() as conn:
            # Check how many were marked as completed
            cursor = conn.execute("""
                SELECT COUNT(*) as completed_count 
                FROM data_items 
                WHERE namespace = 'limitless' 
                AND semantic_status = 'completed'
            """)
            completed_count = cursor.fetchone()['completed_count']
            
            # Check remaining pending
            cursor = conn.execute("""
                SELECT COUNT(*) as pending_count 
                FROM data_items 
                WHERE namespace = 'limitless' 
                AND semantic_status = 'pending'
            """)
            pending_count = cursor.fetchone()['pending_count']
            
            logger.info(f"✅ Completed conversations: {completed_count}")
            logger.info(f"⏳ Remaining pending: {pending_count}")
            
            # Sample check of processed metadata
            cursor = conn.execute("""
                SELECT metadata FROM data_items 
                WHERE namespace = 'limitless' 
                AND semantic_status = 'completed'
                LIMIT 1
            """)
            sample_row = cursor.fetchone()
            
            if sample_row:
                metadata = json.loads(sample_row['metadata'])
                processed_response = metadata.get('processed_response', {})
                semantic_metadata = processed_response.get('semantic_metadata', {})
                
                logger.info(f"✅ Sample semantic processing status: processed={semantic_metadata.get('processed', False)}")
                logger.info(f"✅ Sample display conversation items: {len(processed_response.get('display_conversation', []))}")
                logger.info(f"✅ Sample semantic clusters: {len(processed_response.get('semantic_clusters', {}))}")
        
        logger.info("🎉 Batch processing completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Batch processing failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(process_conversations_batch())
    sys.exit(0 if success else 1)