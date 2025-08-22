#!/usr/bin/env python3
"""
Simple WebSocket test script to verify connectivity
"""
import asyncio
import json
import sys

import websockets


async def test_websocket():
    uri = "ws://localhost:8000/ws/processing"

    try:
        print(f"Attempting to connect to {uri}...")

        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket connected successfully!")

            # Send a test message
            test_message = {
                "type": "subscribe",
                "topics": ["processing_updates"],
            }

            await websocket.send(json.dumps(test_message))
            print("📤 Sent test message")

            # Wait for response (with timeout)
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                print(f"📥 Received response: {response}")
            except asyncio.TimeoutError:
                print("⏰ No response received (timeout)")

            print("🔌 Closing connection")

    except (ConnectionRefusedError, OSError) as e:
        print(f"❌ Connection refused - server may not be running: {e}")
        return False
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

    return True

if __name__ == "__main__":
    success = asyncio.run(test_websocket())
    sys.exit(0 if success else 1)
