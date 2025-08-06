#!/bin/bash

# Full Stack Lifeboard Startup Script
# Starts both backend API server and frontend React development server

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

# Function to check if port is in use
check_port() {
    local port=$1
    if lsof -i :$port >/dev/null 2>&1; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

# Function to kill processes using specific ports
kill_port_processes() {
    local port=$1
    local process_name=$2
    
    if check_port $port; then
        print_warning "$process_name port $port is in use. Attempting to free it..."
        
        # Get PID of process using the port
        local pid=$(lsof -ti :$port)
        if [ ! -z "$pid" ]; then
            print_status "Killing process $pid using port $port"
            kill -TERM $pid 2>/dev/null || true
            sleep 2
            
            # If still running, force kill
            if kill -0 $pid 2>/dev/null; then
                print_warning "Process $pid didn't respond to TERM signal, using KILL"
                kill -KILL $pid 2>/dev/null || true
                sleep 1
            fi
        fi
        
        # Double-check the port is now free
        if check_port $port; then
            print_error "Unable to free port $port. You may need to manually kill the process."
            return 1
        else
            print_success "Port $port is now available"
        fi
    fi
    return 0
}

# Function to kill existing processes
cleanup_processes() {
    print_status "Cleaning up existing processes..."
    
    # Kill processes on specific ports
    kill_port_processes 8000 "Backend API"
    kill_port_processes 5173 "Frontend Dev Server"
    
    # Kill Python server processes by pattern
    pkill -f "python.*server.py" 2>/dev/null || true
    pkill -f "uvicorn.*api.server" 2>/dev/null || true
    
    # Kill Vite dev server processes
    pkill -f "vite" 2>/dev/null || true
    pkill -f "npm.*run.*dev" 2>/dev/null || true
    
    # Wait a moment for processes to terminate
    sleep 2
    
    print_success "Cleanup completed"
}

# Function to start backend
start_backend() {
    print_status "Starting Python backend API server..."
    cd "$(dirname "$0")"
    
    # Double-check port 8000 is available
    if check_port 8000; then
        print_error "Port 8000 is still in use after cleanup. Aborting backend startup."
        return 1
    fi
    
    # Start backend in background
    python -m uvicorn api.server:app --reload --port 8000 > logs/backend.log 2>&1 &
    BACKEND_PID=$!
    
    # Wait a moment and check if it started successfully
    sleep 3
    if kill -0 $BACKEND_PID 2>/dev/null; then
        # Verify it's actually listening on the port
        if check_port 8000; then
            print_success "Backend API server started (PID: $BACKEND_PID) at http://localhost:8000"
        else
            print_error "Backend process is running but not listening on port 8000. Check logs/backend.log"
            kill $BACKEND_PID 2>/dev/null || true
            return 1
        fi
    else
        print_error "Backend server failed to start. Check logs/backend.log"
        return 1
    fi
}

# Function to start frontend
start_frontend() {
    print_status "Starting React frontend development server..."
    cd "$(dirname "$0")/frontend"
    
    # Double-check port 5173 is available
    if check_port 5173; then
        print_error "Port 5173 is still in use after cleanup. Aborting frontend startup."
        return 1
    fi
    
    # Check if node_modules exists
    if [ ! -d "node_modules" ]; then
        print_warning "Node modules not found. Installing dependencies..."
        npm install
    fi
    
    # Start frontend in background
    npm run dev > ../logs/frontend.log 2>&1 &
    FRONTEND_PID=$!
    
    # Wait a moment and check if it started successfully
    sleep 5  # Give Vite a bit more time to start
    if kill -0 $FRONTEND_PID 2>/dev/null; then
        # Verify it's actually listening on the port
        if check_port 5173; then
            print_success "Frontend dev server started (PID: $FRONTEND_PID) at http://localhost:5173"
        else
            print_error "Frontend process is running but not listening on port 5173. Check logs/frontend.log"
            kill $FRONTEND_PID 2>/dev/null || true
            return 1
        fi
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
    print_status "Press Ctrl+C to stop both servers"
    echo ""
}

# Function to handle cleanup on exit
cleanup_on_exit() {
    echo ""
    print_status "Shutting down servers..."
    
    # Try to gracefully stop tracked PIDs first
    if [ ! -z "$BACKEND_PID" ] && kill -0 $BACKEND_PID 2>/dev/null; then
        print_status "Stopping backend server (PID: $BACKEND_PID)..."
        kill -TERM $BACKEND_PID 2>/dev/null || true
        sleep 2
        if kill -0 $BACKEND_PID 2>/dev/null; then
            kill -KILL $BACKEND_PID 2>/dev/null || true
        fi
        print_status "Backend server stopped"
    fi
    
    if [ ! -z "$FRONTEND_PID" ] && kill -0 $FRONTEND_PID 2>/dev/null; then
        print_status "Stopping frontend server (PID: $FRONTEND_PID)..."
        kill -TERM $FRONTEND_PID 2>/dev/null || true
        sleep 2
        if kill -0 $FRONTEND_PID 2>/dev/null; then
            kill -KILL $FRONTEND_PID 2>/dev/null || true
        fi
        print_status "Frontend server stopped"
    fi
    
    # Use the same comprehensive cleanup as startup
    print_status "Performing comprehensive cleanup..."
    kill_port_processes 8000 "Backend API" >/dev/null 2>&1 || true
    kill_port_processes 5173 "Frontend Dev Server" >/dev/null 2>&1 || true
    
    # Kill any remaining processes by pattern
    pkill -f "python.*server.py" 2>/dev/null || true
    pkill -f "uvicorn.*api.server" 2>/dev/null || true
    pkill -f "vite" 2>/dev/null || true
    pkill -f "npm.*run.*dev" 2>/dev/null || true
    
    print_success "Cleanup completed"
    exit 0
}

# Set up signal handling
trap cleanup_on_exit SIGINT SIGTERM

# Main execution
echo ""
print_status "🚀 Starting Lifeboard Full Stack..."
echo ""

# Create logs directory if it doesn't exist
mkdir -p logs

# Clean up any existing processes
cleanup_processes

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