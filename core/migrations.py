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


class NewsTableMigration(BaseMigration):
    """Add news articles table"""
    
    @property
    def version(self) -> str:
        return "004_news_table"
    
    @property
    def description(self) -> str:
        return "Add news articles table for news ingestion"
    
    def up(self, conn: sqlite3.Connection) -> None:
        """Create news table"""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                link TEXT NOT NULL UNIQUE,
                snippet TEXT,
                thumbnail_url TEXT,
                published_datetime_utc TEXT,
                days_date TEXT NOT NULL
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Indexes for news table
        conn.execute("CREATE INDEX IF NOT EXISTS idx_news_snippet ON news(snippet)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_news_title ON news(title)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_news_days_date ON news(days_date)")
        

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


class TweetsTableMigration(BaseMigration):
    """Add tweets table"""

    @property
    def version(self) -> str:
        return "006_tweets_table"

    @property
    def description(self) -> str:
        return "Add tweets table for Twitter data"

    def up(self, conn: sqlite3.Connection) -> None:
        """Create tweets table"""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tweets (
                tweet_id TEXT PRIMARY KEY,
                created_at TEXT,
                days_date TEXT,
                text TEXT,
                media_urls TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tweets_days_date ON tweets(days_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tweets_text ON tweets(text)")



class MigrationRunner:
    """Handles database migration execution"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.migrations: List[BaseMigration] = [
            InitialSchemaMigration(),
            IndexesMigration(),
            ChatMessagesMigration(),
            NewsTableMigration(),
            WeatherTableMigration(),
            TweetsTableMigration(),
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