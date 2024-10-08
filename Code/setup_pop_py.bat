@echo off
REM Exit immediately if a command exits with a non-zero status
SETLOCAL ENABLEEXTENSIONS

REM Check for Python installation
python --version
IF %ERRORLEVEL% NEQ 0 (
    echo Python is not installed. Installing Python 3.10.11 silently...
    
    REM Define Python version and download URL
    SET PYTHON_VERSION=3.10.11
    SET PYTHON_INSTALLER=python-%PYTHON_VERSION%-amd64.exe
    SET PYTHON_URL=https://www.python.org/ftp/python/%PYTHON_VERSION%/%PYTHON_INSTALLER%
    
    REM Download Python installer
    echo Downloading Python from %PYTHON_URL%...
    powershell -Command "Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%PYTHON_INSTALLER%'"
    
    IF %ERRORLEVEL% NEQ 0 (
        echo Failed to download Python installer.
        pause
        exit /b 1
    )
    
    REM Install Python silently for the current user and add to PATH
    echo Installing Python silently...
    %PYTHON_INSTALLER% /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
    
    IF %ERRORLEVEL% NEQ 0 (
        echo Python installation failed.
        pause
        exit /b 1
    )
    
    REM Remove the installer
    del /f /q %PYTHON_INSTALLER%
    
    REM Verify Python installation
    python --version
    IF %ERRORLEVEL% NEQ 0 (
        echo Python installation failed or is not in PATH.
        pause
        exit /b 1
    ) ELSE (
        echo Python installed successfully.
    )
) ELSE (
    echo Python is already installed.
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

REM Install Poppler
echo Installing Poppler...

REM Define Poppler version and download URL
SET POPPLER_VERSION=23.05.0
SET POPPLER_ZIP=poppler-23.05.0.zip
SET POPPLER_URL=https://github.com/oschwartz10612/poppler-windows/releases/download/v%POPPLER_VERSION%/%POPPLER_ZIP%

REM Define installation directory
SET POPPLER_DIR=%CD%\poppler

REM Download Poppler
echo Downloading Poppler from %POPPLER_URL%...
powershell -Command "Invoke-WebRequest -Uri '%POPPLER_URL%' -OutFile '%POPPLER_ZIP%'"

IF %ERRORLEVEL% NEQ 0 (
    echo Failed to download Poppler.
    pause
    exit /b 1
)

REM Extract Poppler using Expand-Archive
echo Extracting Poppler...
powershell -Command "Expand-Archive -Path '%POPPLER_ZIP%' -DestinationPath '%POPPLER_DIR%' -Force"

IF %ERRORLEVEL% NEQ 0 (
    echo Failed to extract Poppler.
    pause
    exit /b 1
)

REM Remove the downloaded zip file
del /f /q %POPPLER_ZIP%

REM Define Poppler bin directory
SET POPPLER_BIN=%POPPLER_DIR%\poppler-%POPPLER_VERSION%\bin

REM Add Poppler's bin directory to PATH for the current session
SET PATH=%POPPLER_BIN%;%PATH%

REM Add Poppler to the user PATH permanently
echo Adding Poppler to user PATH...
powershell -Command "$currentPath = [Environment]::GetEnvironmentVariable('PATH', 'User'); if (-not $currentPath.Contains('%POPPLER_BIN%')) { [Environment]::SetEnvironmentVariable('PATH', '$currentPath;%POPPLER_BIN%', 'User') }"

IF %ERRORLEVEL% NEQ 0 (
    echo Failed to add Poppler to PATH.
    pause
    exit /b 1
)

REM Verify Poppler installation
echo Verifying Poppler installation...
pdftoppm -version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo Poppler installation failed or pdftoppm is not in PATH.
    pause
    exit /b 1
) ELSE (
    echo Poppler installed successfully.
)

REM Create the executable
pyinstaller --onefile --windowed Gui_final.py

IF %ERRORLEVEL% NEQ 0 (
    echo Failed to create the executable.
    pause
    exit /b 1
)

REM Check if Poppler is installed by checking for pdftoppm (Redundant if already verified)
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
