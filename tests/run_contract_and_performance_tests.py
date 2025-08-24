#!/usr/bin/env python3
"""
Test runner for contract testing and performance regression tests.

This script provides a convenient way to run the new contract and performance
testing infrastructure with appropriate configuration.
"""

import sys
import os
import subprocess
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def run_contract_tests(verbose=False, specific_test=None):
    """Run contract tests to validate service interface compliance."""
    print("🔍 Running Contract Tests...")
    print("=" * 60)
    
    cmd = [
        sys.executable, "-m", "pytest",
        "-v" if verbose else "-q",
        "-m", "contract",
        "--tb=short",
        "tests/contracts/"
    ]
    
    if specific_test:
        cmd.extend(["-k", specific_test])
    
    result = subprocess.run(cmd, cwd=project_root)
    return result.returncode == 0


def run_performance_tests(verbose=False, specific_test=None, benchmark_only=False):
    """Run performance tests and benchmarks."""
    print("⚡ Running Performance Tests...")
    print("=" * 60)
    
    cmd = [
        sys.executable, "-m", "pytest",
        "-v" if verbose else "-q",
        "-m", "benchmark" if benchmark_only else "performance",
        "--tb=short",
        "tests/performance/"
    ]
    
    if specific_test:
        cmd.extend(["-k", specific_test])
    
    # Add performance-specific options
    cmd.extend([
        "--durations=10",  # Show 10 slowest tests
        "--disable-warnings"  # Reduce noise
    ])
    
    result = subprocess.run(cmd, cwd=project_root)
    return result.returncode == 0


def run_example_tests(verbose=False):
    """Run example tests to demonstrate testing patterns."""
    print("📚 Running Example Tests...")
    print("=" * 60)
    
    cmd = [
        sys.executable, "-m", "pytest",
        "-v" if verbose else "-q",
        "--tb=short",
        "tests/examples/"
    ]
    
    result = subprocess.run(cmd, cwd=project_root)
    return result.returncode == 0


def check_dependencies():
    """Check if required dependencies are available."""
    print("🔧 Checking Dependencies...")
    
    required_packages = [
        "pytest",
        "psutil",
        "sqlite3"
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            if package == "sqlite3":
                import sqlite3
            else:
                __import__(package)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package}")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\nMissing packages: {', '.join(missing_packages)}")
        print("Install with: pip install " + " ".join(missing_packages))
        return False
    
    print("✅ All dependencies available")
    return True


def run_quick_validation():
    """Run a quick validation of the testing infrastructure."""
    print("🚀 Running Quick Validation...")
    print("=" * 60)
    
    # Test basic imports
    try:
        from tests.contracts.test_service_contracts import TestServiceContracts
        from tests.performance.test_performance_benchmarks import PerformanceBenchmarks
        print("✅ Test modules can be imported")
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    
    # Run a minimal test
    cmd = [
        sys.executable, "-m", "pytest",
        "-v",
        "tests/examples/test_contract_examples.py::TestContractValidationHelpers::test_validation_helpers",
        "--tb=short"
    ]
    
    result = subprocess.run(cmd, cwd=project_root, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ Basic test execution works")
        return True
    else:
        print(f"❌ Test execution failed: {result.stderr}")
        return False


def generate_test_report():
    """Generate a comprehensive test report."""
    print("📊 Generating Test Report...")
    print("=" * 60)
    
    cmd = [
        sys.executable, "-m", "pytest",
        "--collect-only",
        "-q",
        "tests/contracts/",
        "tests/performance/",
        "tests/examples/"
    ]
    
    result = subprocess.run(cmd, cwd=project_root, capture_output=True, text=True)
    
    if result.returncode == 0:
        lines = result.stdout.split('\n')
        contract_tests = sum(1 for line in lines if 'contracts' in line and '::' in line)
        performance_tests = sum(1 for line in lines if 'performance' in line and '::' in line)
        example_tests = sum(1 for line in lines if 'examples' in line and '::' in line)
        
        print(f"Contract Tests: {contract_tests}")
        print(f"Performance Tests: {performance_tests}")
        print(f"Example Tests: {example_tests}")
        print(f"Total New Tests: {contract_tests + performance_tests + example_tests}")
        
    else:
        print("Could not generate test count")


def main():
    """Main entry point for test runner."""
    parser = argparse.ArgumentParser(
        description="Run contract testing and performance regression tests"
    )
    parser.add_argument(
        "--type",
        choices=["all", "contract", "performance", "examples", "validation"],
        default="all",
        help="Type of tests to run"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--test", "-t",
        help="Run specific test (use pytest -k syntax)"
    )
    parser.add_argument(
        "--benchmark-only",
        action="store_true", 
        help="Run only benchmark tests (subset of performance tests)"
    )
    parser.add_argument(
        "--check-deps",
        action="store_true",
        help="Check dependencies and exit"
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate test report and exit"
    )
    
    args = parser.parse_args()
    
    # Check dependencies if requested
    if args.check_deps:
        success = check_dependencies()
        sys.exit(0 if success else 1)
    
    # Generate report if requested
    if args.report:
        generate_test_report()
        sys.exit(0)
    
    # Check dependencies before running tests
    if not check_dependencies():
        print("\nPlease install missing dependencies before running tests.")
        sys.exit(1)
    
    success = True
    
    # Run validation first if running all tests
    if args.type in ["all", "validation"]:
        if not run_quick_validation():
            print("\n❌ Quick validation failed. Check your setup.")
            success = False
    
    # Run contract tests
    if args.type in ["all", "contract"] and success:
        if not run_contract_tests(args.verbose, args.test):
            success = False
    
    # Run performance tests
    if args.type in ["all", "performance"] and success:
        if not run_performance_tests(args.verbose, args.test, args.benchmark_only):
            success = False
    
    # Run example tests
    if args.type in ["all", "examples"] and success:
        if not run_example_tests(args.verbose):
            success = False
    
    # Summary
    if args.type == "all":
        print("\n" + "=" * 60)
        if success:
            print("✅ All tests completed successfully!")
            print("\nNew testing infrastructure is ready to use:")
            print("- Contract tests validate service interface compliance")
            print("- Performance tests detect regressions and bottlenecks")
            print("- Example tests demonstrate best practices")
        else:
            print("❌ Some tests failed. Check output above.")
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()