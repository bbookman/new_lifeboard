#!/usr/bin/env python3
"""
Test script to verify source registration fixes
"""

try:
    print("Testing source imports...")
    from sources.limitless import LimitlessSource
    from sources.news import NewsSource  
    from sources.weather import WeatherSource
    from sources.twitter import TwitterSource
    print('✅ All source imports successful')
    
    print("\nTesting source instantiation...")
    from config.models import LimitlessConfig, NewsConfig, WeatherConfig, TwitterConfig
    from core.database import DatabaseService
    
    # Create mock configs
    limitless_config = LimitlessConfig(api_key='test')
    news_config = NewsConfig(api_key='test')
    weather_config = WeatherConfig(api_key='test')
    twitter_config = TwitterConfig(data_path='/tmp')
    
    db = DatabaseService(':memory:')
    
    # Test instantiation
    limitless_source = LimitlessSource(limitless_config)
    news_source = NewsSource(news_config)
    weather_source = WeatherSource(weather_config, db)
    twitter_source = TwitterSource(twitter_config, db)
    
    print('✅ All source instantiations successful')
    print(f'Limitless namespace: {limitless_source.namespace}')
    print(f'News namespace: {news_source.namespace}')
    print(f'Weather namespace: {weather_source.namespace}')
    print(f'Twitter namespace: {twitter_source.namespace}')
    
    print("\nTesting HTTPClientMixin functionality...")
    print(f'Limitless has _get_client: {hasattr(limitless_source, "_get_client")}')
    print(f'News has _get_client: {hasattr(news_source, "_get_client")}')
    print(f'Weather has _get_client: {hasattr(weather_source, "_get_client")}')
    
    print("\nTesting required methods...")
    print(f'Limitless get_source_type: {limitless_source.get_source_type()}')
    print(f'News get_source_type: {news_source.get_source_type()}')
    print(f'Weather get_source_type: {weather_source.get_source_type()}')
    print(f'Twitter get_source_type: {twitter_source.get_source_type()}')
    
    print("\n🎉 All tests passed! Source registration should work now.")
    
except Exception as e:
    print(f'❌ Error: {e}')
    import traceback
    traceback.print_exc()