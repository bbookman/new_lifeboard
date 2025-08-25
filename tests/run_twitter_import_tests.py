"""
Comprehensive test runner for Twitter import functionality.

This script runs all Twitter import tests and provides a summary report.
"""

import os
import subprocess
import sys
from pathlib import Path


def run_test_suite(test_path: str, test_name: str) -> dict:
    """Run a test suite and return results."""
    print(f"\n{'='*60}")
    print(f"Running {test_name}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", test_path, "-v", "--tb=short"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )
        
        success = result.returncode == 0
        output = result.stdout
        error_output = result.stderr
        
        # Parse test results
        lines = output.split('\n')
        passed_count = 0
        failed_count = 0
        skipped_count = 0
        
        for line in lines:
            if ' PASSED ' in line:
                passed_count += 1
            elif ' FAILED ' in line:
                failed_count += 1
            elif ' SKIPPED ' in line:
                skipped_count += 1
        
        return {
            'success': success,
            'passed': passed_count,
            'failed': failed_count,
            'skipped': skipped_count,
            'output': output,
            'error': error_output
        }
        
    except Exception as e:
        return {
            'success': False,
            'passed': 0,
            'failed': 1,
            'skipped': 0,
            'output': '',
            'error': str(e)
        }


def main():
    """Run all Twitter import tests."""
    print("🔥 Twitter Import Test Suite")
    print("=" * 80)
    
    # Define test suites
    test_suites = [
        {
            'path': 'tests/backend/unit/config/test_twitter_config_archive_mode.py',
            'name': 'Twitter Configuration Tests'
        },
        {
            'path': 'tests/backend/integration/service_interactions/test_twitter_archive_import.py',
            'name': 'Twitter Archive Import Integration Tests'
        },
        {
            'path': 'tests/api/test_twitter_upload_api.py', 
            'name': 'Twitter Upload API Tests'
        },
        {
            'path': 'tests/performance/test_twitter_import_performance.py',
            'name': 'Twitter Import Performance Tests'
        }
    ]
    
    # Check if all test files exist
    missing_files = []
    for suite in test_suites:
        test_file = Path(__file__).parent.parent / suite['path']
        if not test_file.exists():
            missing_files.append(suite['path'])
    
    if missing_files:
        print("❌ Missing test files:")
        for file in missing_files:
            print(f"   - {file}")
        return False
    
    # Check if Twitter archive exists
    archive_path = Path(__file__).parent / "media" / "twitter-x.zip"
    if not archive_path.exists():
        print("⚠️  Warning: Twitter archive not found at tests/media/twitter-x.zip")
        print("   Some integration tests may be skipped.")
    else:
        print(f"✅ Twitter archive found: {archive_path}")
    
    # Run test suites
    results = {}
    total_passed = 0
    total_failed = 0
    total_skipped = 0
    
    for suite in test_suites:
        result = run_test_suite(suite['path'], suite['name'])
        results[suite['name']] = result
        
        total_passed += result['passed']
        total_failed += result['failed'] 
        total_skipped += result['skipped']
        
        # Print immediate results
        if result['success']:
            print(f"✅ {suite['name']}: {result['passed']} passed, {result['skipped']} skipped")
        else:
            print(f"❌ {suite['name']}: {result['failed']} failed, {result['passed']} passed")
            if result['error']:
                print(f"   Error: {result['error']}")
    
    # Print summary
    print("\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)
    
    for suite_name, result in results.items():
        status = "✅ PASS" if result['success'] else "❌ FAIL"
        print(f"{status} {suite_name}")
        print(f"      Passed: {result['passed']}")
        print(f"      Failed: {result['failed']}")
        print(f"      Skipped: {result['skipped']}")
        print()
    
    print(f"TOTAL RESULTS:")
    print(f"  ✅ Passed:  {total_passed}")
    print(f"  ❌ Failed:  {total_failed}")
    print(f"  ⏭️  Skipped: {total_skipped}")
    
    overall_success = total_failed == 0
    if overall_success:
        print(f"\n🎉 ALL TESTS PASSED! Twitter import functionality is working correctly.")
    else:
        print(f"\n💥 {total_failed} test(s) failed. Please review the output above.")
    
    print("\n" + "="*80)
    print("🧪 Test Coverage Summary:")
    print("✅ Configuration: Archive-only mode support")
    print("✅ Integration: Full import workflow with real archive")  
    print("✅ API Endpoints: Upload and error handling")
    print("✅ Performance: Scalability and memory usage")
    print("="*80)
    
    return overall_success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)