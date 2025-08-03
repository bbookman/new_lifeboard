#!/bin/bash

# Lifeboard Reset & Startup Script
#
# This script provides a complete clean environment setup:
# 1. Stops all running Lifeboard services (frontend + backend)
# 2. Clears all data (databases, logs, cache files, vector stores)
# 3. Reinstalls dependencies (Python + Node.js)
# 4. Starts the application with both frontend and backend servers
#
# Usage: ./reset.sh
# 
# To make executable: chmod +x reset.sh
#
# The script will start:
# - Backend API server at http://localhost:8000
# - Frontend React UI at http://localhost:5173 (if frontend exists)
#
# Press Ctrl+C to stop all services

echo "========================================="
echo "      LIFEBOARD RESET & STARTUP"
echo "========================================="
echo ""

echo "🛑 Stopping all lifeboard-related services..."

# Kill processes by name pattern
pkill -f "lifeboard" 2>/dev/null
pkill -f "python.*lifeboard" 2>/dev/null
pkill -f "node.*lifeboard" 2>/dev/null
pkill -f "python.*api.server" 2>/dev/null
pkill -f "vite" 2>/dev/null

# Wait a moment for graceful shutdown
sleep 2

# Force kill if still running
pkill -9 -f "lifeboard" 2>/dev/null
pkill -9 -f "python.*lifeboard" 2>/dev/null
pkill -9 -f "node.*lifeboard" 2>/dev/null
pkill -9 -f "python.*api.server" 2>/dev/null
pkill -9 -f "vite" 2>/dev/null

echo "✅ Services stopped."

echo "🔓 Releasing ports used by the app..."

# Common ports that might be used by the lifeboard app
PORTS=(8000 8080 3000 5000 5001 5173 8001 8888 9000)

for port in "${PORTS[@]}"; do
    # Find and kill processes using these ports
    lsof -ti:$port 2>/dev/null | xargs kill -9 2>/dev/null
done

echo "✅ Ports released."

echo "🧹 Cleaning up data and temporary files..."

# Remove /logs directory if it exists
if [ -d "logs" ]; then
    echo "  • Removing logs directory..."
    rm -rf logs
fi

# Remove all .log files in the project (recursively)
echo "  • Removing all .log files..."
find . -name "*.log" -type f -delete

# Remove all .db files in the project (recursively)
echo "  • Removing all .db files..."
find . -name "*.db" -type f -delete

# Also remove any .db-wal and .db-shm files (SQLite temp files)
echo "  • Removing SQLite temporary files..."
find . -name "*.db-wal" -type f -delete
find . -name "*.db-shm" -type f -delete

# Remove vector store files
echo "  • Removing vector store files..."
find . -name "*.faiss" -type f -delete
find . -name "*.index" -type f -delete
find . -name "*.pkl" -type f -delete

# Remove vector store directories
if [ -d "vector_store" ]; then
    echo "  • Removing vector_store directory..."
    rm -rf vector_store
fi

if [ -d "embeddings" ]; then
    echo "  • Removing embeddings directory..."
    rm -rf embeddings
fi

# Remove frontend build artifacts
if [ -d "frontend/dist" ]; then
    echo "  • Removing frontend build artifacts..."
    rm -rf frontend/dist
fi

if [ -d "frontend/node_modules" ]; then
    echo "  • Removing frontend node_modules (will reinstall)..."
    rm -rf frontend/node_modules
fi

# Remove Python cache files
echo "  • Removing Python cache files..."
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -type f -delete

echo "✅ Cleanup complete."

echo ""
echo "📦 Installing dependencies..."

# Check Python version and virtual environment
echo "🐍 Setting up Python environment..."
export PYTHONPATH=$(pwd):$PYTHONPATH

# Install Python dependencies
if [ -f "requirements.txt" ]; then
    echo "  • Installing Python dependencies..."
    pip install -r requirements.txt
else
    echo "  ⚠️  No requirements.txt found"
fi

# Install frontend dependencies
if [ -d "frontend" ] && [ -f "frontend/package.json" ]; then
    echo "🌐 Setting up frontend environment..."
    echo "  • Installing Node.js dependencies..."
    cd frontend
    npm install
    cd ..
else
    echo "  ⚠️  No frontend directory or package.json found"
fi

echo "✅ Dependencies installed."
echo ""

# Verify required files exist
echo "🔍 Verifying application files..."

# Check if we're in the right directory
if [ ! -f "api/server.py" ]; then
    echo "❌ Error: api/server.py not found!"
    echo "   Make sure you're running this script from the Lifeboard project root directory."
    exit 1
fi

# Check Python
if ! command -v python &> /dev/null && ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python not found! Please install Python 3.7 or higher."
    exit 1
fi

# Check Node.js if frontend exists
if [ -d "frontend" ] && ! command -v node &> /dev/null; then
    echo "❌ Error: Node.js not found! Please install Node.js to run the frontend."
    exit 1
fi

# Check .env file
if [ ! -f ".env" ]; then
    echo "⚠️  Warning: .env file not found. You may need to configure environment variables."
    if [ -f ".env.example" ]; then
        echo "  💡 Tip: Copy .env.example to .env and configure your settings"
        echo "         cp .env.example .env"
    fi
fi

echo "✅ Application files verified."
echo ""

# Start the application
echo "🚀 Starting Lifeboard application..."

# Use the existing start_full_stack.sh if available, otherwise start manually
if [ -f "start_full_stack.sh" ]; then
    echo "  • Using start_full_stack.sh for full-stack startup..."
    chmod +x start_full_stack.sh
    echo ""
    echo "🔄 Handing off to start_full_stack.sh..."
    echo "   (Press Ctrl+C to stop both frontend and backend servers)"
    echo ""
    exec ./start_full_stack.sh
else
    echo "  • Starting backend server..."
    python -m api.server &
    BACKEND_PID=$!
    
    if [ -d "frontend" ]; then
        echo "  • Starting frontend development server..."
        cd frontend
        npm run dev &
        FRONTEND_PID=$!
        cd ..
    fi
    
    # Wait a moment for services to start
    sleep 3
    
    echo ""
    echo "🎉 Lifeboard services started successfully!"
    echo ""
    echo "========================================="
    echo "        🌐 ACCESS INSTRUCTIONS"
    echo "========================================="
    echo ""
    if [ -d "frontend" ]; then
        echo "Modern React UI (Recommended):"
        echo "  🔗 http://localhost:5173"
        echo ""
        echo "Backend API Server:"
        echo "  🔗 http://localhost:8000"
        echo ""
        echo "Legacy HTML Templates:"
        echo "  🔗 http://localhost:8000/calendar"
        echo "  🔗 http://localhost:8000/chat"
    else
        echo "Backend Server:"
        echo "  🔗 http://localhost:8000"
    fi
    echo ""
    echo "📋 To view logs: tail -f logs/lifeboard.log"
    echo "🛑 To stop services: ./reset.sh"
    echo ""
    echo "⚡ Application is ready for use!"
    echo "========================================="
fi