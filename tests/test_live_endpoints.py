#!/usr/bin/env python3
"""
Test script to verify live server endpoints work correctly after dependency injection fix.
"""
import asyncio
import aiohttp
import json
import sys
from datetime import datetime

async def test_endpoint(session, endpoint, description):
    """Test a single endpoint and return result."""
    try:
        print(f"Testing {description}: {endpoint}")
        async with session.get(endpoint, timeout=10) as response:
            status = response.status
            if status == 404:
                print(f"  ❌ FAILED: {description} returned 404")
                return False
            elif status >= 500:
                text = await response.text()
                print(f"  ⚠️  Server Error ({status}): {text[:200]}...")
                return False  # Server errors indicate dependency issues
            elif status >= 400:
                text = await response.text()
                print(f"  ⚠️  Client Error ({status}): {text[:200]}...")
                return True  # Client errors are expected for some endpoints (missing params)
            else:
                print(f"  ✅ SUCCESS: {description} returned {status}")
                return True
    except asyncio.TimeoutError:
        print(f"  ❌ TIMEOUT: {description} timed out")
        return False
    except Exception as e:
        print(f"  ❌ ERROR: {description} failed with {e}")
        return False

async def main():
    """Test all the endpoints that were previously returning 404."""
    base_url = "http://localhost:8000"
    
    # Test endpoints that were previously failing
    test_cases = [
        # Original failing endpoints mentioned by user
        (f"{base_url}/api/news?date=2025-08-22", "News API with date"),
        (f"{base_url}/api/llm/summary/2025-08-22", "LLM Summary API"),
        
        # Additional endpoint tests
        (f"{base_url}/api/news/latest?limit=5", "Latest News API"),
        (f"{base_url}/api/data_items?namespace=news&date=2025-08-22", "Data Items API"),
        (f"{base_url}/api/data_items/namespaces", "Data Items Namespaces API"),
        
        # Health check
        (f"{base_url}/api/health", "Health Check API"),
        
        # Root endpoint
        (f"{base_url}/", "Root endpoint"),
    ]
    
    print("🚀 Testing live server endpoints...")
    print("=" * 60)
    
    # Test if server is running
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{base_url}/", timeout=5) as response:
                if response.status != 200:
                    print("❌ Server is not responding correctly. Make sure it's running on port 8000.")
                    return False
                print("✅ Server is running and responding")
    except Exception as e:
        print(f"❌ Cannot connect to server: {e}")
        print("💡 Make sure the server is running with: python3 api/server.py")
        return False
    
    print("=" * 60)
    
    # Run tests
    results = []
    async with aiohttp.ClientSession() as session:
        for endpoint, description in test_cases:
            result = await test_endpoint(session, endpoint, description)
            results.append((description, result))
            print()  # Empty line for readability
    
    print("=" * 60)
    print("📊 RESULTS SUMMARY:")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for description, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {description}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print("=" * 60)
    print(f"Total: {len(results)} tests")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    if failed == 0:
        print("🎉 All endpoints are working correctly! Dependency injection fix was successful.")
        return True
    else:
        print(f"💥 {failed} endpoints still have issues. Further investigation needed.")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)