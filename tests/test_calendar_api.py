#!/usr/bin/env python3
"""
Test script to verify the calendar API endpoint is working correctly.
This will help debug whether the issue is with the API or the frontend.
"""

import sys
from datetime import datetime

import requests


def test_calendar_api():
    """Test the calendar API endpoint directly"""
    base_url = "http://localhost:8000"

    # Test 1: Basic API health
    try:
        response = requests.get(f"{base_url}/health/status", timeout=5)
        print(f"✅ Health check: Status {response.status_code}")
        if response.status_code == 200:
            print(f"   Response: {response.json()}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Health check failed: {e}")
        return False

    # Test 2: Calendar days-with-data endpoint
    try:
        current_date = datetime.now()
        year = current_date.year
        month = current_date.month

        endpoint = f"{base_url}/calendar/api/days-with-data?year={year}&month={month}"
        print(f"\n🔍 Testing calendar endpoint: {endpoint}")

        response = requests.get(endpoint, timeout=10)
        print(f"   Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"   Response type: {type(data)}")
            print(f"   Response keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")

            if isinstance(data, dict):
                all_dates = data.get("all", [])
                twitter_dates = data.get("twitter", [])
                print(f"   All dates count: {len(all_dates)}")
                print(f"   Twitter dates count: {len(twitter_dates)}")
                print(f"   Sample all dates: {all_dates[:5] if all_dates else 'None'}")
                print(f"   Sample twitter dates: {twitter_dates[:5] if twitter_dates else 'None'}")

                # Check if today's date or recent dates are in the results
                today_str = current_date.strftime("%Y-%m-%d")
                print(f"   Today ({today_str}) in results: {today_str in all_dates}")

                return len(all_dates) > 0 or len(twitter_dates) > 0
            print(f"   Unexpected response format: {data}")
            return False
        print(f"   Error response: {response.text}")
        return False

    except requests.exceptions.RequestException as e:
        print(f"❌ Calendar API test failed: {e}")
        return False

    # Test 3: Calendar days-with-data endpoint without parameters
    try:
        endpoint = f"{base_url}/calendar/api/days-with-data"
        print(f"\n🔍 Testing calendar endpoint (no params): {endpoint}")

        response = requests.get(endpoint, timeout=10)
        print(f"   Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            all_dates = data.get("all", []) if isinstance(data, dict) else []
            print(f"   All dates count (no filter): {len(all_dates)}")
            return True
        print(f"   Error response: {response.text}")
        return False

    except requests.exceptions.RequestException as e:
        print(f"❌ Calendar API test (no params) failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing Calendar API Endpoint")
    print("=" * 50)

    success = test_calendar_api()

    print("\n" + "=" * 50)
    if success:
        print("✅ Calendar API tests completed - Found data!")
    else:
        print("❌ Calendar API tests failed - No data found or API issues")

    sys.exit(0 if success else 1)
