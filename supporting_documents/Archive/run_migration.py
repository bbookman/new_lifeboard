#!/usr/bin/env python3
"""
Run database migrations for Lifeboard
"""
import sys
import os
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import DatabaseService
from core.logging_config import setup_application_logging

def main():
    """Run database migrations"""
    # Set up logging
    setup_application_logging()
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("Starting database migration...")
        
        # Initialize DatabaseService - this will automatically run migrations
        db_service = DatabaseService()
        
        logger.info("Database migration completed successfully!")
        return 0
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)