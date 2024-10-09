@echo off
REM ------------------------------------------------------------------------------
REM Setup Script for PDF OCR Tool
REM ------------------------------------------------------------------------------
REM This script automates the installation of Python (version >= 3.11.0), creates
REM a virtual environment, installs all necessary Python dependencies, installs
REM Poppler, and creates an executable using PyInstaller.
REM ------------------------------------------------------------------------------
REM Author: William vdWBake (23086983)
REM Date: October 8, 2024
REM ------------------------------------------------------------------------------

REM ------------------------------------------------------------------------------
REM Initialization
REM ------------------------------------------------------------------------------
SETLOCAL ENABLEEXTENSIONS ENABLEDELAYEDEXPANSION

REM Define log files
SET PYTHON_LOG=install_python.log
SET POPPLER_LOG=install_poppler.log

REM Define minimum Python version
SET MIN_PYTHON_VERSION=3.11.0

REM Define Poppler version and download URL
SET POPPLER_URL=https://github.com/oschwartz10612/poppler-windows/releases/download/v24.08.0-0/Release-24.08.0-0.zip

REM Define Python installer URL for the latest 3.11.x version
REM Note: Update PYTHON_VERSION_DOWNLOAD if a newer patch is available
SET PYTHON_VERSION_DOWNLOAD=3.11.5
SET PYTHON_INSTALLER=python-%PYTHON_VERSION_DOWNLOAD%-amd64.exe
SET PYTHON_URL=https://www.python.org/ftp/python/%PYTHON_VERSION_DOWNLOAD%/%PYTHON_INSTALLER%

REM Define installation directories
SET POPPLER_DIR=%CD%\poppler
SET VENV_DIR=venv

REM ------------------------------------------------------------------------------
REM Function: Check Python Installation and Version
REM ------------------------------------------------------------------------------
:: Commented this out as currently doesn't work properly
:CheckPython
::echo ================================
::echo Checking for Python installation...
::echo ================================
::python --version >nul 2>&1
::IF %ERRORLEVEL% NEQ 0 (
::    echo Python is not installed. Proceeding to install Python %PYTHON_VERSION_DOWNLOAD%...
::    GOTO :InstallPython
::) ELSE (
::    for /f "tokens=2 delims==" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
::    echo Python version: %PYTHON_VERSION%
::    REM Compare Python version using PowerShell
::    FOR /F %%A IN ('powershell -Command "if ([version]'%PYTHON_VERSION%' -ge [version]'%MIN_PYTHON_VERSION%') { Write-Output 1 } else { Write-Output -1 }"') DO SET VERSION_COMPARE=%%A
::    IF "%VERSION_COMPARE%"=="1" (
::        echo Python version is sufficient.
::        GOTO :EndCheckPython
::    ) ELSE (
::        echo Python version is below %MIN_PYTHON_VERSION%. Proceeding to install Python %PYTHON_VERSION_DOWNLOAD%...
::        GOTO :InstallPython
::    )
::)
:EndCheckPython
echo.
GOTO :CreateVenv

REM ------------------------------------------------------------------------------
REM Function: Install Python Silently
REM ------------------------------------------------------------------------------
:InstallPython
echo ================================
echo Installing Python %PYTHON_VERSION_DOWNLOAD% silently...
echo ================================
REM Download Python installer using PowerShell
powershell -Command "try { Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%PYTHON_INSTALLER%' -UseBasicParsing } catch { exit 1 }"
IF %ERRORLEVEL% NEQ 0 (
    echo Failed to download Python installer.
    echo Please check your internet connection or the Python download URL.
    pause
    EXIT /B 1
)

REM Install Python silently for the current user and add to PATH
REM /quiet : Silent mode
REM InstallAllUsers=0 : Install for the current user only
REM PrependPath=1 : Add Python to PATH
REM Include_test=0 : Do not install test suite
REM /log : Log installation details
%PYTHON_INSTALLER% /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 /log "%PYTHON_LOG%"
IF %ERRORLEVEL% NEQ 0 (
    echo Python installation failed. Check %PYTHON_LOG% for details.
    del /f /q %PYTHON_INSTALLER%
    pause
    EXIT /B 1
)

REM Remove the installer after successful installation
del /f /q %PYTHON_INSTALLER%

REM Define Python installation directory (Assuming default installation path)
SET PYTHON_INSTALL_DIR=%LOCALAPPDATA%\Programs\Python\Python%PYTHON_VERSION_DOWNLOAD%

REM Add Python installation directory to PATH in current session
IF EXIST "%PYTHON_INSTALL_DIR%\python.exe" (
    SET PATH=%PYTHON_INSTALL_DIR%;%PYTHON_INSTALL_DIR%\Scripts;%PATH%
    echo Added Python to PATH in the current session.
) ELSE (
    echo Python installation directory not found. Please verify installation.
    pause
    EXIT /B 1
)

REM Verify Python installation
echo Verifying Python installation...
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo Python installation failed or is not in PATH.
    pause
    EXIT /B 1
) ELSE (
    FOR /F "tokens=2 delims= " %%A IN ('python --version') DO SET PYTHON_VERSION_VERIFIED=%%A
    echo Python installed successfully. Version: %PYTHON_VERSION_VERIFIED%
)
:End
echo.
GOTO :EOF

REM ------------------------------------------------------------------------------
REM Function: Create and Activate Virtual Environment
REM ------------------------------------------------------------------------------
:CreateVenv
echo ================================
echo Creating virtual environment...
echo ================================
REM Check if virtual environment already exists
IF EXIST %VENV_DIR% (
    echo Existing virtual environment detected. Deleting...
    rmdir /S /Q %VENV_DIR%
    IF %ERRORLEVEL% NEQ 0 (
        echo Failed to delete existing virtual environment.
        pause
        EXIT /B 1
    )
)

REM Create virtual environment
python -m venv %VENV_DIR%
IF %ERRORLEVEL% NEQ 0 (
    echo Failed to create virtual environment.
    pause
    EXIT /B 1
)

echo Activating virtual environment...
CALL %VENV_DIR%\Scripts\activate
IF %ERRORLEVEL% NEQ 0 (
    echo Failed to activate virtual environment.
    pause
    EXIT /B 1
)

REM Verify activation by checking Python executable path
FOR /F "tokens=2 delims=:" %%A IN ('python -c "import sys; print(sys.executable)"') DO SET PYTHON_EXEC=%%A
IF NOT DEFINED PYTHON_EXEC (
    echo Virtual environment activation failed.
    pause
    EXIT /B 1
) ELSE (
    echo Virtual environment activated successfully.
    
    GOTO :UpgradePip
)

echo.
GOTO :EOF

REM ------------------------------------------------------------------------------
REM Function: Upgrade pip
REM ------------------------------------------------------------------------------
:UpgradePip
echo ================================
echo Upgrading pip...
echo ================================
python -m pip install --upgrade pip
IF %ERRORLEVEL% NEQ 0 (
    echo Failed to upgrade pip.
    pause
    EXIT /B 1
)
echo Pip upgraded successfully.
GOTO :InstallDependencies
echo.
GOTO :EOF

REM ------------------------------------------------------------------------------
REM Function: Install Python Dependencies
REM ------------------------------------------------------------------------------
:InstallDependencies
echo ================================
echo Installing Python dependencies from requirements.txt...
echo ================================
IF NOT EXIST requirements.txt (
    echo requirements.txt not found. Please ensure it exists in the current directory.
    pause
    EXIT /B 1
)

pip install -r requirements.txt
IF %ERRORLEVEL% NEQ 0 (
    echo Failed to install Python dependencies.
    pause
    EXIT /B 1
)
echo Python dependencies installed successfully.
GOTO :InstallPyInstaller
echo.
GOTO :EOF

REM ------------------------------------------------------------------------------
REM Function: Install PyInstaller
REM ------------------------------------------------------------------------------
:InstallPyInstaller
echo ================================
echo Installing PyInstaller...
echo ================================
pip install pyinstaller
IF %ERRORLEVEL% NEQ 0 (
    echo Failed to install PyInstaller.
    pause
    EXIT /B 1
)
echo PyInstaller installed successfully.
GOTO :InstallPoppler
echo.
GOTO :EOF

REM ------------------------------------------------------------------------------
REM Function: Install Poppler
REM ------------------------------------------------------------------------------
:InstallPoppler
echo ================================
echo Installing Poppler...
echo ================================

REM Download Poppler using PowerShell
echo Downloading Poppler from %POPPLER_URL%...
powershell -Command "try { Invoke-WebRequest -Uri '%POPPLER_URL%' -OutFile '%POPPLER_ZIP%' -UseBasicParsing } catch { exit 1 }"
IF %ERRORLEVEL% NEQ 0 (
    echo Failed to download Poppler.
    pause
    EXIT /B 1
)

REM Extract Poppler using PowerShell
echo Extracting Poppler...
powershell -Command "try { Expand-Archive -Path '%POPPLER_ZIP%' -DestinationPath '%POPPLER_DIR%' -Force } catch { exit 1 }"
IF %ERRORLEVEL% NEQ 0 (
    echo Failed to extract Poppler.
    del /f /q %POPPLER_ZIP%
    pause
    EXIT /B 1
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
    EXIT /B 1
)

REM Verify Poppler installation
echo Verifying Poppler installation...
pdftoppm -version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo Poppler installation failed or pdftoppm is not in PATH.
    pause
    EXIT /B 1
) ELSE (
    echo Poppler installed successfully.
    GOTO :CreateExecutable
)
echo.
GOTO :EOF

REM ------------------------------------------------------------------------------
REM Function: Create Executable with PyInstaller
REM ------------------------------------------------------------------------------
:CreateExecutable
echo ================================
echo Creating executable with PyInstaller...
echo ================================
pyinstaller --noconfirm --onedir --console Gui_final.py
IF %ERRORLEVEL% NEQ 0 (
    echo Failed to create the executable.
    pause
    EXIT /B 1
)
echo Executable created successfully.
GOTO :FinalChecks
echo.
GOTO :EOF

REM ------------------------------------------------------------------------------
REM Function: Final Checks and Messages
REM ------------------------------------------------------------------------------
:FinalChecks
echo ================================
echo Performing final checks...
echo ================================
echo Checking Poppler installation...
where pdftoppm >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo Poppler is not installed or not in PATH.
    echo Please install Poppler and add it to your system PATH.
    echo Refer to https://github.com/oschwartz10612/poppler-windows for installation instructions.
    pause
) ELSE (
    echo All installations completed successfully.
    echo The executable is located in the dist\ folder.
)

echo.
GOTO :EOF

REM ------------------------------------------------------------------------------
REM Main Execution Flow
REM ------------------------------------------------------------------------------
CALL :CreateVenv
CALL :UpgradePip
CALL :InstallDependencies
CALL :InstallPyInstaller
CALL :InstallPoppler
CALL :CreateExecutable
CALL :FinalChecks

echo ================================
echo Setup completed
echo ================================
pause
EXIT /B 0
