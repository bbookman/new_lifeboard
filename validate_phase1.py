#!/usr/bin/env python3
"""
Phase 1 validation script for async implementation.
This validates that the API routes are using async database methods.
"""

import ast
import re
from pathlib import Path

def check_calendar_routes_async():
    """Check that calendar routes use async database methods"""
    calendar_file = Path("api/routes/calendar.py")
    
    if not calendar_file.exists():
        print("❌ Calendar routes file not found")
        return False
    
    content = calendar_file.read_text()
    
    # Check for sync database calls (should be none)
    sync_calls = re.findall(r'database\.get_[a-zA-Z_]+\(', content)
    
    # Filter out markdown calls (acceptable for now)
    sync_calls = [call for call in sync_calls if 'get_markdown_by_date' not in call]
    
    if sync_calls:
        print(f"❌ Found sync database calls in calendar routes: {sync_calls}")
        return False
    
    # Check for async database calls (should be present)
    async_calls = re.findall(r'await database\.async_[a-zA-Z_]+\(', content)
    
    if len(async_calls) < 10:  # Should have many async calls
        print(f"❌ Not enough async database calls found: {len(async_calls)}")
        return False
    
    print(f"✅ Calendar routes using async database methods: {len(async_calls)} async calls found")
    return True

def check_dependency_injection():
    """Check that dependency injection is properly set up"""
    dependencies_file = Path("core/dependencies.py")
    
    if not dependencies_file.exists():
        print("❌ Dependencies file not found")
        return False
    
    content = dependencies_file.read_text()
    
    if 'get_database_service_dependency' not in content:
        print("❌ Async database service dependency function not found")
        return False
    
    calendar_file = Path("api/routes/calendar.py")
    calendar_content = calendar_file.read_text()
    
    if 'get_database_service_dependency' not in calendar_content:
        print("❌ Calendar routes not using async database dependency")
        return False
    
    print("✅ Dependency injection properly configured for async database service")
    return True

def check_import_validity():
    """Check that the modules can be imported without errors"""
    try:
        from api.routes.calendar import router
        print("✅ Calendar routes import successfully")
    except Exception as e:
        print(f"❌ Calendar routes import failed: {e}")
        return False
    
    try:
        from core.dependencies import get_database_service_dependency
        print("✅ Database service dependency imports successfully")
    except Exception as e:
        print(f"❌ Database service dependency import failed: {e}")
        return False
    
    return True

def main():
    print("🔍 Phase 1 Validation: API Layer Integration")
    print("=" * 50)
    
    results = []
    
    results.append(check_calendar_routes_async())
    results.append(check_dependency_injection()) 
    results.append(check_import_validity())
    
    print("\n" + "=" * 50)
    if all(results):
        print("🎉 Phase 1 validation PASSED!")
        print("   • Calendar routes converted to async database methods")
        print("   • Dependency injection configured for async operations")
        print("   • All modules import successfully")
        return True
    else:
        print("❌ Phase 1 validation FAILED!")
        print("   Some checks did not pass. See details above.")
        return False

if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)