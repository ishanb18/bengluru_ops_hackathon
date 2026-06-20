@echo off
echo ========================================================
echo BengaluruOps 2.0 Backend Startup Script
echo ========================================================
echo Starting Uvicorn with --reload enabled...
echo (This ensures ML model updates and code changes take effect immediately)
echo.
cd %~dp0
call venv\Scripts\activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
