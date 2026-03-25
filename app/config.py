"""
app/config.py
LectureLensAI — Configuration
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "lecturelens-dev-secret")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"

    DATA_DIR = BASE_DIR / "data"
    CACHE_DIR = DATA_DIR / "cache"
    AUDIO_DIR = DATA_DIR / "audio"
    VIDEO_DIR = DATA_DIR / "videos"
    NOTES_DIR = DATA_DIR / "notes"
    FLASHCARDS_DIR = DATA_DIR / "flashcards"
    EXPORTS_DIR = DATA_DIR / "exports"

    MAX_CONTENT_LENGTH = 2 * 1024 * 1024 * 1024  # 2 GB upload limit


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
