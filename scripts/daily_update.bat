@echo off
REM Daily Bloomberg update — wrapper for Windows Task Scheduler
REM Runs the Python script from the project root directory
cd /d "%~dp0\.."
python scripts\daily_update.py --lookback-days 5
