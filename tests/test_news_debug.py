#!/usr/bin/env python3

import sys
import asyncio
import httpx
sys.path.append('.')
from config.factory import get_config

async def debug_news_api():
    config = get_config()
    
    print("=== DEBUGGING NEWS API CONNECTIVITY ===")
    print(f"API Key: {config.news.api_key}")
    print(f"Endpoint: {config.news.endpoint}")
    print(f"Country: {config.news.country}")
    print(f"Language: {config.news.language}")
    print()
    
    # Test the exact same call our application makes
    print("=== TESTING APPLICATION'S EXACT REQUEST ===")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {
                'x-rapidapi-key': config.news.api_key,
                'x-rapidapi-host': config.news.endpoint
            }
            params = {
                'limit': str(config.news.items_to_retrieve),  # "20"
                'country': config.news.country,               # "US"
                'lang': config.news.language                  # "en"
            }
            
            url = f'https://{config.news.endpoint}/top-headlines'
            print(f"URL: {url}")
            print(f"Headers: {headers}")
            print(f"Params: {params}")
            print()
            
            response = await client.get(url, headers=headers, params=params)
            print(f"Response Status: {response.status_code}")
            print(f"Response Headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"Response Keys: {list(data.keys())}")
                if 'data' in data:
                    print(f"Articles Count: {len(data['data'])}")
                    if data['data']:
                        first_article = data['data'][0]
                        print(f"First Article Keys: {list(first_article.keys())}")
                        print(f"First Article Title: {first_article.get('title', 'N/A')}")
                else:
                    print("No 'data' key in response")
                    print(f"Full Response: {data}")
            else:
                print(f"Error Response: {response.text}")
                
    except Exception as e:
        print(f"Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_news_api())