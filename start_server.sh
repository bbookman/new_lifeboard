#!/bin/bash

# Lifeboard Server Startup Script
# This script starts the Lifeboard API server

echo "Starting Lifeboard API server..."

# Change to the project directory
cd "$(dirname "$0")"

# Start the server
python api/server.py --port 8000

echo "Server stopped."