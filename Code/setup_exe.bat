@echo off
REM ------------------------------------------------------------------------------
REM Setup Script for PDF OCR Tool
REM ------------------------------------------------------------------------------
REM This script automates the installation of Python (version >= 3.11.0), creates
REM a virtual environment, installs all necessary Python dependencies, installs
REM Poppler, and creates an executable using PyInstaller.
REM ------------------------------------------------------------------------------

REM Exit immediately if a command exits with a non-zero status
SETLOCAL ENABLEEXTENSIONS ENABLEDELAYEDEXPANSION

REM ------------------------------------------------------------------------------
REM Function: Check Python Installation and Version
REM ------------------------------------------------------------------------------
:CheckPython
echo Checking for Python installation...

python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo Python is not installed. Proceeding to install Python 3.11.0...
    GOTO :InstallPython
) ELSE (
    FOR /F "tokens=2 delims= " %%A IN ('python --version') DO SET PYTHON_VERSION=%%A
    echo Detected Python version: %PYTHON_VERSION%
    REM Compare Python version
    SET MIN_VERSION=3.11.0
    CALL :VersionCompare %PYTHON_VERSION% %MIN_VERSION%
    IF %VERSION_COMPARE% GEQ 0 (
        echo Python version is sufficient.
        GOTO :EndCheckPython
    ) ELSE (
        echo Python version is below 3.11.0. Please upgrade to at least Python 3.11.0.
        echo Downloading and installing Python 3.11.0...
        GOTO :InstallPython
    )
)

:EndCheckPython
GOTO :EOF

REM ------------------------------------------------------------------------------
REM Function: Version Comparison
REM Compares two version strings and sets VERSION_COMPARE:
REM   -1 : first version is less than second
REM    0 : versions are equal
REM    1 : first version is greater than second
REM Usage: CALL :VersionCompare 3.11.0 3.11.0
REM ------------------------------------------------------------------------------
:VersionCompare
SETLOCAL
SET V1=%1
SET V2=%2

FOR /F "tokens=1-4 delims=." %%a IN ("%V1%") DO (
    SET v1_1=%%a
    SET v1_2=%%b
    SET v1_3=%%c
    SET v1_4=%%d
)

FOR /F "tokens=1-4 delims=." %%a IN ("%V2%") DO (
    SET v2_1=%%a
    SET v2_2=%%b
    SET v2_3=%%c
    SET v2_4=%%d
)

SET /A cmp=0
IF %v1_1% GTR %v2_1% SET /A cmp=1
IF %v1_1% LSS %v2_1% SET /A cmp=-1
IF %v1_1% EQU %v2_1% (
    IF %v1_2% GTR %v2_2% SET /A cmp=1
    IF %v1_2% LSS %v2_2% SET /A cmp=-1
    IF %v1_2% EQU %v2_2% (
        IF %v1_3% GTR %v2_3% SET /A cmp=1
        IF %v1_3% LSS %v2_3% SET /A cmp=-1
    )
)

ENDLOCAL & SET VERSION_COMPARE=%cmp%
GOTO :EOF

REM ------------------------------------------------------------------------------
REM Function: Install Python Silently
REM ------------------------------------------------------------------------------
:InstallPython
REM Define Python version and download URL
SET PYTHON_VERSION=3.11.0
SET PYTHON_INSTALLER=python-%PYTHON_VERSION%-amd64.exe
SET PYTHON_URL=https://www.python.org/ftp/python/%PYTHON_VERSION%/%PYTHON_INSTALLER%

REM Download Python installer using PowerShell
echo Downloading Python %PYTHON_VERSION% from %PYTHON_URL%...
powershell -Command "try { Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%PYTHON_INSTALLER%' } catch { exit 1 }"
IF %ERRORLEVEL% NEQ 0 (
    echo Failed to download Python installer.
    pause
    exit /b 1
)

REM Install Python silently for the current user and add to PATH
echo Installing Python %PYTHON_VERSION% silently...
%PYTHON_INSTALLER% /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
IF %ERRORLEVEL% NEQ 0 (
    echo Python installation failed.
    del /f /q %PYTHON_INSTALLER%
    pause
    exit /b 1
)

REM Remove the installer
del /f /q %PYTHON_INSTALLER%

REM Verify Python installation
echo Verifying Python installation...
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo Python installation failed or is not in PATH.
    pause
    exit /b 1
) ELSE (
    echo Python installed successfully.
)

GOTO :EOF

REM ------------------------------------------------------------------------------
REM Function: Create and Activate Virtual Environment
REM ------------------------------------------------------------------------------
:CreateVenv
echo Creating virtual environment...
python -m venv venv
IF %ERRORLEVEL% NEQ 0 (
    echo Failed to create virtual environment.
    pause
    exit /b 1
)

echo Activating virtual environment...
CALL venv\Scripts\activate
IF %ERRORLEVEL% NEQ 0 (
    echo Failed to activate virtual environment.
    pause
    exit /b 1
)

GOTO :EOF

REM ------------------------------------------------------------------------------
REM Function: Upgrade pip
REM ------------------------------------------------------------------------------
:UpgradePip
echo Upgrading pip...
pip install --upgrade pip
IF %ERRORLEVEL% NEQ 0 (
    echo Failed to upgrade pip.
    pause
    exit /b 1
)
GOTO :EOF

REM ------------------------------------------------------------------------------
REM Function: Install Python Dependencies
REM ------------------------------------------------------------------------------
:InstallDependencies
echo Installing Python dependencies from requirements.txt...
IF NOT EXIST requirements.txt (
    echo requirements.txt not found. Please ensure it exists in the current directory.
    pause
    exit /b 1
)

pip install -r requirements.txt
IF %ERRORLEVEL% NEQ 0 (
    echo Failed to install Python dependencies.
    pause
    exit /b 1
)
GOTO :EOF

REM ------------------------------------------------------------------------------
REM Function: Install PyInstaller
REM ------------------------------------------------------------------------------
:InstallPyInstaller
echo Installing PyInstaller...
pip install pyinstaller
IF %ERRORLEVEL% NEQ 0 (
    echo Failed to install PyInstaller.
    pause
    exit /b 1
)
GOTO :EOF

REM ------------------------------------------------------------------------------
REM Function: Install Poppler
REM ------------------------------------------------------------------------------
:InstallPoppler
echo Installing Poppler...

REM Define Poppler version and download URL
SET POPPLER_VERSION=23.07.0
SET POPPLER_ZIP=poppler-%POPPLER_VERSION%-0.zip
SET POPPLER_URL=https://github.com/oschwartz10612/poppler-windows/releases/download/v%POPPLER_VERSION%/%POPPLER_ZIP%

REM Define installation directory
SET POPPLER_DIR=%CD%\poppler

REM Download Poppler using PowerShell
echo Downloading Poppler from %POPPLER_URL%...
powershell -Command "try { Invoke-WebRequest -Uri '%POPPLER_URL%' -OutFile '%POPPLER_ZIP%' } catch { exit 1 }"
IF %ERRORLEVEL% NEQ 0 (
    echo Failed to download Poppler.
    pause
    exit /b 1
)

REM Extract Poppler using PowerShell
echo Extracting Poppler...
powershell -Command "try { Expand-Archive -Path '%POPPLER_ZIP%' -DestinationPath '%POPPLER_DIR%' -Force } catch { exit 1 }"
IF %ERRORLEVEL% NEQ 0 (
    echo Failed to extract Poppler.
    del /f /q %POPPLER_ZIP%
    pause
    exit /b 1
)

REM Remove the downloaded zip file
del /f /q %POPPLER_ZIP%

REM Define Poppler bin directory
SET POPPLER_BIN=%POPPLER_DIR%\poppler-%POPPLER_VERSION%\Library\bin

REM Add Poppler's bin directory to PATH for the current session
SET PATH=%POPPLER_BIN%;%PATH%

REM Add Poppler to the user PATH permanently
echo Adding Poppler to user PATH...
powershell -Command ^
"$currentPath = [Environment]::GetEnvironmentVariable('PATH', 'User'); ^
 if (-not $currentPath.Contains('%POPPLER_BIN%')) { ^
    [Environment]::SetEnvironmentVariable('PATH', '$currentPath;%POPPLER_BIN%', 'User') }"
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

GOTO :EOF

REM ------------------------------------------------------------------------------
REM Function: Create Executable with PyInstaller
REM ------------------------------------------------------------------------------
:CreateExecutable
echo Creating executable with PyInstaller...
pyinstaller --onefile --windowed Gui_final.py
IF %ERRORLEVEL% NEQ 0 (
    echo Failed to create the executable.
    pause
    exit /b 1
)

GOTO :EOF

REM ------------------------------------------------------------------------------
REM Function: Final Checks and Messages
REM ------------------------------------------------------------------------------
:FinalChecks
echo Checking Poppler installation...
where pdftoppm >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo Poppler is not installed or not in PATH.
    echo Please install Poppler and add it to your system PATH.
    echo Refer to https://github.com/oschwartz10612/poppler-windows for installation instructions.
    pause
    exit /b 1
) ELSE (
    echo All installations completed successfully.
    echo The executable is located in the dist\ folder.
)

GOTO :EOF

REM ------------------------------------------------------------------------------
REM Main Execution Flow
REM ------------------------------------------------------------------------------
CALL :CheckPython
CALL :CreateVenv
CALL :UpgradePip
CALL :InstallDependencies
CALL :InstallPyInstaller
CALL :InstallPoppler
CALL :CreateExecutable
CALL :FinalChecks

echo Setup completed successfully.
pause
EXIT /B 0
