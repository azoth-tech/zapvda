#!/bin/bash
echo "=========================================="
echo "   ZapOrion VDA Analyzer - Build Package"
echo "=========================================="
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install PyInstaller if not present
if ! python -c "import PyInstaller" 2>/dev/null; then
    echo "Installing PyInstaller..."
    pip install pyinstaller
fi

# Build the executable
echo "Building executable..."
pyinstaller vda.spec --clean

echo ""
echo "=========================================="
echo "   Build Complete!"
echo "=========================================="
echo ""

if [ "$(uname)" = "Darwin" ]; then
    echo "macOS App Bundle: dist/ZapOrion_VDA_Analyzer.app"
    echo ""
    echo "To run:  open dist/ZapOrion_VDA_Analyzer.app"
else
    echo "Executable: dist/ZapOrion_VDA_Analyzer/ZapOrion_VDA_Analyzer"
    chmod +x dist/ZapOrion_VDA_Analyzer/ZapOrion_VDA_Analyzer 2>/dev/null
fi

echo ""
echo "Press Enter to exit..."
read
