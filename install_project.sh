#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

echo "Starting project installation..."

# 1. Create Python virtual environment
echo "1. Creating Python virtual environment..."
python3 -m venv venv
echo "   Virtual environment 'venv' created."

# 2. Activate the virtual environment
echo "2. Activating virtual environment..."
source venv/bin/activate
echo "   Virtual environment activated."

# 3. Install Python requirements
echo "3. Installing Python dependencies from requirements.txt..."
pip3 install -r requirements.txt
echo "   Python dependencies installed."

# 4. Navigate to the frontend directory and install Node.js dependencies
echo "4. Navigating to frontend directory and installing Node.js dependencies..."
cd frontend
npm install
echo "   Node.js dependencies installed."

# 5. Build the Node.js project
echo "5. Building the Node.js project..."
npm run build
echo "   Node.js project built."

# Navigate back to the root directory
cd ..

echo "Project installation complete!"
echo "To activate the Python virtual environment, run: source venv/bin/activate"
echo "To run the full stack, use: ./start_full_stack.sh"
