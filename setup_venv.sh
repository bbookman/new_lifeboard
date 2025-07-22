#!/bin/bash

# Virtual Environment Setup Script for Lifeboard
# This script creates and configures a Python virtual environment with all dependencies

set -e  # Exit on any error

# Configuration
VENV_NAME="lifeboard_venv"
PYTHON_VERSION="python3"
PROJECT_DIR=$(pwd)

echo "🚀 Lifeboard Virtual Environment Setup"
echo "======================================="

# Check if Python 3 is available
if ! command -v $PYTHON_VERSION &> /dev/null; then
    echo "❌ Error: $PYTHON_VERSION is not installed or not in PATH"
    echo "Please install Python 3.8+ before running this script"
    exit 1
fi

# Get Python version
PYTHON_VER=$($PYTHON_VERSION --version 2>&1 | cut -d' ' -f2)
echo "📍 Using Python version: $PYTHON_VER"

# Check minimum Python version (3.8+)
MIN_VERSION="3.8"
if ! $PYTHON_VERSION -c "import sys; exit(0 if sys.version_info >= (3,8) else 1)"; then
    echo "❌ Error: Python 3.8+ is required. Current version: $PYTHON_VER"
    exit 1
fi

# Remove existing virtual environment if it exists
if [ -d "$VENV_NAME" ]; then
    echo "🗑️  Removing existing virtual environment: $VENV_NAME"
    rm -rf "$VENV_NAME"
fi

# Create virtual environment
echo "🔧 Creating virtual environment: $VENV_NAME"
$PYTHON_VERSION -m venv "$VENV_NAME"

# Activate virtual environment
echo "⚡ Activating virtual environment"
source "$VENV_NAME/bin/activate"

# Upgrade pip, setuptools, and wheel
echo "📦 Upgrading pip, setuptools, and wheel"
pip install --upgrade pip setuptools wheel

# Install requirements
echo "📚 Installing project dependencies"
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    echo "✅ Dependencies installed successfully"
else
    echo "❌ Error: requirements.txt not found"
    exit 1
fi

# Verify key installations
echo "🔍 Verifying key installations"

# Check sentence-transformers
if python -c "import sentence_transformers; print('✅ sentence-transformers:', sentence_transformers.__version__)" 2>/dev/null; then
    :
else
    echo "❌ sentence-transformers installation failed"
    exit 1
fi

# Check torch
if python -c "import torch; print('✅ torch:', torch.__version__)" 2>/dev/null; then
    :
else
    echo "❌ torch installation failed"
    exit 1
fi

# Check numpy
if python -c "import numpy; print('✅ numpy:', numpy.__version__)" 2>/dev/null; then
    :
else
    echo "❌ numpy installation failed"
    exit 1
fi

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from .env.example"
    cp .env.example .env
    echo "⚠️  Please edit .env file to configure your settings"
else
    echo "📝 .env file already exists"
fi

# Create logs directory if it doesn't exist
if [ ! -d "logs" ]; then
    echo "📁 Creating logs directory"
    mkdir -p logs
fi

echo ""
echo "🎉 Virtual Environment Setup Complete!"
echo "======================================="
echo ""
echo "📋 Next Steps:"
echo "1. Activate the virtual environment:"
echo "   source $VENV_NAME/bin/activate"
echo ""
echo "2. Configure your .env file with appropriate settings"
echo ""
echo "3. Test the embedding service:"
echo "   python -c \"from core.embeddings import EmbeddingService; print('✅ Embedding service ready')\""
echo ""
echo "4. Run your application or tests"
echo ""
echo "💡 To deactivate the virtual environment later, run:"
echo "   deactivate"
echo ""
echo "🔧 Virtual environment location: $PROJECT_DIR/$VENV_NAME"