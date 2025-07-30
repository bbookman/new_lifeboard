#!/bin/bash

# Lifeboard Server Startup Script
# This script starts the Lifeboard API server with intelligent port management

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default configuration
DEFAULT_PORT=8000
KILL_EXISTING=false
AUTO_PORT=true
DEBUG=false

# Function to print colored output
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

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo "Options:"
    echo "  --port PORT        Specify port number (default: $DEFAULT_PORT)"
    echo "  --kill-existing    Kill existing server processes before starting"
    echo "  --no-auto-port     Don't automatically find available ports"
    echo "  --debug           Enable debug mode"
    echo "  --help            Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                           # Start with auto-port finding"
    echo "  $0 --port 8001             # Start on specific port"
    echo "  $0 --kill-existing         # Kill old processes first"
    echo "  $0 --kill-existing --debug # Kill old processes and start in debug mode"
}

# Function to find server processes
find_server_processes() {
    # Find Python processes running our server
    pgrep -f "python.*api/server.py" 2>/dev/null || true
}

# Function to find processes using a specific port
find_port_processes() {
    local port=$1
    lsof -ti:$port 2>/dev/null || true
}

# Function to kill existing server processes
kill_existing_processes() {
    print_status "Checking for existing server processes..."
    
    local server_pids=$(find_server_processes)
    if [ -n "$server_pids" ]; then
        print_warning "Found existing server processes: $server_pids"
        
        if [ "$KILL_EXISTING" = true ]; then
            print_status "Terminating existing server processes..."
            echo "$server_pids" | xargs kill -TERM 2>/dev/null || true
            sleep 2
            
            # Check if any processes are still running and force kill if needed
            local remaining_pids=$(find_server_processes)
            if [ -n "$remaining_pids" ]; then
                print_warning "Some processes didn't respond to TERM signal, force killing..."
                echo "$remaining_pids" | xargs kill -KILL 2>/dev/null || true
                sleep 1
            fi
            
            print_success "Existing server processes terminated"
        else
            print_warning "Use --kill-existing to automatically terminate them"
            
            # Interactive mode - ask user what to do
            echo ""
            echo -e "${YELLOW}What would you like to do?${NC}"
            echo "1) Kill existing processes and continue"
            echo "2) Continue anyway (may fail if ports conflict)"
            echo "3) Exit"
            echo -n "Choice [1-3]: "
            read -r choice
            
            case $choice in
                1)
                    print_status "Terminating existing processes..."
                    echo "$server_pids" | xargs kill -TERM 2>/dev/null || true
                    sleep 2
                    local remaining_pids=$(find_server_processes)
                    if [ -n "$remaining_pids" ]; then
                        echo "$remaining_pids" | xargs kill -KILL 2>/dev/null || true
                    fi
                    print_success "Processes terminated"
                    ;;
                2)
                    print_warning "Continuing with existing processes running..."
                    ;;
                3)
                    print_status "Exiting..."
                    exit 0
                    ;;
                *)
                    print_error "Invalid choice. Exiting..."
                    exit 1
                    ;;
            esac
        fi
    else
        print_success "No existing server processes found"
    fi
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --port)
            DEFAULT_PORT="$2"
            shift 2
            ;;
        --kill-existing)
            KILL_EXISTING=true
            shift
            ;;
        --no-auto-port)
            AUTO_PORT=false
            shift
            ;;
        --debug)
            DEBUG=true
            shift
            ;;
        --help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Main execution
echo ""
print_status "🚀 Starting Lifeboard API server..."
echo ""

# Change to the project directory
cd "$(dirname "$0")"

# Kill existing processes if requested or prompt user
kill_existing_processes

# Build server command
SERVER_CMD="python api/server.py"

if [ "$AUTO_PORT" = true ]; then
    SERVER_CMD="$SERVER_CMD --auto-port --port $DEFAULT_PORT"
    print_status "Using auto-port mode starting from port $DEFAULT_PORT"
else
    SERVER_CMD="$SERVER_CMD --port $DEFAULT_PORT"
    print_status "Using fixed port $DEFAULT_PORT"
fi

if [ "$DEBUG" = true ]; then
    SERVER_CMD="$SERVER_CMD --debug"
    print_status "Debug mode enabled"
fi

echo ""
print_status "Executing: $SERVER_CMD"
echo ""

# Start the server
if $SERVER_CMD; then
    print_success "Server started successfully"
else
    print_error "Server failed to start"
    echo ""
    print_status "💡 Troubleshooting tips:"
    echo "  • Try: $0 --kill-existing"
    echo "  • Try: $0 --port 8001"
    echo "  • Check logs in: logs/lifeboard.log"
    exit 1
fi

echo ""
print_status "Server stopped."