"""
app/services/pipeline.py
LectureLensAI — Full Pipeline Orchestrator

Runs the complete processing pipeline in a background thread.
Each job is tracked by a UUID in the JOBS dict AND persisted to disk,
so results survive Flask server restarts.

Demo mode skips all LLM/ffmpeg calls and uses cached JSON fixtures.
"""

import uuid
import threading
import traceback
from pathlib import Path
from typing import Dict, Any

from ..utils.cache import demo_segments, demo_notes, demo_flashcards, load_json, save_json
from ..utils.helpers import sanitize_filename

# In-memory job store  {job_id: {...}}
JOBS: Dict[str, Dict[str, Any]] = {}

# Disk persistence dir — survives server restarts
JOBS_DIR = Path("data/jobs")

# Demo YouTube video (ML lecture)
DEMO_VIDEO_ID = "ukzFI9rgwfU"
DEMO_VIDEO_URL = f"https://www.youtube.com/embed/{DEMO_VIDEO_ID}?enablejsapi=1"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def start_pipeline(input_data: str, demo: bool = False) -> str:
    """Start the pipeline in a background thread. Returns job_id."""
    job_id = str(uuid.uuid4())
    JOBS[job_id] = {
        "status": "running",
        "step": "Initialising",
        "progress": 0,
        "error": None,
        "notes": [],
        "flashcards": [],
        "pdf_path": None,
        "video_url": None,
        "video_type": None,
        "title": "Demo Lecture" if demo else (
            Path(input_data).stem if not input_data.startswith("http") else "YouTube Lecture"
        ),
    }
    thread = threading.Thread(
        target=_run_pipeline,
        args=(job_id, input_data, demo),
        daemon=True
    )
    thread.start()
    return job_id


def get_job(job_id: str) -> Dict[str, Any]:
    """Get job from memory, falling back to disk (survives server restarts)."""
    if job_id in JOBS:
        return JOBS[job_id]

    # Try disk fallback
    job_path = JOBS_DIR / f"{job_id}.json"
    if job_path.exists():
        data = load_json(job_path)
        if data:
            JOBS[job_id] = data
            return data

    return {"status": "not_found"}


# ---------------------------------------------------------------------------
# Internal pipeline orchestration
# ---------------------------------------------------------------------------

def _update(job_id: str, step: str, progress: int):
    JOBS[job_id]["step"] = step
    JOBS[job_id]["progress"] = progress


def _run_pipeline(job_id: str, input_data: str, demo: bool):
    try:
        if demo:
            _run_demo(job_id)
        else:
            _run_full(job_id, input_data)
        _persist_job(job_id)
    except Exception as e:
        JOBS[job_id]["status"] = "error"
        JOBS[job_id]["error"] = str(e)
        JOBS[job_id]["progress"] = 0
        traceback.print_exc()
        _persist_job(job_id)


def _persist_job(job_id: str):
    """Save job state to disk so it survives server restarts."""
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    save_json(JOBS_DIR / f"{job_id}.json", JOBS[job_id])


# ---------------------------------------------------------------------------
# Demo pipeline (no LLM, no ffmpeg)
# ---------------------------------------------------------------------------

def _run_demo(job_id: str):
    """Load cached fixtures instantly."""
    import time

    _update(job_id, "Loading video metadata", 10)
    time.sleep(0.4)

    _update(job_id, "Fetching transcript (cached)", 30)
    time.sleep(0.4)
    segments = demo_segments()

    _update(job_id, "Generating structured notes (cached)", 55)
    time.sleep(0.4)
    notes = demo_notes()

    _update(job_id, "Generating flashcards (cached)", 75)
    time.sleep(0.4)
    flashcards = demo_flashcards()

    _update(job_id, "Exporting PDF", 90)
    pdf_path = _export_pdf(notes, flashcards, title="Introduction to Machine Learning")

    JOBS[job_id].update({
        "status": "done",
        "step": "Complete",
        "progress": 100,
        "notes": notes,
        "flashcards": flashcards,
        "pdf_path": str(pdf_path) if pdf_path else None,
        "title": "Introduction to Machine Learning",
        "video_url": DEMO_VIDEO_URL,
        "video_type": "youtube",
    })


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------

def _run_full(job_id: str, input_data: str):
    """Full pipeline: video → audio → notes → flashcards → PDF."""
    _update(job_id, "Loading video", 10)
    from .video_loader import load_video
    meta = load_video(input_data)
    title = meta.title
    JOBS[job_id]["title"] = title

    # Video URL
    if meta.source == "youtube":
        vid_id = _extract_youtube_id(meta.original_input)
        JOBS[job_id]["video_url"] = f"https://www.youtube.com/embed/{vid_id}?enablejsapi=1" if vid_id else None
        JOBS[job_id]["video_type"] = "youtube"
    else:
        JOBS[job_id]["video_url"] = f"/api/video/{job_id}"
        JOBS[job_id]["video_type"] = "local"
        JOBS[job_id]["_local_path"] = str(meta.local_path)

    # Transcribe
    _update(job_id, "Transcribing audio with Whisper", 30)
    segments_cache = Path(f"data/audio/{sanitize_filename(title)}.json")
    segments = load_json(segments_cache) if segments_cache.exists() else None
    if not segments:
        from .audio import extract_and_transcribe
        segments = extract_and_transcribe(meta)

    # Generate notes
    _update(job_id, "Generating notes with LLaMA 3.3", 55)
    notes_cache = Path(f"data/notes/{sanitize_filename(title)}_notes.json")
    notes = load_json(notes_cache) if notes_cache.exists() else None
    if not notes:
        from .notes import generate_notes
        notes = generate_notes(segments)
        save_json(notes_cache, notes)

    # Generate flashcards
    _update(job_id, "Generating flashcards", 75)
    fc_cache = Path(f"data/flashcards/{sanitize_filename(title)}_flashcards.json")
    flashcards = load_json(fc_cache) if fc_cache.exists() else None
    if not flashcards:
        from .flashcards import generate_flashcards
        flashcards = generate_flashcards(notes)
        save_json(fc_cache, flashcards)

    # Export PDF
    _update(job_id, "Exporting PDF", 90)
    pdf_path = _export_pdf(notes, flashcards, title=title)

    JOBS[job_id].update({
        "status": "done",
        "step": "Complete",
        "progress": 100,
        "notes": notes,
        "flashcards": flashcards,
        "pdf_path": str(pdf_path) if pdf_path else None,
    })


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _export_pdf(notes, flashcards, title="Lecture Notes"):
    try:
        from .pdf_export import export_pdf
        output_dir = Path(__file__).resolve().parent.parent.parent / "data" / "exports"
        output_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = export_pdf(notes, flashcards, title=title, output_dir=output_dir)
        return pdf_path
    except Exception as e:
        print(f"[pipeline] PDF export failed: {e}")
        traceback.print_exc()
        return None


def _extract_youtube_id(url: str) -> str:
    import re
    m = re.search(r"(?:v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})", url)
    return m.group(1) if m else ""
