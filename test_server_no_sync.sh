#!/bin/bash

# Test server without sync operations
echo "Starting Lifeboard API server in TEST MODE (no sync)..."

# Change to the project directory
cd "$(dirname "$0")"

# Set environment variables to disable sync
export LIFEBOARD_TEST_MODE=true
export LIFEBOARD_DISABLE_SYNC=true

# Start the server
python api/server.py --port 8000

echo "Server stopped."