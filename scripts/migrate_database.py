#!/usr/bin/env python3
"""Script to run database migration."""

import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.database_migration import DatabaseMigration

if __name__ == "__main__":
    print("🔄 Starting database migration...")
    migration = DatabaseMigration()
    
    if migration.perform_migration():
        print("✅ Database migration completed successfully!")
        print(f"📁 Backup saved at: {migration.backup_path}")
        migration.cleanup_migration()
        print("🧹 Migration cleanup completed")
    else:
        print("❌ Database migration failed!")
        print("📋 Check logs for details")
        sys.exit(1)