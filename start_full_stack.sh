#!/bin/bash

# Full Stack Lifeboard Startup Script
# Starts both backend API server and frontend React development server


'''
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
'''



set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to kill existing processes
cleanup_processes() {


    
    print_status "Cleaning up existing processes..."
    
    # Kill Python server processes
    pkill -f "python.*server.py" 2>/dev/null || true
    
    # Kill Vite dev server processes
    pkill -f "vite" 2>/dev/null || true
    
    # Kill any process using port 8000 (backend port)
    print_status "Ensuring port 8000 is available..."
    PORT_8000_PIDS=$(lsof -ti:8000 2>/dev/null || true)
    if [ ! -z "$PORT_8000_PIDS" ]; then
        print_warning "Found processes using port 8000: $PORT_8000_PIDS"
        echo "$PORT_8000_PIDS" | xargs kill -TERM 2>/dev/null || true
        sleep 2
        
        # Check if any processes are still using port 8000
        REMAINING_PIDS=$(lsof -ti:8000 2>/dev/null || true)
        if [ ! -z "$REMAINING_PIDS" ]; then
            print_warning "Forcefully killing remaining processes on port 8000: $REMAINING_PIDS"
            echo "$REMAINING_PIDS" | xargs kill -9 2>/dev/null || true
            sleep 1
        fi
    fi
    
    # Wait a moment for processes to terminate
    sleep 2
    
    # Verify port 8000 is actually free
    if lsof -i:8000 >/dev/null 2>&1; then
        print_error "Port 8000 is still in use after cleanup. Manual intervention required."
        print_error "Try: lsof -i:8000 to see what's using the port"
        return 1
    fi
    
    print_success "Cleanup completed - port 8000 is available"
}

# Function to start backend
start_backend() {
    print_status "Starting Python backend API server..."
    cd "$(dirname "$0")"

    # --- Python Virtual Environment Setup ---
    if [ -z "$VIRTUAL_ENV" ]; then
        print_status "No active virtual environment. Searching for one..."
        # Find the first file named "activate" within a "bin" directory
        VENV_ACTIVATE=$(find . -type f -path "*/bin/activate" -not -path "./node_modules/*" -not -path "./frontend/node_modules/*" -not -path "./.git/*" -print -quit)

        if [ -n "$VENV_ACTIVATE" ]; then
            VENV_DIR=$(dirname "$(dirname "$VENV_ACTIVATE")")
            print_status "Found virtual environment in '$VENV_DIR'. Activating..."
            source "$VENV_ACTIVATE"
        else
            print_warning "No existing virtual environment found. Creating 'venv'..."
            if command -v python3 &> /dev/null; then
                python3 -m venv venv
                print_status "Activating new virtual environment..."
                source venv/bin/activate
            else
                print_error "'python3' not found. Cannot create a virtual environment."
                return 1 # Abort starting the backend
            fi
        fi
    else
        print_status "Running in active virtual environment: $VIRTUAL_ENV"
    fi

    # --- Install dependencies ---
    if [ -f "requirements.txt" ]; then
        print_status "Installing Python dependencies..."
        pip install -r requirements.txt > logs/pip_install.log 2>&1
        print_success "Python dependencies installed."
    else
        print_warning "requirements.txt not found. Skipping dependency installation."
    fi
    
    # Start backend in background
    python -m uvicorn api.server:app --reload --port 8000 > logs/backend.log 2>&1 &
    BACKEND_PID=$!
    
    # Wait a moment and check if it started successfully
    sleep 3
    if kill -0 $BACKEND_PID 2>/dev/null; then
        print_success "Backend API server started (PID: $BACKEND_PID) at http://localhost:8000"
    else
        print_error "Backend server failed to start. Check logs/backend.log"
        return 1
    fi
}

# Function to start frontend
start_frontend() {
    print_status "Starting React frontend development server..."
    cd "$(dirname "$0")/frontend"
    
    # Check if node_modules exists
    if [ ! -d "node_modules" ]; then
        print_warning "Node modules not found. Installing dependencies..."
        npm install
    fi

    # Build the frontend if it hasn't been built yet
    if [ ! -d "dist" ]; then
        print_status "Frontend build not found. Building frontend..."
        npm run build > ../logs/frontend_build.log 2>&1
        print_success "Frontend built successfully."
    else
        print_status "Frontend already built. Skipping build step."
    fi
    
    # Start frontend in background
    npm run dev > ../logs/frontend.log 2>&1 &
    FRONTEND_PID=$!
    
    # Wait a moment and check if it started successfully
    sleep 3
    if kill -0 $FRONTEND_PID 2>/dev/null; then
        print_success "Frontend dev server started (PID: $FRONTEND_PID) at http://localhost:5173"
    else
        print_error "Frontend server failed to start. Check logs/frontend.log"
        return 1
    fi
}

# Function to show running servers
show_servers() {
    echo ""
    print_success "🎉 Lifeboard Full Stack is now running!"
    echo ""
    echo -e "${GREEN}Frontend (New UI):${NC} http://localhost:5173"
    echo -e "${BLUE}Backend API:${NC}      http://localhost:8000"
    echo ""
    echo "==============================="
    echo "FOR BEST RESULTS, LET THE SERVERS BAKE FOR A FEW MOMENTS"
    echo "==============================="
    echo ""
    print_status "Press Ctrl+C to stop both servers"
    echo ""
}

# Function to handle cleanup on exit
cleanup_on_exit() {
    echo ""
    print_status "Shutting down servers..."
    
    if [ ! -z "$BACKEND_PID" ] && kill -0 $BACKEND_PID 2>/dev/null; then
        kill $BACKEND_PID
        print_status "Backend server stopped"
    fi
    
    if [ ! -z "$FRONTEND_PID" ] && kill -0 $FRONTEND_PID 2>/dev/null; then
        kill $FRONTEND_PID
        print_status "Frontend server stopped"
    fi
    
    # Also kill any remaining processes
    pkill -f "python.*server.py" 2>/dev/null || true
    pkill -f "vite" 2>/dev/null || true
    
    print_success "Cleanup completed"
    exit 0
}

# Set up signal handling
trap cleanup_on_exit SIGINT SIGTERM

# Function to delete logs
delete_logs() {
    print_status "Deleting logs directory..."
    if [ -d "logs" ]; then
        rm -rf "logs"
        print_success "Logs directory deleted."
    else
        print_warning "Logs directory not found, nothing to delete."
    fi
}

# Main execution
echo ""
print_status "🚀 Starting Lifeboard Full Stack..."
echo ""

# Check for --delete-logs flag
if [ "$1" == "--delete-logs" ]; then
    delete_logs
fi

# Create logs directory if it doesn't exist
mkdir -p logs

# Clean up any existing processes
if ! cleanup_processes; then
    print_error "Failed to clean up existing processes"
    print_error "Cannot proceed with startup - port 8000 is not available"
    exit 1
fi

# Start backend
if ! start_backend; then
    print_error "Failed to start backend server"
    exit 1
fi

# Start frontend
if ! start_frontend; then
    print_error "Failed to start frontend server"
    cleanup_on_exit
fi

# Show status
show_servers

# Keep script running and monitor processes
while true; do
    sleep 5
    
    # Check if backend is still running
    if [ ! -z "$BACKEND_PID" ] && ! kill -0 $BACKEND_PID 2>/dev/null; then
        print_error "Backend server died unexpectedly"
        cleanup_on_exit
    fi
    
    # Check if frontend is still running
    if [ ! -z "$FRONTEND_PID" ] && ! kill -0 $FRONTEND_PID 2>/dev/null; then
        print_error "Frontend server died unexpectedly"
        cleanup_on_exit
    fi
done