# backend/app/config.py
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATABASE_PATH = BASE_DIR / "data" / "app.db"

# Ensure data directory exists
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)