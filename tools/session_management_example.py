#!/usr/bin/env python3
"""
Example: Manual Session Lock Management

This demonstrates how to manually use the session lock manager
for custom conflict resolution scenarios.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from services.session_lock_manager import SessionLockManager


async def check_session_status():
    """Check current session status"""
    manager = SessionLockManager()

    print("📋 Current Session Status:")
    status = await manager.get_session_status()

    print(f"   Has current session: {status['has_current_session']}")
    print(f"   Heartbeat running: {status['heartbeat_running']}")
    print(f"   Lock files exist: {status['lock_files_exist']}")

    if status["current_session"]:
        session = status["current_session"]
        print(f"   Session ID: {session['session_id']}")
        print(f"   PID: {session['pid']}")
        print(f"   Port: {session['port']}")
        print(f"   State: {session['state']}")


async def list_all_sessions():
    """List all existing sessions"""
    manager = SessionLockManager()

    print("\n📋 All Sessions:")
    sessions = await manager.list_all_sessions()

    if not sessions:
        print("   No sessions found")
        return

    for session in sessions:
        validation = session.get("validation", {})
        print(f"   Session: {session['session_id']}")
        print(f"   PID: {session['pid']}, Port: {session['port']}")
        print(f"   State: {session['state']}")
        print(f"   Valid: {validation.get('is_valid', 'unknown')}")
        print(f"   Status: {validation.get('status', 'unknown')}")
        if validation.get("reason"):
            print(f"   Reason: {validation['reason']}")
        print()


async def attempt_lock_acquisition(host: str = "localhost", port: int = 8000):
    """Attempt to acquire session lock and show conflict resolution"""
    manager = SessionLockManager()

    print(f"\n🔒 Attempting to acquire lock for {host}:{port}")
    result = await manager.acquire_session_lock(host, port)

    if result["success"]:
        print(f"✅ Successfully acquired session lock: {result['session_id']}")

        # Release the lock
        print("🔓 Releasing session lock...")
        release_result = await manager.release_session_lock()

        if release_result["success"]:
            print("✅ Session lock released successfully")
        else:
            print(f"❌ Error releasing lock: {release_result.get('error')}")
    else:
        print("❌ Failed to acquire session lock")

        if result.get("existing_session"):
            existing = result["existing_session"]
            print(f"   Existing session: {existing['session_id']}")
            print(f"   PID: {existing['pid']}, Port: {existing['port']}")
            print(f"   State: {existing['state']}")

            conflict = result.get("conflict_resolution", {})
            print(f"   Conflict type: {conflict.get('type', 'unknown')}")
            print(f"   Severity: {conflict.get('severity', 'unknown')}")

            print("\n💡 Recommendations:")
            for rec in result.get("recommendations", []):
                print(f"   • {rec['description']}")
                if "command" in rec:
                    print(f"     Command: {rec['command']}")
                print(f"     Risk: {rec.get('risk', 'unknown')}")


async def cleanup_stale_sessions():
    """Find and cleanup stale sessions"""
    manager = SessionLockManager()

    print("\n🧹 Checking for stale sessions...")
    sessions = await manager.list_all_sessions()

    stale_count = 0
    for session_data in sessions:
        validation = session_data.get("validation", {})

        if not validation.get("is_valid") and validation.get("status") in ["stale", "zombie", "process_dead"]:
            stale_count += 1
            print(f"   Found stale session: {session_data['session_id']}")
            print(f"   Status: {validation['status']}")
            print(f"   Reason: {validation.get('reason', 'unknown')}")

            # The cleanup would happen automatically during lock acquisition
            # This is just for demonstration

    if stale_count == 0:
        print("   No stale sessions found")
    else:
        print(f"   Found {stale_count} stale sessions")
        print("   These will be automatically cleaned up on next server start")


async def main():
    """Main demonstration function"""
    print("🔐 Lifeboard Session Lock Manager Demo")
    print("=" * 50)

    try:
        await check_session_status()
        await list_all_sessions()
        await cleanup_stale_sessions()
        await attempt_lock_acquisition()

    except KeyboardInterrupt:
        print("\n\n⏹️  Demo interrupted")
    except Exception as e:
        print(f"\n❌ Error during demo: {e}")


if __name__ == "__main__":
    asyncio.run(main())
