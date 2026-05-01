@echo off
REM Run AI SOP Monitor in SPA mode on Windows
REM Double-click this file to start the full application
REM Press Ctrl+C to stop

echo ===================================
echo   AI SOP Monitor - SPA Mode
echo ===================================
echo.

REM Step 1: Build frontend
echo [1/2] Building frontend...
cd /d "%~dp0\..\frontend"
call npm run build
if %ERRORLEVEL% neq 0 (
    echo ERROR: Frontend build failed!
    pause
    exit /b 1
)
echo   OK Frontend built -^> static\

REM Step 2: Start backend
echo.
echo [2/2] Starting backend...
cd /d "%~dp0\.."
echo.
echo   http://localhost:8000
echo   http://localhost:8000/docs
echo.
echo   Press Ctrl+C to stop
echo.

python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
