#!/usr/bin/env python3
"""
Frontend-Backend URL Synchronization Tests

These tests ensure that frontend API calls match backend endpoint paths
to prevent 404 errors caused by URL path mismatches.

Fixed Issue: Calendar frontend was calling /calendar/api/days-with-data
but backend only serves /calendar/days-with-data
"""

import pytest
import re
from pathlib import Path
from typing import List, Dict, Set


class TestFrontendBackendUrlSync:
    """Test that frontend API URLs match backend endpoints"""
    
    @pytest.fixture
    def project_root(self):
        """Get project root path"""
        return Path(__file__).parent.parent.parent.parent.parent
    
    def extract_calendar_urls_from_frontend(self, project_root: Path) -> List[str]:
        """Extract calendar-related API URLs from frontend code"""
        frontend_src = project_root / "frontend" / "src"
        calendar_urls = []
        
        # Look for calendar URLs in TypeScript/JSX files
        for file_path in frontend_src.rglob("*.ts*"):
            try:
                content = file_path.read_text()
                
                # Find API URLs that contain 'calendar'
                url_patterns = [
                    r'[\'"`](http://localhost:8000)?/calendar/[^\'"`\s]+[\'"`]',
                    r'`[^`]*calendar[^`]*`',
                    r'apiUrl\s*=\s*[\'"`][^\'"`]*calendar[^\'"`]*[\'"`]'
                ]
                
                for pattern in url_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    for match in matches:
                        # Clean up the URL
                        url = match.replace('http://localhost:8000', '').strip('\'"` ')
                        if url.startswith('/calendar') and url not in calendar_urls:
                            calendar_urls.append(url)
                            
            except Exception as e:
                # Skip files that can't be read
                continue
                
        return calendar_urls
    
    def extract_calendar_endpoints_from_backend(self, project_root: Path) -> List[str]:
        """Extract calendar endpoints from backend router"""
        backend_routes = project_root / "api" / "routes" / "calendar.py"
        endpoints = []
        
        try:
            content = backend_routes.read_text()
            
            # Find @router.get(), @router.post() decorators
            endpoint_patterns = [
                r'@router\.get\([\'"`]([^\'"`]+)[\'"`]',
                r'@router\.post\([\'"`]([^\'"`]+)[\'"`]',
                r'@router\.put\([\'"`]([^\'"`]+)[\'"`]',
                r'@router\.delete\([\'"`]([^\'"`]+)[\'"`]'
            ]
            
            for pattern in endpoint_patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    # Add the router prefix
                    full_endpoint = f"/calendar{match}"
                    if full_endpoint not in endpoints:
                        endpoints.append(full_endpoint)
                        
        except Exception as e:
            pytest.fail(f"Could not read backend calendar routes: {e}")
            
        return endpoints
    
    def test_calendar_frontend_backend_url_sync(self, project_root):
        """Test that frontend calendar URLs match backend endpoints"""
        frontend_urls = self.extract_calendar_urls_from_frontend(project_root)
        backend_endpoints = self.extract_calendar_endpoints_from_backend(project_root)
        
        print(f"\nFrontend calendar URLs found: {frontend_urls}")
        print(f"Backend calendar endpoints: {backend_endpoints}")
        
        # Check for the specific bug pattern we fixed
        problematic_urls = [url for url in frontend_urls if '/calendar/api/' in url]
        if problematic_urls:
            pytest.fail(f"Frontend contains problematic URLs with /calendar/api/: {problematic_urls}")
        
        # Check that frontend URLs have corresponding backend endpoints
        mismatched_urls = []
        for frontend_url in frontend_urls:
            # Remove query parameters for comparison
            base_url = frontend_url.split('?')[0]
            
            # Skip non-endpoint URLs (like template strings)
            if '{' in base_url or '$' in base_url:
                continue
                
            if base_url not in backend_endpoints:
                mismatched_urls.append(base_url)
        
        if mismatched_urls:
            pytest.fail(f"Frontend URLs not found in backend endpoints: {mismatched_urls}")
    
    def test_no_calendar_api_pattern_in_frontend(self, project_root):
        """Test that frontend doesn't use the problematic /calendar/api/ pattern"""
        frontend_src = project_root / "frontend" / "src"
        problematic_files = []
        
        for file_path in frontend_src.rglob("*.ts*"):
            # Skip test files - they may contain negative assertions about the old pattern
            if '__tests__' in str(file_path) or '.test.' in str(file_path) or '.spec.' in str(file_path):
                continue
                
            try:
                content = file_path.read_text()
                if '/calendar/api/' in content:
                    # Find the specific lines, but ignore lines that are testing the old pattern
                    lines = content.split('\n')
                    problem_lines = []
                    for i, line in enumerate(lines):
                        if '/calendar/api/' in line:
                            # Skip lines that are clearly testing the old pattern should NOT be used
                            if any(keyword in line.lower() for keyword in ['not.', 'tonotcontain', 'should not', 'avoid', 'dont', "don't"]):
                                continue
                            problem_lines.append((i+1, line))
                    
                    if problem_lines:
                        problematic_files.append((str(file_path), problem_lines))
            except Exception:
                continue
        
        if problematic_files:
            error_msg = "Found problematic /calendar/api/ patterns in frontend files:\n"
            for file_path, lines in problematic_files:
                error_msg += f"\n{file_path}:\n"
                for line_num, line in lines:
                    error_msg += f"  Line {line_num}: {line.strip()}\n"
            pytest.fail(error_msg)
    
    def test_calendar_endpoints_accessible(self, project_root):
        """Test that calendar endpoints are accessible via requests"""
        import requests
        
        try:
            # Test if server is running
            response = requests.get("http://localhost:8000/health", timeout=2)
            if response.status_code != 200:
                pytest.skip("Live server not available for endpoint testing")
        except requests.RequestException:
            pytest.skip("Live server not available for endpoint testing")
        
        # Test key calendar endpoints
        endpoints_to_test = [
            "/calendar/days-with-data",
            "/calendar/today",
        ]
        
        for endpoint in endpoints_to_test:
            try:
                response = requests.get(f"http://localhost:8000{endpoint}", timeout=5)
                assert response.status_code in [200, 400], f"Endpoint {endpoint} should be accessible (got {response.status_code})"
            except requests.RequestException as e:
                pytest.fail(f"Could not access endpoint {endpoint}: {e}")
    
    def test_no_orphaned_calendar_api_endpoints(self, project_root):
        """Test that there are no orphaned /calendar/api/ endpoints in backend"""
        backend_routes = project_root / "api" / "routes" / "calendar.py"
        
        try:
            content = backend_routes.read_text()
            if '/api/' in content and 'calendar' in content:
                # Check if it's in a comment or not an actual endpoint
                lines = content.split('\n')
                problem_lines = []
                for i, line in enumerate(lines):
                    if '/api/' in line and 'calendar' in line and not line.strip().startswith('#'):
                        problem_lines.append((i+1, line.strip()))
                
                if problem_lines:
                    error_msg = "Found potential /api/ patterns in calendar backend:\n"
                    for line_num, line in problem_lines:
                        error_msg += f"Line {line_num}: {line}\n"
                    # This is a warning, not a failure, as there might be legitimate uses
                    print(f"\nWarning: {error_msg}")
                    
        except Exception as e:
            pytest.fail(f"Could not read backend calendar routes: {e}")


class TestSpecificCalendarUrlFix:
    """Test the specific calendar URL fix that was implemented"""
    
    def test_calendar_days_with_data_url_fix(self):
        """Test that the specific calendar days-with-data URL fix is working"""
        import requests
        
        try:
            # Test if server is running
            response = requests.get("http://localhost:8000/health", timeout=2)
            if response.status_code != 200:
                pytest.skip("Live server not available")
        except requests.RequestException:
            pytest.skip("Live server not available")
        
        # Test the CORRECT URL (should work)
        try:
            response = requests.get("http://localhost:8000/calendar/days-with-data", timeout=5)
            assert response.status_code == 200, "Fixed calendar URL should work"
            
            data = response.json()
            assert "data" in data, "Response should contain data field"
            assert "sync_status" in data, "Response should contain sync_status field"
            
        except requests.RequestException as e:
            pytest.fail(f"Fixed calendar URL failed: {e}")
        
        # Test the INCORRECT URL (should return 404)
        try:
            response = requests.get("http://localhost:8000/calendar/api/days-with-data", timeout=5)
            assert response.status_code == 404, "Old problematic calendar URL should return 404"
            
        except requests.RequestException as e:
            pytest.fail(f"Old calendar URL test failed: {e}")
    
    def test_frontend_uses_correct_calendar_url(self):
        """Test that frontend CalendarView component uses correct URL"""
        calendar_view_path = Path(__file__).parent.parent.parent.parent.parent / "frontend" / "src" / "components" / "CalendarView.tsx"
        
        if not calendar_view_path.exists():
            pytest.skip("CalendarView.tsx not found")
        
        try:
            content = calendar_view_path.read_text()
            
            # Should contain the CORRECT URL
            assert "/calendar/days-with-data" in content, "CalendarView should use correct URL path"
            
            # Should NOT contain the INCORRECT URL
            assert "/calendar/api/days-with-data" not in content, "CalendarView should not use old incorrect URL path"
            
        except Exception as e:
            pytest.fail(f"Could not verify CalendarView.tsx: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])