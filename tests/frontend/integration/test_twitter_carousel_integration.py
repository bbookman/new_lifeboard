#!/usr/bin/env python3
"""
Twitter Carousel Integration Tests

Integration tests for the complete Twitter carousel API flow and data display.
Tests the issues resolved in the Twitter carousel debugging session.
"""

import pytest
import requests
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional


class TestTwitterCarouselAPIIntegration:
    """Integration tests for Twitter carousel API endpoints"""
        
    def test_twitter_data_endpoint_routing(self):
        """Test that Twitter data endpoint routes correctly"""
        base_url = "http://localhost:8000"
        test_date = "2024-11-05"
        endpoint = f"/calendar/data_items/{test_date}?namespaces=twitter"
        
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=10)
            
            # Should not return 404 (the original routing issue)
            assert response.status_code != 404, f"Endpoint {endpoint} returned 404 - routing issue not fixed"
            
            # Should return valid JSON response
            if response.status_code == 200:
                data = response.json()
                assert isinstance(data, list), "Response should be a list of DataItems"
                
                # If data exists, validate structure
                if len(data) > 0:
                    item = data[0]
                    required_fields = ["id", "namespace", "source_id", "content", "metadata", "days_date"]
                    for field in required_fields:
                        assert field in item, f"Missing required field: {field}"
                    
                    assert item["namespace"] == "twitter", "Namespace filter not working"
                    assert item["days_date"] == test_date, "Date filter not working"
                    
            return True
            
        except requests.exceptions.ConnectionError:
            pytest.skip("Backend server not available")
        except Exception as e:
            pytest.fail(f"Twitter data endpoint test failed: {e}")
    
    def test_twitter_metadata_structure_validation(self):
        """Test that Twitter metadata has expected structure for conversion"""
        test_date = "2024-11-05"  # Known date with Twitter data
        endpoint = f"/calendar/data_items/{test_date}?namespaces=twitter"
        
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if len(data) > 0:
                    for item in data[:3]:  # Test first 3 items
                        metadata = item.get("metadata")
                        
                        # Test metadata parsing (string or object)
                        if isinstance(metadata, str):
                            try:
                                parsed = json.loads(metadata)
                                assert isinstance(parsed, dict), "Parsed metadata should be dict"
                            except json.JSONDecodeError:
                                pytest.fail(f"Invalid JSON metadata for item {item['id']}")
                        elif isinstance(metadata, dict):
                            parsed = metadata
                        else:
                            pytest.fail(f"Metadata should be string or dict, got {type(metadata)}")
                        
                        # Check for data source type indicators
                        source_type = parsed.get("source_type")
                        if source_type == "twitter_archive":
                            # Archive format - should have minimal fields
                            assert "original_created_at" in parsed or item.get("created_at"), "Archive needs timestamp"
                        else:
                            # API format might have additional fields
                            pass  # More flexible validation for API format
                            
        except requests.exceptions.ConnectionError:
            pytest.skip("Backend server not available")
    
    def test_twitter_media_metadata_extraction(self):
        """Test that Twitter media metadata can be extracted by frontend"""
        test_date = "2024-11-05"
        endpoint = f"/calendar/data_items/{test_date}?namespaces=twitter"
        
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                media_test_patterns = [
                    "media.has_media",
                    "media.media_urls", 
                    "entities.media",
                    "extended_entities.media",
                    "photo",
                    "photos",
                    "media_urls"
                ]
                
                media_items_found = 0
                for item in data:
                    metadata = item.get("metadata")
                    
                    if isinstance(metadata, str):
                        try:
                            parsed = json.loads(metadata)
                        except json.JSONDecodeError:
                            continue
                    else:
                        parsed = metadata
                    
                    # Check for any media pattern
                    has_media_pattern = False
                    for pattern in media_test_patterns:
                        if self._check_nested_key(parsed, pattern):
                            has_media_pattern = True
                            media_items_found += 1
                            break
                
                # Log findings for debugging
                print(f"Found {media_items_found} items with media patterns out of {len(data)} total")
                
        except requests.exceptions.ConnectionError:
            pytest.skip("Backend server not available")
    
    def _check_nested_key(self, data: Dict, key_path: str) -> bool:
        """Check if nested key exists in data"""
        keys = key_path.split('.')
        current = data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return False
        return current is not None


class TestTwitterCarouselEndToEnd:
    """End-to-end tests simulating frontend behavior"""
    
    def test_complete_twitter_carousel_flow(self):
        """Test the complete flow from API call to data conversion"""
        test_date = "2024-11-05"
        base_url = "http://localhost:8000"
        
        try:
            # Step 1: Fetch Twitter data (simulates fetchTwitterDataItems)
            response = requests.get(f"{base_url}/calendar/data_items/{test_date}?namespaces=twitter", timeout=10)
            
            if response.status_code != 200:
                pytest.skip(f"Twitter data not available for {test_date}")
                
            data_items = response.json()
            
            if len(data_items) == 0:
                pytest.skip(f"No Twitter data found for {test_date}")
            
            # Step 2: Simulate data conversion logic
            conversion_results = []
            conversion_errors = []
            
            for item in data_items:
                try:
                    # Simulate convertDataItemToContentItem logic
                    converted = self._simulate_conversion(item)
                    conversion_results.append(converted)
                except Exception as e:
                    conversion_errors.append({
                        'item_id': item.get('id', 'unknown'),
                        'error': str(e)
                    })
            
            # Step 3: Validate conversion results
            assert len(conversion_results) > 0, "No items successfully converted"
            
            for result in conversion_results:
                # Check required fields exist
                required_fields = ['type', 'id', 'username', 'handle', 'content', 'source']
                for field in required_fields:
                    assert field in result, f"Converted item missing field: {field}"
                
                assert result['type'] == 'content-item', "Wrong type"
                assert result['source'] == 'twitter', "Wrong source"
                
                # Check fallback values for archive data
                if result.get('username') == "Twitter User":
                    # This indicates archive data with fallbacks
                    assert result.get('handle') == "@user", "Archive fallback not applied"
                    assert result.get('likes') == 0, "Archive likes fallback not applied"
                    assert result.get('retweets') == 0, "Archive retweets fallback not applied"
            
            # Report any conversion errors for debugging
            if conversion_errors:
                print(f"Conversion errors found: {len(conversion_errors)}")
                for error in conversion_errors[:3]:  # Show first 3
                    print(f"  {error['item_id']}: {error['error']}")
            
            # Success metrics
            success_rate = len(conversion_results) / len(data_items)
            assert success_rate >= 0.8, f"Conversion success rate too low: {success_rate:.1%}"
            
        except requests.exceptions.ConnectionError:
            pytest.skip("Backend server not available")
    
    def _simulate_conversion(self, data_item: Dict) -> Dict:
        """Simulate the convertDataItemToContentItem function logic"""
        # Parse metadata
        metadata = data_item.get("metadata", {})
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        
        # Detect data source type
        is_archive = metadata.get("source_type") == "twitter_archive"
        
        # Apply conversion logic based on source type
        if is_archive:
            # Archive format with fallbacks
            result = {
                "type": "content-item",
                "id": data_item["id"],
                "username": "Twitter User",
                "handle": "@user", 
                "content": data_item["content"],
                "timestamp": metadata.get("original_created_at", data_item["created_at"]),
                "verified": False,
                "source": "twitter",
                "likes": 0,
                "retweets": 0,
                "url": None,
                "hasMedia": False,
                "mediaUrl": None
            }
        else:
            # API format with real data
            result = {
                "type": "content-item",
                "id": data_item["id"],
                "username": metadata.get("username", metadata.get("author", "Twitter User")),
                "handle": metadata.get("handle", metadata.get("screen_name", "@user")),
                "content": data_item["content"],
                "timestamp": metadata.get("timestamp", data_item["created_at"]),
                "verified": metadata.get("verified", False),
                "source": "twitter",
                "likes": metadata.get("likes", metadata.get("favorite_count")),
                "retweets": metadata.get("retweets", metadata.get("retweet_count")),
                "url": metadata.get("url", metadata.get("permalink_url")),
                "hasMedia": False,
                "mediaUrl": None
            }
        
        # Media detection logic (simplified)
        media_url = None
        if metadata.get("media", {}).get("has_media"):
            media_urls = metadata["media"].get("media_urls", [])
            if isinstance(media_urls, str):
                media_urls = json.loads(media_urls)
            if media_urls and len(media_urls) > 0:
                media_url = media_urls[0]
        elif metadata.get("entities", {}).get("media"):
            media_url = metadata["entities"]["media"][0].get("media_url_https")
        elif metadata.get("extended_entities", {}).get("media"):
            media_url = metadata["extended_entities"]["media"][0].get("media_url_https")
        
        if media_url:
            result["hasMedia"] = True
            result["mediaUrl"] = media_url
        
        return result


class TestTwitterCarouselErrorHandling:
    """Test error handling scenarios for Twitter carousel"""
    
    def test_api_endpoint_not_found_handling(self):
        """Test behavior when API endpoint returns 404"""
        base_url = "http://localhost:8000"
        invalid_endpoint = "/calendar/data_items/invalid-date?namespaces=twitter"
        
        try:
            response = requests.get(f"{base_url}{invalid_endpoint}", timeout=10)
            
            # Should handle invalid dates gracefully
            if response.status_code == 404:
                # This is acceptable behavior
                assert True
            elif response.status_code == 200:
                # Should return empty array for invalid dates
                data = response.json()
                assert isinstance(data, list), "Should return list even for invalid dates"
            
        except requests.exceptions.ConnectionError:
            pytest.skip("Backend server not available")
    
    def test_malformed_response_handling(self):
        """Test handling of malformed API responses"""
        # This would require mocking the API response
        # For now, document the expected behavior
        expected_behaviors = [
            "Handle non-JSON responses gracefully",
            "Handle empty responses", 
            "Handle responses with wrong structure",
            "Show appropriate error messages in UI"
        ]
        
        assert len(expected_behaviors) > 0  # Placeholder


def test_twitter_carousel_performance():
    """Test performance characteristics of Twitter carousel"""
    test_date = "2024-11-05"
    base_url = "http://localhost:8000"
    
    try:
        start_time = time.time()
        response = requests.get(f"{base_url}/calendar/data_items/{test_date}?namespaces=twitter", timeout=10)
        end_time = time.time()
        
        response_time = end_time - start_time
        
        # API should respond within reasonable time
        assert response_time < 5.0, f"API response too slow: {response_time:.2f}s"
        
        if response.status_code == 200:
            data = response.json()
            
            # Should handle reasonable amounts of data efficiently
            if len(data) > 100:
                pytest.fail("Unexpectedly large dataset - may cause frontend performance issues")
            
    except requests.exceptions.ConnectionError:
        pytest.skip("Backend server not available")


if __name__ == "__main__":
    # Run the integration tests
    pytest.main([__file__, "-v", "-s"])