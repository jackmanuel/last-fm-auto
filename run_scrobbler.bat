@echo off
REM Get the directory of this script, which is the project root
SET "SCRIPT_DIR=%~dp0"

REM Activate the virtual environment using an absolute path
CALL "%SCRIPT_DIR%venv\Scripts\activate.bat"

REM Run the Python script using an absolute path
echo Starting the Last.fm Scrobbler...
python "%SCRIPT_DIR%scrobbler.py"

REM Pause at the end to keep the window open and see any final output
echo.
pause
