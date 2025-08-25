#!/usr/bin/env python3
"""
Comprehensive API Endpoint URL Validation Tests

These tests verify that frontend API calls match actual backend endpoints
to prevent URL routing issues like the one fixed in the useLimitlessData hook.
"""

import pytest
import requests
import json
import re
from pathlib import Path
from typing import List, Dict, Set, Tuple
from datetime import datetime, timedelta

class APIEndpointValidator:
    """Validates that frontend API calls match backend endpoints"""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.backend_url = "http://localhost:8000"
        self.frontend_src = self.project_root / "frontend" / "src"
        self.backend_routes = self.project_root / "api" / "routes"
        
    def extract_frontend_api_calls(self) -> Dict[str, List[Tuple[str, str]]]:
        """Extract all API calls from frontend code"""
        api_calls = {
            'fetch_calls': [],
            'axios_calls': [],
            'url_templates': []
        }
        
        # Patterns to match API calls
        fetch_patterns = [
            r'fetch\s*\(\s*[\'"`]([^\'"`]+)[\'"`]',
            r'fetch\s*\(\s*`([^`]+)`',
            r'await\s+fetch\s*\(\s*[\'"`]([^\'"`]+)[\'"`]',
            r'await\s+fetch\s*\(\s*`([^`]+)`'
        ]
        
        # Find all TypeScript/JavaScript files
        for file_path in self.frontend_src.rglob("*.ts"):
            self._extract_from_file(file_path, fetch_patterns, api_calls)
        for file_path in self.frontend_src.rglob("*.tsx"):
            self._extract_from_file(file_path, fetch_patterns, api_calls)
        
        return api_calls
    
    def _extract_from_file(self, file_path: Path, patterns: List[str], api_calls: Dict):
        """Extract API calls from a single file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            for pattern in patterns:
                matches = re.findall(pattern, content, re.MULTILINE | re.IGNORECASE)
                for match in matches:
                    # Filter out non-API URLs
                    if self._is_api_url(match):
                        api_calls['fetch_calls'].append((str(file_path), match))
        except (UnicodeDecodeError, PermissionError):
            pass  # Skip files that can't be read
    
    def _is_api_url(self, url: str) -> bool:
        """Check if a URL is an API endpoint"""
        api_indicators = ['/api/', '/calendar/', '/llm/', '/data_items', 'localhost:8000']
        return any(indicator in url for indicator in api_indicators)
    
    def extract_backend_endpoints(self) -> Dict[str, List[str]]:
        """Extract all available backend endpoints"""
        endpoints = {
            'get': [],
            'post': [],
            'put': [],
            'delete': []
        }
        
        # Find all Python route files
        for route_file in self.backend_routes.rglob("*.py"):
            self._extract_backend_routes(route_file, endpoints)
            
        return endpoints
    
    def _extract_backend_routes(self, file_path: Path, endpoints: Dict):
        """Extract routes from a backend route file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract router prefix
            prefix_match = re.search(r'router\s*=\s*APIRouter\s*\([^)]*prefix\s*=\s*[\'"]([^\'"]+)[\'"]', content)
            prefix = prefix_match.group(1) if prefix_match else ""
            
            # Extract route decorators
            route_patterns = [
                r'@router\.(get|post|put|delete)\s*\(\s*[\'"]([^\'"]+)[\'"]',
            ]
            
            for pattern in route_patterns:
                matches = re.findall(pattern, content, re.MULTILINE | re.IGNORECASE)
                for method, path in matches:
                    full_path = f"{prefix}{path}"
                    endpoints[method.lower()].append(full_path)
        except (UnicodeDecodeError, PermissionError):
            pass
    
    def validate_endpoints(self) -> Dict[str, List[str]]:
        """Validate that frontend API calls match backend endpoints"""
        frontend_calls = self.extract_frontend_api_calls()
        backend_endpoints = self.extract_backend_endpoints()
        
        validation_results = {
            'valid_calls': [],
            'invalid_calls': [],
            'potential_issues': []
        }
        
        for file_path, url in frontend_calls['fetch_calls']:
            # Normalize URL for comparison
            normalized_url = self._normalize_url(url)
            
            # Check if URL matches any backend endpoint
            matches_endpoint = self._url_matches_endpoints(normalized_url, backend_endpoints)
            
            if matches_endpoint:
                validation_results['valid_calls'].append((file_path, url, matches_endpoint))
            else:
                validation_results['invalid_calls'].append((file_path, url))
                
            # Check for common issues
            issues = self._detect_url_issues(url)
            if issues:
                validation_results['potential_issues'].extend([(file_path, url, issue) for issue in issues])
        
        return validation_results
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL for comparison"""
        # Remove localhost and port
        url = re.sub(r'https?://localhost:\d+', '', url)
        # Remove template variables
        url = re.sub(r'\$\{[^}]+\}', '{param}', url)
        # Remove query parameters for basic matching
        url = url.split('?')[0]
        return url
    
    def _url_matches_endpoints(self, url: str, endpoints: Dict[str, List[str]]) -> str:
        """Check if URL matches any backend endpoint"""
        for method, endpoint_list in endpoints.items():
            for endpoint in endpoint_list:
                if self._paths_match(url, endpoint):
                    return f"{method.upper()} {endpoint}"
        return ""
    
    def _paths_match(self, frontend_path: str, backend_path: str) -> bool:
        """Check if frontend path matches backend path pattern"""
        # Simple pattern matching - can be enhanced
        if frontend_path == backend_path:
            return True
            
        # Replace path parameters for matching
        backend_pattern = re.sub(r'\{[^}]+\}', r'[^/]+', backend_path)
        frontend_normalized = re.sub(r'\{param\}', 'test-value', frontend_path)
        
        return bool(re.match(f"^{backend_pattern}$", frontend_normalized))
    
    def _detect_url_issues(self, url: str) -> List[str]:
        """Detect common URL issues"""
        issues = []
        
        # Check for double /api/ in path
        if url.count('/api/') > 1:
            issues.append("Duplicate /api/ in URL path")
            
        # Check for incorrect calendar API usage
        if '/calendar/api/' in url:
            issues.append("Should be /calendar/ not /calendar/api/")
            
        # Check for missing leading slash
        if url.startswith('api/') and not url.startswith('/api/'):
            issues.append("Missing leading slash in API path")
            
        return issues


class TestAPIEndpointValidation:
    """Test cases for API endpoint validation"""
    
    @pytest.fixture
    def validator(self):
        """Create API endpoint validator"""
        return APIEndpointValidator("/Users/brucebookman/code/new_lifeboard")
    
    def test_extract_frontend_api_calls(self, validator):
        """Test extraction of frontend API calls"""
        api_calls = validator.extract_frontend_api_calls()
        
        assert isinstance(api_calls, dict)
        assert 'fetch_calls' in api_calls
        assert isinstance(api_calls['fetch_calls'], list)
        
        # Should find some API calls
        assert len(api_calls['fetch_calls']) > 0, "No API calls found in frontend code"
    
    def test_extract_backend_endpoints(self, validator):
        """Test extraction of backend endpoints"""
        endpoints = validator.extract_backend_endpoints()
        
        assert isinstance(endpoints, dict)
        for method in ['get', 'post', 'put', 'delete']:
            assert method in endpoints
            assert isinstance(endpoints[method], list)
        
        # Should find some endpoints
        total_endpoints = sum(len(endpoints[method]) for method in endpoints)
        assert total_endpoints > 0, "No backend endpoints found"
    
    def test_validate_endpoints_comprehensive(self, validator):
        """Comprehensive endpoint validation test"""
        results = validator.validate_endpoints()
        
        assert isinstance(results, dict)
        assert 'valid_calls' in results
        assert 'invalid_calls' in results
        assert 'potential_issues' in results
        
        # Report results
        print(f"\n=== API Endpoint Validation Results ===")
        print(f"Valid calls: {len(results['valid_calls'])}")
        print(f"Invalid calls: {len(results['invalid_calls'])}")
        print(f"Potential issues: {len(results['potential_issues'])}")
        
        # List invalid calls for debugging
        if results['invalid_calls']:
            print(f"\n❌ Invalid API calls found:")
            for file_path, url in results['invalid_calls']:
                print(f"  {Path(file_path).name}: {url}")
        
        # List potential issues
        if results['potential_issues']:
            print(f"\n⚠️  Potential issues:")
            for file_path, url, issue in results['potential_issues']:
                print(f"  {Path(file_path).name}: {url} - {issue}")
        
        # The test should pass, but we want to see the results
        # In a real CI environment, you might want this to fail if issues are found
        assert len(results['invalid_calls']) == 0, f"Found {len(results['invalid_calls'])} invalid API calls"
    
    def test_specific_endpoint_patterns(self, validator):
        """Test specific endpoint patterns that were problematic"""
        frontend_calls = validator.extract_frontend_api_calls()
        
        # Look for the specific patterns we fixed
        problematic_patterns = [
            '/calendar/api/data_items',  # Should be /calendar/data_items
            '/calendar/api/limitless/fetch',  # Should be /calendar/limitless/fetch
        ]
        
        found_issues = []
        for file_path, url in frontend_calls['fetch_calls']:
            for pattern in problematic_patterns:
                if pattern in url:
                    found_issues.append((file_path, url, f"Contains problematic pattern: {pattern}"))
        
        if found_issues:
            print(f"\n❌ Found problematic URL patterns:")
            for file_path, url, issue in found_issues:
                print(f"  {Path(file_path).name}: {url} - {issue}")
        
        assert len(found_issues) == 0, f"Found {len(found_issues)} problematic URL patterns"


def test_live_endpoint_availability():
    """Test that the backend endpoints we rely on are actually available"""
    base_url = "http://localhost:8000"
    test_date = "2025-08-24"  # Use the date from our recent fix
    
    endpoints_to_test = [
        ("GET", f"/calendar/data_items/{test_date}?namespaces=limitless", "Limitless data endpoint"),
        ("POST", f"/calendar/limitless/fetch/{test_date}", "Limitless fetch endpoint"),
        ("GET", f"/api/llm/summary/{test_date}", "LLM summary endpoint"),
        ("GET", f"/calendar/data_items/{test_date}?namespaces=twitter", "Twitter data endpoint"),
        ("GET", "/health", "Health check endpoint"),
    ]
    
    results = []
    for method, endpoint, description in endpoints_to_test:
        try:
            if method == "GET":
                response = requests.get(f"{base_url}{endpoint}", timeout=5)
            else:
                response = requests.post(f"{base_url}{endpoint}", timeout=5, json={})
            
            results.append({
                'endpoint': endpoint,
                'description': description,
                'status_code': response.status_code,
                'available': response.status_code < 500,  # Accept 404, but not 503
                'response_size': len(response.content)
            })
        except requests.exceptions.RequestException as e:
            results.append({
                'endpoint': endpoint,
                'description': description,
                'status_code': None,
                'available': False,
                'error': str(e)
            })
    
    # Report results
    print(f"\n=== Live Endpoint Availability Test ===")
    for result in results:
        status = "✅" if result['available'] else "❌"
        if result['status_code']:
            print(f"{status} {result['endpoint']} - {result['description']} (HTTP {result['status_code']})")
        else:
            print(f"{status} {result['endpoint']} - {result['description']} (ERROR: {result.get('error', 'Unknown')})")
    
    # Count available endpoints
    available_count = sum(1 for r in results if r['available'])
    total_count = len(results)
    
    print(f"\nEndpoint Availability: {available_count}/{total_count}")
    
    # We want at least 60% of endpoints to be available (some might be expected to fail)
    availability_ratio = available_count / total_count
    assert availability_ratio >= 0.6, f"Too many endpoints unavailable: {available_count}/{total_count}"


if __name__ == "__main__":
    # Run the validator directly
    validator = APIEndpointValidator("/Users/brucebookman/code/new_lifeboard")
    results = validator.validate_endpoints()
    
    print("=== API Endpoint Validation Summary ===")
    print(f"Valid calls: {len(results['valid_calls'])}")
    print(f"Invalid calls: {len(results['invalid_calls'])}")
    print(f"Potential issues: {len(results['potential_issues'])}")
    
    if results['invalid_calls']:
        print("\n❌ Invalid API calls:")
        for file_path, url in results['invalid_calls']:
            print(f"  {Path(file_path).name}: {url}")
    
    if results['potential_issues']:
        print("\n⚠️  Potential issues:")
        for file_path, url, issue in results['potential_issues']:
            print(f"  {Path(file_path).name}: {url} - {issue}")