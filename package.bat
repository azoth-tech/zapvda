@echo off
echo ==========================================
echo    ZapOrion VDA Analyzer - Build Package
echo ==========================================
echo.

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt >nul 2>&1
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

REM Build the executable
echo Building executable...
pyinstaller vda.spec --clean

echo.
echo ==========================================
echo    Build Complete!
echo ==========================================
echo.
echo Executable: dist\ZapOrion_VDA_Analyzer\ZapOrion_VDA_Analyzer.exe
echo.

pause