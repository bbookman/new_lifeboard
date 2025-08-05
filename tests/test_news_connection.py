#!/usr/bin/env python3

import sys
import asyncio
sys.path.append('.')
from sources.news import NewsSource
from config.factory import get_config
from core.database import DatabaseService
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

async def test_news_connection():
    config = get_config()
    db = DatabaseService(':memory:')
    
    print("=== TESTING NEWS SOURCE CONNECTION METHOD ===")
    
    news_source = NewsSource(config.news, db)
    
    print(f"Is configured: {news_source.is_configured()}")
    print(f"API key configured: {config.news.is_api_key_configured()}")
    print(f"Endpoint configured: {config.news.is_endpoint_configured()}")
    print()
    
    try:
        # Test the connection method directly
        print("Calling test_connection()...")
        result = await news_source.test_connection()
        print(f"Connection test result: {result}")
        
        # If it failed, let's also test the HTTP client directly
        if not result:
            print()
            print("=== TESTING HTTP CLIENT DIRECTLY ===")
            try:
                client = await news_source._ensure_client()
                print(f"HTTP client created: {client}")
                
                print("Making test request...")
                response = await news_source._make_test_request(client)
                print(f"Test response status: {response.status_code}")
                print(f"Test response headers: {dict(response.headers)}")
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"Test response data keys: {list(data.keys())}")
                else:
                    print(f"Test response text: {response.text}")
                    
            except Exception as e:
                print(f"HTTP client test error: {e}")
                import traceback
                traceback.print_exc()
        
    except Exception as e:
        print(f"Connection test error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_news_connection())