#!/usr/bin/env python3

import sys
import asyncio
sys.path.append('.')
from sources.weather import WeatherSource
from config.factory import get_config
from core.database import DatabaseService
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

async def test_weather_connection():
    config = get_config()
    db = DatabaseService(':memory:')
    
    print("=== TESTING WEATHER SOURCE CONNECTION METHOD ===")
    
    weather_source = WeatherSource(config.weather, db)
    
    print(f"API key configured: {config.weather.is_api_key_configured()}")
    print(f"Endpoint configured: {config.weather.is_endpoint_configured()}")
    print()
    
    try:
        # Test the connection method directly
        print("Calling test_connection()...")
        result = await weather_source.test_connection()
        print(f"Connection test result: {result}")
        print(f"Result type: {type(result)}")
        
    except Exception as e:
        print(f"Connection test error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_weather_connection())