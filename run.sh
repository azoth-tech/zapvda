#!/bin/bash
echo "=========================================="
echo "   ZapOrion VDA Analyzer"
echo "=========================================="
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed."
    echo "Please install Python 3.10+ from https://python.org"
    exit 1
fi

# Create virtual environment if it doesn't exist
VENV_DIR="venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to create virtual environment."
        exit 1
    fi
fi

# Activate virtual environment
echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Check if dependencies are installed
if ! python -c "import PySide6, duckdb, requests, polars" 2>/dev/null; then
    echo "Installing dependencies into virtual environment..."
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to install dependencies."
        exit 1
    fi
fi

echo "Starting ZapOrion VDA Analyzer..."
python main.py

echo ""
echo "Press Enter to exit..."
read
