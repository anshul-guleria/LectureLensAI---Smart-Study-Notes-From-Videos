"""
app/utils/cache.py
LectureLensAI — JSON Cache Utilities
"""

import json
from pathlib import Path
from typing import List, Dict, Optional

CACHE_DIR = Path("data/cache")


def load_json(path: Path) -> Optional[List[Dict]]:
    """Load JSON from a path; return None if missing."""
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_json(path: Path, data) -> None:
    """Save data as JSON to path, creating parent dirs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def demo_segments() -> List[Dict]:
    return load_json(CACHE_DIR / "demo_segments.json") or []


def demo_notes() -> List[Dict]:
    return load_json(CACHE_DIR / "demo_notes.json") or []


def demo_flashcards() -> List[Dict]:
    return load_json(CACHE_DIR / "demo_flashcards.json") or []
