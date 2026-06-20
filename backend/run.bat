@echo off
echo ============================================================
echo  BengaluruOps Command — Backend Setup ^& Launch
echo ============================================================
echo.

REM Step 1: Install dependencies
echo [1/4] Installing Python dependencies...
pip install -r requirements.txt --quiet
echo Done.

REM Step 2: Copy the CSV to the right place if not already there
if not exist "data\raw\Astram_event_data_anonymized.csv" (
    echo [2/4] Copying raw dataset...
    copy "..\Astram event data_anonymized - Astram event data_anonymizedb40ac87.csv" "data\raw\Astram_event_data_anonymized.csv"
) else (
    echo [2/4] Raw dataset already in place.
)

REM Step 3: Run ML pipeline
echo [3/4] Running ML pipeline (data prep + training)...
python ml\data_prep.py
python ml\train_classifier.py
python ml\train_duration.py
python ml\corridor_risk.py
echo ML pipeline complete.

REM Step 4: Start FastAPI server
echo [4/4] Starting FastAPI server on http://localhost:8000 ...
echo       Press Ctrl+C to stop.
echo.
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
