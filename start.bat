@echo off
echo ========================================
echo   HVAC Intelligence Engine
echo ========================================
echo.

echo [1/2] Starting API backend on http://localhost:8000...
start "HVAC Intel — Backend" cmd /k "cd /d %~dp0backend && python main.py"

echo [2/2] Starting frontend UI on http://localhost:5173...
start "HVAC Intel — Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo Servers starting — opening browser in 5 seconds...
echo.
echo   Dashboard:   http://localhost:5173
echo   API Docs:    http://localhost:8000/docs
echo   Health:      http://localhost:8000/api/health
echo.
timeout /t 5 /nobreak >nul
start http://localhost:5173

echo Press any key to exit launcher (servers keep running in their own windows)
pause >nul
