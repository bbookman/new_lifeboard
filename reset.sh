#!/bin/bash

# Reset script - stops services and removes all log files and directories

echo "Stopping all lifeboard-related services..."

# Kill processes by name pattern
pkill -f "lifeboard" 2>/dev/null
pkill -f "python.*lifeboard" 2>/dev/null
pkill -f "node.*lifeboard" 2>/dev/null

# Wait a moment for graceful shutdown
sleep 2

# Force kill if still running
pkill -9 -f "lifeboard" 2>/dev/null
pkill -9 -f "python.*lifeboard" 2>/dev/null
pkill -9 -f "node.*lifeboard" 2>/dev/null

echo "Services stopped."

echo "Releasing ports used by the app..."

# Common ports that might be used by the lifeboard app
PORTS=(8000 8080 3000 5000 5001 8001 8888 9000)

for port in "${PORTS[@]}"; do
    # Find and kill processes using these ports
    lsof -ti:$port 2>/dev/null | xargs kill -9 2>/dev/null
done

echo "Ports released."

echo "Removing all log files and directories..."

# Remove /logs directory if it exists
if [ -d "logs" ]; then
    echo "Removing logs directory..."
    rm -rf logs
fi

# Remove all .log files in the project (recursively)
echo "Removing all .log files..."
find . -name "*.log" -type f -delete

# Remove all .db files in the project (recursively)
echo "Removing all .db files..."
find . -name "*.db" -type f -delete

# Also remove any .db-wal and .db-shm files (SQLite temp files)
echo "Removing SQLite temporary files..."
find . -name "*.db-wal" -type f -delete
find . -name "*.db-shm" -type f -delete

# Remove vector store files and directories
echo "Removing vector store files..."
find . -name "*.faiss" -type f -delete
find . -name "*.index" -type f -delete
find . -name "*.pkl" -type f -delete

# Remove specific vector store directories and files
if [ -d "data/vectors" ]; then
    echo "Removing data/vectors directory..."
    rm -rf data/vectors/*
fi

if [ -d "data/index" ]; then
    echo "Removing data/index directory..."
    rm -rf data/index/*
fi

if [ -d "vector_store" ]; then
    echo "Removing vector_store directory..."
    rm -rf vector_store
fi

if [ -d "embeddings" ]; then
    echo "Removing embeddings directory..."
    rm -rf embeddings
fi

# Remove data directory completely for clean state
if [ -d "data" ]; then
    echo "Removing data directory for clean state..."
    rm -rf data
fi

# Remove any cache directories
if [ -d "__pycache__" ]; then
    echo "Removing Python cache directories..."
    find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
fi

if [ -d ".pytest_cache" ]; then
    echo "Removing pytest cache..."
    rm -rf .pytest_cache
fi

# Remove any temporary or backup files
echo "Removing temporary and backup files..."
find . -name "*.tmp" -type f -delete 2>/dev/null || true
find . -name "*.temp" -type f -delete 2>/dev/null || true
find . -name "*.bak" -type f -delete 2>/dev/null || true
find . -name "*~" -type f -delete 2>/dev/null || true

# Remove any .env.local or test environment files (preserve .env)
echo "Removing local environment files..."
find . -name ".env.local" -type f -delete 2>/dev/null || true
find . -name ".env.test" -type f -delete 2>/dev/null || true
find . -name ".env.development" -type f -delete 2>/dev/null || true

echo "Cleanup complete."

echo "Starting lifeboard services..."

# Check if we have a requirements.txt and install dependencies
if [ -f "requirements.txt" ]; then
    echo "Installing Python dependencies..."
    pip install -r requirements.txt
fi

# Check if we have package.json and install dependencies
if [ -f "package.json" ]; then
    echo "Installing Node.js dependencies..."
    npm install
fi

# Start the main application
echo "Starting main application..."

# Set PYTHONPATH to current directory for module imports
export PYTHONPATH=$(pwd):$PYTHONPATH

# Try common startup patterns
if [ -f "api/server.py" ]; then
    echo "Starting Lifeboard server..."
    cd "$(dirname "$0")" && python api/server.py &
elif [ -f "main.py" ]; then
    echo "Starting Python application..."
    python main.py &
elif [ -f "app.py" ]; then
    echo "Starting Python Flask/FastAPI application..."
    python app.py &
elif [ -f "server.py" ]; then
    echo "Starting Python server..."
    python server.py &
elif [ -f "package.json" ]; then
    echo "Starting Node.js application..."
    npm start &
fi

echo "Lifeboard services started successfully!"
echo "Application should be available shortly."
echo ""
echo "========================================="
echo "           ACCESS INSTRUCTIONS"
echo "========================================="
echo ""
echo "The Lifeboard web UI is accessible at:"
echo "  • http://localhost:8000"
echo ""
echo "If you need to use a different port, stop the service"
echo "and run: python api/server.py --port [PORT_NUMBER]"
echo ""
echo "To stop all services, run this script again."
echo "========================================="