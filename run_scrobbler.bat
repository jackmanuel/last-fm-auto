@echo off
REM ============================================================================
REM  Last.fm Auto Scrobbler - Startup Script
REM  This script activates the local Python virtual environment and runs the
REM  main scrobbler application in continuous mode.
REM  It is designed to be portable and can be run from a shortcut anywhere,
REM  including the Windows Startup folder.
REM ============================================================================

REM --- Step 1: Find the Project Directory ---
REM This is the magic command. %~dp0 expands to the drive and path of this
REM batch file. This makes the script location-independent.
SET "PROJECT_DIR=%~dp0"
ECHO Project directory set to: %PROJECT_DIR%

REM --- Step 2: Activate the Virtual Environment ---
REM Check if the virtual environment exists before trying to activate it.
IF NOT EXIST "%PROJECT_DIR%venv\Scripts\activate.bat" (
    ECHO.
    ECHO ERROR: Virtual environment not found!
    ECHO Please ensure you have run the setup steps from the README.md file.
    ECHO The script expects the venv at: %PROJECT_DIR%venv\
    PAUSE
    EXIT /B 1
)

ECHO Activating the virtual environment...
CALL "%PROJECT_DIR%venv\Scripts\activate.bat"

REM --- Step 3: Change to the Project Directory ---
REM Change the current directory to the project root. This ensures that
REM Python's module resolution and any relative file paths work correctly.
cd /d "%PROJECT_DIR%"

REM --- Step 4: Run the Main Python Application ---
ECHO Starting the scrobbler application...
ECHO (To stop the scrobbler, close this window or press Ctrl+C)
ECHO.
python -m last_fm_auto.main

REM --- Optional: Pause on Exit ---
REM Uncomment the line below if you want the window to stay open after the
REM script finishes (useful for debugging, but not for startup).
REM PAUSE