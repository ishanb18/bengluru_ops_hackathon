#!/bin/bash
# build.sh — Single build script for Render deployment
# Builds both frontend and backend in one step

set -e

echo "=== BengaluruOps 2.0 — Production Build ==="

# 1. Install frontend dependencies and build
echo "[1/3] Building React frontend..."
cd frontend
npm install
npm run build
echo "[OK] Frontend built → frontend/dist/"

# 2. Install backend dependencies
echo "[2/3] Installing Python dependencies..."
cd ../backend
pip install -r requirements.txt
echo "[OK] Backend dependencies installed"

# 3. Done
echo "[3/3] Build complete!"
echo "Start with: cd backend && uvicorn app.main:app --host 0.0.0.0 --port \$PORT"
