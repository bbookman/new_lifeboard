"""
Simplified Database Bootstrap Runner for Lifeboard

Replaces the complex migration system with a single bootstrap approach
suitable for test/development environments where the database is frequently deleted.
"""

import sqlite3
import logging
from contextlib import contextmanager
from typing import Dict, Any

from .bootstrap_schema import bootstrap_database, is_database_initialized

logger = logging.getLogger(__name__)


class BootstrapRunner:
    """Simplified database bootstrap runner"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    @contextmanager
    def get_connection(self):
        """Get database connection with proper setup"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # Enable foreign key constraints
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
        finally:
            conn.close()
    
    def initialize_database(self) -> Dict[str, Any]:
        """Initialize database with complete schema"""
        result = {
            "success": True,
            "initialized": False,
            "already_exists": False,
            "errors": []
        }
        
        try:
            with self.get_connection() as conn:
                # Check if database is already initialized
                if is_database_initialized(conn):
                    logger.info("Database already initialized, skipping bootstrap")
                    result["already_exists"] = True
                    return result
                
                # Bootstrap the complete schema
                logger.info("Initializing database with complete schema...")
                bootstrap_database(conn)
                
                result["initialized"] = True
                logger.info("Database initialization completed successfully")
                
        except Exception as e:
            error_msg = f"Database initialization failed: {str(e)}"
            logger.error(error_msg)
            result["errors"].append(error_msg)
            result["success"] = False
        
        return result
    
    def get_database_status(self) -> Dict[str, Any]:
        """Get current database status"""
        try:
            with self.get_connection() as conn:
                is_initialized = is_database_initialized(conn)
                
                # Get table count
                cursor = conn.execute("""
                    SELECT COUNT(*) as table_count 
                    FROM sqlite_master 
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                """)
                table_count = cursor.fetchone()["table_count"]
                
                # Get basic stats
                stats = {
                    "initialized": is_initialized,
                    "table_count": table_count,
                    "database_path": self.db_path
                }
                
                if is_initialized:
                    # Get data item count
                    try:
                        cursor = conn.execute("SELECT COUNT(*) as count FROM data_items")
                        stats["data_items_count"] = cursor.fetchone()["count"]
                    except sqlite3.OperationalError:
                        stats["data_items_count"] = 0
                    
                    # Get namespace counts
                    try:
                        cursor = conn.execute("""
                            SELECT namespace, COUNT(*) as count 
                            FROM data_items 
                            GROUP BY namespace
                        """)
                        stats["namespace_counts"] = {
                            row["namespace"]: row["count"] 
                            for row in cursor.fetchall()
                        }
                    except sqlite3.OperationalError:
                        stats["namespace_counts"] = {}
                
                return stats
                
        except Exception as e:
            return {
                "error": str(e),
                "initialized": False,
                "table_count": 0,
                "database_path": self.db_path
            }
    
    def reset_database(self) -> Dict[str, Any]:
        """Reset database by dropping all tables and reinitializing"""
        result = {
            "success": True,
            "tables_dropped": 0,
            "reinitialized": False,
            "errors": []
        }
        
        try:
            with self.get_connection() as conn:
                # Get list of all tables
                cursor = conn.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                """)
                tables = [row["name"] for row in cursor.fetchall()]
                
                # Drop all tables
                for table in tables:
                    try:
                        conn.execute(f"DROP TABLE IF EXISTS {table}")
                        result["tables_dropped"] += 1
                        logger.info(f"Dropped table: {table}")
                    except Exception as e:
                        logger.warning(f"Could not drop table {table}: {e}")
                
                # Reinitialize with bootstrap
                logger.info("Reinitializing database...")
                bootstrap_database(conn)
                result["reinitialized"] = True
                
                logger.info(f"Database reset completed: {result['tables_dropped']} tables dropped and reinitialized")
                
        except Exception as e:
            error_msg = f"Database reset failed: {str(e)}"
            logger.error(error_msg)
            result["errors"].append(error_msg)
            result["success"] = False
        
        return result
    
    def run_migrations(self) -> Dict[str, Any]:
        """Legacy method for compatibility - delegates to initialize_database"""
        return self.initialize_database()
    
    def get_migration_status(self) -> Dict[str, Any]:
        """Legacy method for compatibility - delegates to get_database_status"""
        status = self.get_database_status()
        
        # Convert to legacy format
        return {
            "total_migrations": 1,
            "applied_count": 1 if status.get("initialized", False) else 0,
            "pending_count": 0 if status.get("initialized", False) else 1,
            "migrations": [{
                "version": "bootstrap_schema_complete",
                "description": "Complete database schema bootstrap",
                "applied": status.get("initialized", False)
            }]
        }