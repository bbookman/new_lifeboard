"""
Database migration system for Lifeboard

This module provides a clean separation of database schema creation
from the main DatabaseService class, following the single responsibility principle.
"""

import sqlite3
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class BaseMigration(ABC):
    """Base class for database migrations"""
    
    @property
    @abstractmethod
    def version(self) -> str:
        """Migration version identifier"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of the migration"""
        pass
    
    @abstractmethod
    def up(self, conn: sqlite3.Connection) -> None:
        """Apply the migration"""
        pass
    
    def down(self, conn: sqlite3.Connection) -> None:
        """Rollback the migration (optional)"""
        raise NotImplementedError(f"Rollback not implemented for {self.version}")


class InitialSchemaMigration(BaseMigration):
    """Initial database schema creation"""
    
    @property
    def version(self) -> str:
        return "001_initial_schema"
    
    @property
    def description(self) -> str:
        return "Create initial database schema with core tables"
    
    def up(self, conn: sqlite3.Connection) -> None:
        """Create initial schema"""
        # System settings table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Data sources registry
        conn.execute("""
            CREATE TABLE IF NOT EXISTS data_sources (
                namespace TEXT PRIMARY KEY,
                source_type TEXT NOT NULL,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                item_count INTEGER DEFAULT 0,
                metadata TEXT,
                is_active BOOLEAN DEFAULT TRUE
            )
        """)
        
        # Unified data storage
        conn.execute("""
            CREATE TABLE IF NOT EXISTS data_items (
                id TEXT PRIMARY KEY,
                namespace TEXT NOT NULL,
                source_id TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                days_date DATE,
                embedding_status TEXT DEFAULT 'pending',
                FOREIGN KEY (namespace) REFERENCES data_sources(namespace)
            )
        """)


class IndexesMigration(BaseMigration):
    """Create database indexes for performance"""
    
    @property
    def version(self) -> str:
        return "002_indexes"
    
    @property
    def description(self) -> str:
        return "Create indexes for performance optimization"
    
    def up(self, conn: sqlite3.Connection) -> None:
        """Create indexes"""
        conn.execute("CREATE INDEX IF NOT EXISTS idx_data_items_namespace ON data_items(namespace)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_data_items_embedding_status ON data_items(embedding_status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_data_items_updated_at ON data_items(updated_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_data_items_days_date ON data_items(days_date)")


class ChatMessagesMigration(BaseMigration):
    """Add chat messages table for Phase 7"""
    
    @property
    def version(self) -> str:
        return "003_chat_messages"
    
    @property
    def description(self) -> str:
        return "Add chat messages table for conversation history"
    
    def up(self, conn: sqlite3.Connection) -> None:
        """Create chat messages table"""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_message TEXT NOT NULL,
                assistant_response TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Index for chat messages
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_timestamp ON chat_messages(timestamp)")



class WeatherTableMigration(BaseMigration):
    """Add weather table"""

    @property
    def version(self) -> str:
        return "005_weather_table"

    @property
    def description(self) -> str:
        return "Add weather table for weather data"

    def up(self, conn: sqlite3.Connection) -> None:
        """Create weather table"""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS weather (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                days_date TEXT NOT NULL,
                response_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("CREATE INDEX IF NOT EXISTS idx_weather_days_date ON weather(days_date)")




class TwoKeyMetadataMigration(BaseMigration):
    """Migrate to two-key metadata structure and add semantic processing status"""
    
    @property
    def version(self) -> str:
        return "007_two_key_metadata"
    
    @property
    def description(self) -> str:
        return "Migrate to two-key metadata structure (original_response + processed_response)"
    
    def up(self, conn: sqlite3.Connection) -> None:
        """Apply two-key metadata migration"""
        import json
        from datetime import datetime
        
        logger.info("Starting two-key metadata migration...")
        
        # Add new columns for semantic processing status tracking
        # Note: semantic_status is handled by 0007_add_semantic_status_tracking migration
        # This was originally here but moved to a separate migration for better organization
            
        try:
            conn.execute("ALTER TABLE data_items ADD COLUMN semantic_processed_at TIMESTAMP")
        except sqlite3.OperationalError:
            # Column already exists
            pass
            
        try:
            conn.execute("ALTER TABLE data_items ADD COLUMN processing_priority INTEGER DEFAULT 1")
        except sqlite3.OperationalError:
            # Column already exists
            pass
        
        # Create indexes for efficient status queries
        conn.execute("CREATE INDEX IF NOT EXISTS idx_semantic_status_date ON data_items(semantic_status, days_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_processed_at ON data_items(semantic_processed_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_semantic_queue ON data_items(semantic_status, processing_priority, days_date, created_at)")
        
        # Migrate existing metadata structure
        logger.info("Migrating existing metadata to two-key structure...")
        
        cursor = conn.execute("SELECT id, metadata FROM data_items WHERE namespace = 'limitless' AND metadata IS NOT NULL")
        rows = cursor.fetchall()
        
        migrated_count = 0
        error_count = 0
        
        for row in rows:
            try:
                # Parse existing metadata
                old_metadata = json.loads(row['metadata']) if row['metadata'] else {}
                
                # Create new two-key structure
                new_metadata = self._migrate_metadata_to_two_key(old_metadata)
                priority = self._determine_priority(old_metadata)
                
                # Update record with new structure
                conn.execute("""
                    UPDATE data_items 
                    SET metadata = ?, semantic_status = 'pending', processing_priority = ? 
                    WHERE id = ?
                """, (json.dumps(new_metadata), priority, row['id']))
                
                migrated_count += 1
                
                if migrated_count % 100 == 0:
                    logger.info(f"Migrated {migrated_count} records...")
                    
            except Exception as e:
                logger.error(f"Error migrating record {row['id']}: {e}")
                error_count += 1
                continue
        
        logger.info(f"Migration completed: {migrated_count} records migrated, {error_count} errors")
    
    def _migrate_metadata_to_two_key(self, old_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Convert old mixed metadata structure to clean two-key architecture"""
        # Extract original Limitless API response
        original_lifelog = old_metadata.get('original_lifelog', {})
        
        # Create processed response from existing processed fields
        processed_response = {
            # Processing metadata
            'processing_history': old_metadata.get('processing_history', []),
            'semantic_metadata': {'processed': False},  # Will be updated when semantic processing runs
            
            # Basic extracted fields (from original processors)
            'title': old_metadata.get('title'),
            'start_time': old_metadata.get('start_time'),
            'end_time': old_metadata.get('end_time'),
            'is_starred': old_metadata.get('is_starred', False),
            'updated_at': old_metadata.get('updated_at'),
            'speakers': old_metadata.get('speakers', []),
            'content_types': old_metadata.get('content_types', []),
            'has_markdown': old_metadata.get('has_markdown', False),
            'node_count': old_metadata.get('node_count', 0),
            
            # Content statistics
            'content_stats': old_metadata.get('content_stats', {}),
            'duration_seconds': old_metadata.get('duration_seconds'),
            'duration_minutes': old_metadata.get('duration_minutes'),
            'conversation_metadata': old_metadata.get('conversation_metadata', {}),
            
            # Segmentation data
            'segmentation': old_metadata.get('segmentation', {}),
            
            # Cleaned content (if exists)
            'cleaned_markdown': old_metadata.get('cleaned_markdown'),
            
            # Semantic deduplication placeholders (will be populated when processing runs)
            'display_conversation': [],
            'semantic_clusters': {}
        }
        
        # Remove None values from processed_response
        processed_response = {k: v for k, v in processed_response.items() if v is not None}
        
        # Create new two-key structure
        return {
            'original_response': original_lifelog,
            'processed_response': processed_response
        }
    
    def _determine_priority(self, old_metadata: Dict[str, Any]) -> int:
        """Determine processing priority based on metadata"""
        from datetime import datetime, timezone, timedelta
        
        # Try to get start time for priority calculation
        start_time_str = old_metadata.get('start_time')
        if not start_time_str:
            return 1  # Normal priority for conversations without timestamps
        
        try:
            # Parse start time
            if start_time_str.endswith('Z'):
                start_time_str = start_time_str.replace('Z', '+00:00')
            
            start_time = datetime.fromisoformat(start_time_str)
            now = datetime.now(timezone.utc)
            
            # Calculate age
            age = now - start_time
            
            if age <= timedelta(days=2):
                return 3  # Urgent: today/yesterday
            elif age <= timedelta(days=7):
                return 2  # High: this week
            else:
                return 1  # Normal: older
                
        except Exception:
            return 1  # Default to normal priority if date parsing fails


class MigrationRunner:
    """Handles database migration execution"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.migrations: List[BaseMigration] = [
            InitialSchemaMigration(),
            IndexesMigration(),
            ChatMessagesMigration(),
            WeatherTableMigration(),
            SemanticDeduplicationMigration(),
            SemanticStatusTrackingMigration(),
            TwoKeyMetadataMigration(),
            IngestionStatusMigration(),
            UserDocumentsMigration(),
            VirtualDirectoriesMigration(),
        ]
    
    @contextmanager
    def get_connection(self):
        """Get database connection with proper setup"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def initialize_migration_table(self, conn: sqlite3.Connection) -> None:
        """Create migration tracking table"""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    
    def get_applied_migrations(self, conn: sqlite3.Connection) -> List[str]:
        """Get list of already applied migrations"""
        try:
            cursor = conn.execute("SELECT version FROM schema_migrations ORDER BY version")
            return [row['version'] for row in cursor.fetchall()]
        except sqlite3.OperationalError:
            # Migration table doesn't exist yet
            return []
    
    def record_migration(self, conn: sqlite3.Connection, migration: BaseMigration) -> None:
        """Record that a migration has been applied"""
        conn.execute("""
            INSERT INTO schema_migrations (version, description)
            VALUES (?, ?)
        """, (migration.version, migration.description))
    
    def run_migrations(self) -> Dict[str, Any]:
        """Run all pending migrations"""
        result = {
            "success": True,
            "applied_migrations": [],
            "errors": []
        }
        
        with self.get_connection() as conn:
            try:
                # Initialize migration tracking
                self.initialize_migration_table(conn)
                
                # Get applied migrations
                applied = set(self.get_applied_migrations(conn))
                
                # Run pending migrations
                for migration in self.migrations:
                    if migration.version not in applied:
                        try:
                            logger.info(f"Applying migration {migration.version}: {migration.description}")
                            migration.up(conn)
                            self.record_migration(conn, migration)
                            result["applied_migrations"].append(migration.version)
                            logger.info(f"Successfully applied migration {migration.version}")
                        except Exception as e:
                            error_msg = f"Failed to apply migration {migration.version}: {str(e)}"
                            logger.error(error_msg)
                            result["errors"].append(error_msg)
                            result["success"] = False
                            break
                
                if result["success"]:
                    conn.commit()
                else:
                    conn.rollback()
                    
            except Exception as e:
                error_msg = f"Migration runner failed: {str(e)}"
                logger.error(error_msg)
                result["errors"].append(error_msg)
                result["success"] = False
                conn.rollback()
        
        return result
    
    def get_migration_status(self) -> Dict[str, Any]:
        """Get current migration status"""
        with self.get_connection() as conn:
            try:
                self.initialize_migration_table(conn)
                applied = set(self.get_applied_migrations(conn))
                
                status = {
                    "total_migrations": len(self.migrations),
                    "applied_count": len(applied),
                    "pending_count": len(self.migrations) - len(applied),
                    "migrations": []
                }
                
                for migration in self.migrations:
                    status["migrations"].append({
                        "version": migration.version,
                        "description": migration.description,
                        "applied": migration.version in applied
                    })
                
                return status
                
            except Exception as e:
                return {
                    "error": str(e),
                    "total_migrations": len(self.migrations),
                    "applied_count": 0,
                    "pending_count": len(self.migrations)
                }


# Wrapper classes for module-based migrations in versions/ directory
class VersionMigrationAdapter(BaseMigration):
    """Adapter to use module-based migrations with the class-based system"""
    
    def __init__(self, module_name: str, version: str, description: str):
        self._module_name = module_name
        self._version = version
        self._description = description
        self._module = None
    
    @property
    def version(self) -> str:
        return self._version
    
    @property
    def description(self) -> str:
        return self._description
    
    def _get_module(self):
        """Import the migration module"""
        if self._module is None:
            import importlib
            self._module = importlib.import_module(f"core.migrations.versions.{self._module_name}")
        return self._module
    
    def up(self, conn: sqlite3.Connection) -> None:
        """Apply the migration"""
        module = self._get_module()
        module.up(conn)
    
    def down(self, conn: sqlite3.Connection) -> None:
        """Rollback the migration"""
        module = self._get_module()
        if hasattr(module, 'down'):
            module.down(conn)
        else:
            super().down(conn)


class SemanticDeduplicationMigration(VersionMigrationAdapter):
    """Migration for semantic deduplication tables"""
    
    def __init__(self):
        super().__init__(
            "0006_add_semantic_deduplication_tables",
            "0006_add_semantic_deduplication_tables", 
            "Add semantic deduplication tables"
        )


class SemanticStatusTrackingMigration(VersionMigrationAdapter):
    """Migration for semantic status tracking"""
    
    def __init__(self):
        super().__init__(
            "0007_add_semantic_status_tracking",
            "0007_add_semantic_status_tracking",
            "Add semantic status tracking"
        )


class IngestionStatusMigration(VersionMigrationAdapter):
    """Migration for ingestion status column"""
    
    def __init__(self):
        super().__init__(
            "0008_add_ingestion_status_to_data_items",
            "0008_add_ingestion_status_to_data_items",
            "Add ingestion status to data_items"
        )


class UserDocumentsMigration(VersionMigrationAdapter):
    """Migration for user documents tables"""
    
    def __init__(self):
        super().__init__(
            "0009_add_user_documents",
            "0009_add_user_documents",
            "Add user documents tables for Notes & Prompts feature"
        )


class VirtualDirectoriesMigration(VersionMigrationAdapter):
    """Migration for virtual directory support"""
    
    def __init__(self):
        super().__init__(
            "0010_add_virtual_directories", 
            "0010_add_virtual_directories",
            "Add path and is_folder columns for virtual directory support"
        )