#!/usr/bin/env python3
"""
Chat Service Diagnosis Script
Validates chat service initialization during startup
"""

import logging
import sys
import os
import asyncio

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.startup import get_startup_service, StartupService
from config.factory import create_production_config

# Configure logging for diagnosis
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/Users/brucebookman/code/new_lifeboard/logs/chat_diagnosis.log')
    ]
)

logger = logging.getLogger(__name__)

async def diagnose_chat_service():
    """Diagnose chat service initialization issues"""
    logger.info("=== CHAT SERVICE DIAGNOSIS START ===")
    
    try:
        # Step 1: Check if startup service exists
        startup_service = get_startup_service()
        logger.info(f"1. Startup service exists: {startup_service is not None}")
        
        if startup_service is None:
            logger.error("DIAGNOSIS: Startup service is None - application not initialized")
            return False
            
        # Step 2: Check if startup service has chat_service attribute
        has_chat_attr = hasattr(startup_service, 'chat_service')
        logger.info(f"2. Startup service has chat_service attribute: {has_chat_attr}")
        
        if not has_chat_attr:
            logger.error("DIAGNOSIS: StartupService missing chat_service attribute")
            return False
            
        # Step 3: Check if chat service is initialized
        chat_service = getattr(startup_service, 'chat_service', None)
        logger.info(f"3. Chat service instance exists: {chat_service is not None}")
        
        if chat_service is None:
            logger.error("DIAGNOSIS: Chat service is None - not initialized during startup")
            
            # Step 4: Check startup service status
            try:
                status = startup_service.get_application_status()
                logger.info(f"4. Application status: {status.get('status', 'unknown')}")
                logger.info(f"   Services initialized: {status.get('services_initialized', [])}")
                logger.info(f"   Errors: {status.get('errors', [])}")
            except Exception as e:
                logger.error(f"4. Failed to get application status: {e}")
                
            return False
            
        # Step 5: Test chat service functionality
        logger.info(f"5. Chat service type: {type(chat_service)}")
        
        try:
            # Test basic method existence
            has_get_history = hasattr(chat_service, 'get_chat_history')
            has_process_message = hasattr(chat_service, 'process_chat_message')
            logger.info(f"   Has get_chat_history: {has_get_history}")
            logger.info(f"   Has process_chat_message: {has_process_message}")
            
            if has_get_history:
                history = chat_service.get_chat_history(limit=1)
                logger.info(f"   Chat history test successful: {len(history) if history else 0} items")
            
        except Exception as e:
            logger.error(f"5. Chat service functionality test failed: {e}")
            return False
            
        logger.info("=== CHAT SERVICE DIAGNOSIS: SUCCESS ===")
        return True
        
    except Exception as e:
        logger.error(f"=== CHAT SERVICE DIAGNOSIS FAILED: {e} ===")
        logger.exception("Full exception details:")
        return False

if __name__ == "__main__":
    result = asyncio.run(diagnose_chat_service())
    sys.exit(0 if result else 1)