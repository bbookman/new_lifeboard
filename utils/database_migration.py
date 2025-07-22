"""Database migration utility for enhanced preprocessing schema."""

import os
import shutil
import sqlite3
import json
from datetime import datetime
from pathlib import Path

from core.database import DatabaseManager
from core.logger import Logger

logger = Logger(__name__)

class DatabaseMigration:
    """Handles database schema migration and data preservation."""
    
    def __init__(self, db_path: str = "data/lifeboard.db"):
        """Initialize migration utility.
        
        Args:
            db_path: Path to the database file
        """
        self.db_path = db_path
        self.backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.temp_path = f"{db_path}.migration_temp"
        
    def backup_database(self) -> bool:
        """Create a backup of the current database.
        
        Returns:
            True if backup successful, False otherwise
        """
        try:
            if os.path.exists(self.db_path):
                shutil.copy2(self.db_path, self.backup_path)
                logger.info(f"Database backed up to: {self.backup_path}")
                return True
            else:
                logger.info("No existing database to backup")
                return True
        except Exception as e:
            logger.error(f"Failed to backup database: {e}")
            return False
    
    def extract_existing_data(self) -> dict:
        """Extract data from existing database before migration.
        
        Returns:
            Dictionary containing extracted data
        """
        extracted_data = {
            'data_sources': [],
            'data_items': [],
            'embeddings': [],
            'conversations': [],
            'user_interactions': []
        }
        
        if not os.path.exists(self.db_path):
            logger.info("No existing database found")
            return extracted_data
            
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            
            # Extract data_sources
            cursor = conn.execute("SELECT * FROM data_sources")
            extracted_data['data_sources'] = [dict(row) for row in cursor.fetchall()]
            
            # Extract data_items
            cursor = conn.execute("SELECT * FROM data_items")
            extracted_data['data_items'] = [dict(row) for row in cursor.fetchall()]
            
            # Extract embeddings if table exists
            try:
                cursor = conn.execute("SELECT * FROM embeddings")
                extracted_data['embeddings'] = [dict(row) for row in cursor.fetchall()]
            except sqlite3.OperationalError:
                logger.info("No embeddings table found")
            
            # Extract conversations if table exists
            try:
                cursor = conn.execute("SELECT * FROM conversations")
                extracted_data['conversations'] = [dict(row) for row in cursor.fetchall()]
            except sqlite3.OperationalError:
                logger.info("No conversations table found")
            
            # Extract user_interactions if table exists
            try:
                cursor = conn.execute("SELECT * FROM user_interactions")
                extracted_data['user_interactions'] = [dict(row) for row in cursor.fetchall()]
            except sqlite3.OperationalError:
                logger.info("No user_interactions table found")
            
            conn.close()
            logger.info(f"Extracted {len(extracted_data['data_items'])} data items")
            
        except Exception as e:
            logger.error(f"Failed to extract data: {e}")
            
        return extracted_data
    
    def migrate_data_items(self, extracted_data: dict, db_manager: DatabaseManager) -> bool:
        """Migrate data items with new schema fields.
        
        Args:
            extracted_data: Previously extracted data
            db_manager: New database manager instance
            
        Returns:
            True if migration successful
        """
        try:
            data_items = extracted_data.get('data_items', [])
            
            for item in data_items:
                # Prepare new fields with defaults
                migrated_item = {
                    'id': item['id'],
                    'namespace': item['namespace'],
                    'source_id': item['source_id'],
                    'content': item['content'],
                    'metadata': item.get('metadata'),
                    'summary_content': None,  # Will be populated by preprocessing
                    'named_entities': None,   # Will be populated by preprocessing
                    'content_classification': None,  # Will be populated by preprocessing
                    'temporal_context': None,  # Will be populated by preprocessing
                    'conversation_turns': None,  # Will be populated by preprocessing
                    'content_quality_score': None,  # Will be calculated during preprocessing
                    'semantic_density': None,  # Will be calculated during preprocessing
                    'created_at': item.get('created_at'),
                    'updated_at': datetime.now().isoformat(),
                    'embedding_status': 'pending',  # Force re-embedding with new models
                    'preprocessing_status': 'pending'  # New field for preprocessing tracking
                }
                
                # Insert migrated item
                db_manager.add_data_item(
                    namespace=migrated_item['namespace'],
                    source_id=migrated_item['source_id'],
                    content=migrated_item['content'],
                    metadata=migrated_item['metadata'],
                    item_id=migrated_item['id']
                )
                
            logger.info(f"Migrated {len(data_items)} data items")
            return True
            
        except Exception as e:
            logger.error(f"Failed to migrate data items: {e}")
            return False
    
    def migrate_other_tables(self, extracted_data: dict, db_manager: DatabaseManager) -> bool:
        """Migrate other tables that don't require schema changes.
        
        Args:
            extracted_data: Previously extracted data
            db_manager: New database manager instance
            
        Returns:
            True if migration successful
        """
        try:
            conn = db_manager._get_connection()
            
            # Migrate data_sources
            for source in extracted_data.get('data_sources', []):
                conn.execute("""
                    INSERT OR REPLACE INTO data_sources 
                    (namespace, source_type, config, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    source['namespace'],
                    source['source_type'],
                    source.get('config'),
                    source.get('status', 'active'),
                    source.get('created_at'),
                    source.get('updated_at', datetime.now().isoformat())
                ))
            
            # Migrate conversations if they exist
            for conv in extracted_data.get('conversations', []):
                conn.execute("""
                    INSERT OR REPLACE INTO conversations 
                    (id, title, created_at, updated_at, metadata)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    conv['id'],
                    conv.get('title'),
                    conv.get('created_at'),
                    conv.get('updated_at'),
                    conv.get('metadata')
                ))
            
            # Migrate user_interactions if they exist
            for interaction in extracted_data.get('user_interactions', []):
                conn.execute("""
                    INSERT OR REPLACE INTO user_interactions 
                    (id, conversation_id, user_message, assistant_response, 
                     created_at, feedback, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    interaction['id'],
                    interaction.get('conversation_id'),
                    interaction.get('user_message'),
                    interaction.get('assistant_response'),
                    interaction.get('created_at'),
                    interaction.get('feedback'),
                    interaction.get('metadata')
                ))
            
            conn.commit()
            logger.info("Migrated supplementary tables successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to migrate supplementary tables: {e}")
            return False
    
    def perform_migration(self) -> bool:
        """Perform the complete database migration.
        
        Returns:
            True if migration successful
        """
        try:
            logger.info("Starting database migration...")
            
            # Step 1: Backup existing database
            if not self.backup_database():
                return False
            
            # Step 2: Extract existing data
            extracted_data = self.extract_existing_data()
            
            # Step 3: Remove old database
            if os.path.exists(self.db_path):
                os.remove(self.db_path)
                logger.info("Removed old database")
            
            # Step 4: Create new database with updated schema
            db_manager = DatabaseManager()
            db_manager.initialize_database()
            logger.info("Created new database with updated schema")
            
            # Step 5: Migrate data
            if not self.migrate_data_items(extracted_data, db_manager):
                return False
                
            if not self.migrate_other_tables(extracted_data, db_manager):
                return False
            
            logger.info("Database migration completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            self.rollback_migration()
            return False
    
    def rollback_migration(self) -> bool:
        """Rollback migration by restoring backup.
        
        Returns:
            True if rollback successful
        """
        try:
            if os.path.exists(self.backup_path):
                if os.path.exists(self.db_path):
                    os.remove(self.db_path)
                shutil.copy2(self.backup_path, self.db_path)
                logger.info("Migration rolled back successfully")
                return True
            else:
                logger.error("No backup found for rollback")
                return False
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False
    
    def cleanup_migration(self) -> None:
        """Clean up temporary files after successful migration."""
        try:
            # Keep backup for safety, but remove temp files
            if os.path.exists(self.temp_path):
                os.remove(self.temp_path)
            logger.info("Migration cleanup completed")
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")


def main():
    """Main migration script."""
    migration = DatabaseMigration()
    
    if migration.perform_migration():
        print("✓ Database migration completed successfully!")
        print(f"Backup saved at: {migration.backup_path}")
        migration.cleanup_migration()
    else:
        print("✗ Database migration failed!")
        print("Check logs for details")


if __name__ == "__main__":
    main()