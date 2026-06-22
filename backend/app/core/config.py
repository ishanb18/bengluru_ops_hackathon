# config.py — BengaluruOps Command
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

import os
from dotenv import load_dotenv

# Load backend/.env regardless of cwd when starting uvicorn
load_dotenv(BASE_DIR / "backend" / ".env")

class Settings:
    APP_NAME: str = "BengaluruOps Command"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = True
    API_PREFIX: str = "/api"
    TOMTOM_API_KEY: str = os.getenv("TOMTOM_API_KEY", "")
    TOMTOM_API_KEY_FALLBACK: str = os.getenv("TOMTOM_API_KEY_FALLBACK", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    OPENWEATHER_API_KEY: str = os.getenv("OPENWEATHER_API_KEY", "")
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")

    # CORS — allow local dev + any origin in hackathon demo
    CORS_ORIGINS: list = [
        "http://localhost:5173",   # Vite dev
        "http://localhost:3000",   # React alt
        "http://localhost:8080",
        "http://127.0.0.1:5500",  # VS Code Live Server
        "null",                   # File:// origin (for opening HTML directly)
        "*",
    ]

    # Data paths
    PROCESSED_DIR: Path = BASE_DIR / "backend" / "data" / "processed"
    MODELS_DIR: Path = BASE_DIR / "backend" / "data" / "models"
    DB_PATH: Path = BASE_DIR / "backend" / "data" / "bengaluru_ops.db"

settings = Settings()
