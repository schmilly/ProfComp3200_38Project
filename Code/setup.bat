@echo off
REM Exit immediately if a command exits with a non-zero status
SETLOCAL ENABLEEXTENSIONS

REM Check for Python installation
python --version
IF %ERRORLEVEL% NEQ 0 (
    echo Python is not installed. Please install Python 3.8 or higher from https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Create virtual environment
python -m venv venv

REM Activate virtual environment
call venv\Scripts\activate

REM Upgrade pip
pip install --upgrade pip

REM Install Python dependencies
pip install -r requirements.txt

REM Install PyInstaller
pip install pyinstaller

REM Check if pathlib is installed
python -c "import pathlib" >nul 2>&1
if errorlevel 1 (
    echo "PathLib is not installed; no action needed."
) else (
    echo "PathLib is installed; Uninstalling."
    python -m pip uninstall -y pathlib
)

REM Create the executable
pyinstaller --onefile --windowed Gui_final.py

IF %ERRORLEVEL% NEQ 0 (
    echo Failed to create the executable.
    pause
    exit /b 1
)

REM Check if Poppler is installed by checking for pdftoppm
where pdftoppm >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo Poppler is not installed or not in PATH.
    echo Please install Poppler and add it to your system PATH.
    echo Refer to https://github.com/oschwartz10612/poppler-windows for installation instructions.
    pause
    exit /b 1
)


echo Installation complete.
echo The executable is located in the dist\ folder.
pause
