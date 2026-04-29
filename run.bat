@echo off
echo ==========================================
echo    ZapOrion VDA Analyzer
echo ==========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Check if dependencies are installed
python -c "import PySide6, duckdb, requests, polars" >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies into virtual environment...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: Failed to install dependencies.
        pause
        exit /b 1
    )
)

echo Starting ZapOrion VDA Analyzer...
python main.py
if errorlevel 1 (
    echo.
    echo Application exited with an error.
    pause
)
