#!/usr/bin/env python3
"""
Test runner for Lifeboard application

Provides different test modes:
- Fast: Unit tests with mocks only
- Integration: Full pipeline tests
- API: Tests with real external APIs (requires API keys)
- All: Complete test suite
"""

import sys
import os
import subprocess
import argparse
from pathlib import Path


def run_tests(mode="fast", stop_on_first_failure=False, verbose=False):
    """Run tests based on specified mode"""
    
    # Base pytest command
    cmd = ["python", "-m", "pytest"]
    
    if stop_on_first_failure:
        cmd.append("-x")  # Stop on first failure
    
    if verbose:
        cmd.append("-v")
    
    # Test selection based on mode
    if mode == "fast":
        # Unit tests only, skip API and slow tests
        cmd.extend(["-m", "not api and not slow", "tests/test_core.py"])
        print("🚀 Running fast unit tests...")
        
    elif mode == "integration":
        # Integration tests including search pipeline
        cmd.extend(["tests/test_search.py"])
        print("🔧 Running integration tests...")
        
    elif mode == "api":
        # API integration tests (requires API keys)
        cmd.extend(["-m", "api", "tests/test_api_integration.py"])
        print("🌐 Running API integration tests...")
        
    elif mode == "web":
        # Web API tests
        cmd.extend(["tests/test_web_api.py"])
        print("🕸️ Running web API tests...")
        
    elif mode == "all":
        # All tests
        cmd.append("tests/")
        print("🎯 Running all tests...")
        
    else:
        print(f"Unknown test mode: {mode}")
        return 1
    
    # Set environment variables for testing
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).parent)
    
    # Run tests
    try:
        result = subprocess.run(cmd, env=env, cwd=Path(__file__).parent)
        return result.returncode
    except KeyboardInterrupt:
        print("\n🛑 Tests interrupted by user")
        return 1


def check_dependencies():
    """Check if required dependencies are installed"""
    required_packages = [
        ("pytest", "pytest"),
        ("pytest-asyncio", "pytest_asyncio"), 
        ("numpy", "numpy"),
        ("faiss-cpu", "faiss"),
        ("sentence-transformers", "sentence_transformers"),
        ("fastapi", "fastapi"),
        ("pydantic", "pydantic")
    ]
    
    missing = []
    for package_name, import_name in required_packages:
        try:
            __import__(import_name)
        except ImportError:
            missing.append(package_name)
    
    if missing:
        print("❌ Missing required packages:")
        for package in missing:
            print(f"  - {package}")
        print("\nInstall with: pip install -r requirements.txt")
        return False
    
    return True


def main():
    parser = argparse.ArgumentParser(description="Run Lifeboard tests")
    parser.add_argument(
        "mode", 
        nargs="?",
        default="fast",
        choices=["fast", "integration", "api", "web", "all"],
        help="Test mode to run (default: fast)"
    )
    parser.add_argument(
        "-x", "--stop-first", 
        action="store_true",
        help="Stop on first failure"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true", 
        help="Verbose output"
    )
    parser.add_argument(
        "--check-deps",
        action="store_true",
        help="Check if dependencies are installed"
    )
    
    args = parser.parse_args()
    
    if args.check_deps:
        if check_dependencies():
            print("✅ All dependencies are installed")
            return 0
        else:
            return 1
    
    # Check dependencies before running tests
    if not check_dependencies():
        return 1
    
    # Show environment info
    print("📋 Test Environment:")
    print(f"  Python: {sys.version.split()[0]}")
    print(f"  Working Directory: {Path.cwd()}")
    
    # Check for API keys if running API tests
    if args.mode == "api":
        api_keys = {
            "LIMITLESS_API_KEY": os.getenv("LIMITLESS_API_KEY"),
            "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
            "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY")
        }
        
        available_keys = [k for k, v in api_keys.items() if v]
        if not available_keys:
            print("⚠️  No API keys found. Set ENABLE_REAL_API_TESTS=1 and provide API keys:")
            for key in api_keys:
                print(f"  export {key}=your_key_here")
            print("\nOr run with --mode=fast for mock tests only")
            return 1
        else:
            print(f"  Available API keys: {', '.join(available_keys)}")
    
    print()
    
    # Run tests
    exit_code = run_tests(
        mode=args.mode,
        stop_on_first_failure=args.stop_first,
        verbose=args.verbose
    )
    
    if exit_code == 0:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed!")
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())