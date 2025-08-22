#!/usr/bin/env python3
"""
Network Diagnostics CLI Tool

Standalone tool for running comprehensive network diagnostics
on the Lifeboard application.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from services.network_diagnostics import NetworkDiagnosticsService


async def main():
    parser = argparse.ArgumentParser(description="Lifeboard Network Diagnostics Tool")

    # Connection parameters
    parser.add_argument("--host", default="127.0.0.1", help="Host to diagnose (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to diagnose (default: 8000)")

    # Output options
    parser.add_argument("--output", "-o", help="Save report to file")
    parser.add_argument("--format", choices=["json", "summary"], default="summary",
                       help="Output format (default: summary)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    print(f"🔍 Running Network Diagnostics for {args.host}:{args.port}")
    print("=" * 60)

    # Initialize diagnostics service
    diagnostics_service = NetworkDiagnosticsService()

    try:
        # Run comprehensive diagnostics
        report = await diagnostics_service.run_comprehensive_diagnostics(args.host, args.port)

        # Display results
        if args.format == "json":
            print(json.dumps(report, indent=2, default=str))
        else:
            display_summary_report(report, args.verbose)

        # Save to file if requested
        if args.output:
            filepath = await diagnostics_service.save_diagnostic_report(report, args.output)
            print(f"\n📄 Report saved to: {filepath}")

        # Exit with appropriate code
        summary = report["summary"]
        if summary["overall_status"] in ["critical", "degraded"]:
            sys.exit(1)
        elif summary["overall_status"] == "warning":
            sys.exit(2)
        else:
            sys.exit(0)

    except KeyboardInterrupt:
        print("\n\n⏹️  Diagnostics interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Diagnostics failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def display_summary_report(report: dict, verbose: bool = False):
    """Display human-readable summary report"""
    summary = report["summary"]

    # Overall status
    status_icons = {
        "healthy": "✅",
        "warning": "⚠️",
        "degraded": "🟡",
        "critical": "❌",
    }

    status_icon = status_icons.get(summary["overall_status"], "❓")

    print(f"\n{status_icon} Overall Status: {summary['overall_status'].upper()}")
    print(f"🎯 Target: {summary['target_host']}:{summary['target_port']}")
    print(f"⏱️  Execution Time: {summary['execution_time_seconds']:.2f}s")

    # Test summary
    print("\n📊 Test Results:")
    print(f"   Total Tests: {summary['total_tests']}")
    print(f"   ✅ Passed: {summary['passed_tests']}")
    print(f"   ❌ Failed: {summary['failed_tests']}")
    print(f"   ⚠️  Warnings: {summary['warning_tests']}")
    print(f"   📊 Success Rate: {summary['success_rate']:.1f}%")

    # Show failed tests
    diagnostics = report["diagnostics"]
    failed_tests = [d for d in diagnostics if d["status"] == "fail"]
    warning_tests = [d for d in diagnostics if d["status"] == "warning"]

    if failed_tests:
        print("\n❌ Failed Tests:")
        for test in failed_tests:
            print(f"   • {test['test_name']}: {test['message']}")
            if verbose and test.get("details"):
                print(f"     Details: {test['details']}")

    if warning_tests:
        print("\n⚠️  Warning Tests:")
        for test in warning_tests:
            print(f"   • {test['test_name']}: {test['message']}")
            if verbose and test.get("details"):
                print(f"     Details: {test['details']}")

    # Show recommendations
    recommendations = report["recommendations"]
    if recommendations:
        print("\n💡 Recommendations:")
        for rec in recommendations:
            priority_icons = {"high": "🔴", "medium": "🟡", "low": "🟢", "info": "ℹ️"}
            priority_icon = priority_icons.get(rec["priority"], "📋")

            print(f"   {priority_icon} [{rec['priority'].upper()}] {rec['action']}")
            print(f"      {rec['description']}")

    # Verbose details
    if verbose:
        print("\n🔍 Detailed Test Results:")
        for test in diagnostics:
            status_icon = {"pass": "✅", "fail": "❌", "warning": "⚠️", "info": "ℹ️"}.get(test["status"], "❓")
            print(f"   {status_icon} {test['test_name']}: {test['message']}")
            print(f"      Execution time: {test['execution_time_ms']:.1f}ms")

            if test.get("details"):
                # Show key details
                details = test["details"]
                if isinstance(details, dict):
                    for key, value in list(details.items())[:3]:  # Show first 3 items
                        if isinstance(value, (str, int, float, bool)) or (isinstance(value, list) and len(value) < 5):
                            print(f"      {key}: {value}")


if __name__ == "__main__":
    asyncio.run(main())
