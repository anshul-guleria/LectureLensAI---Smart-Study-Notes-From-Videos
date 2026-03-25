"""
app/services/audio.py
LectureLens — Audio Extraction + Transcription (Groq + Chunking)

Pipeline:
  Video → WAV → Chunk → Groq Whisper → Merge → JSON

Output:
  data/audio/<title>.json
"""

import os
import json
import math
import shutil
from pathlib import Path
from typing import List, Dict, Union

import ffmpeg
from groq import Groq
from dotenv import load_dotenv

# Optional import
try:
    from .video_loader import VideoMeta
except ImportError:
    VideoMeta = None


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

AUDIO_DIR = Path("data/audio")

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise RuntimeError("GROQ_API_KEY not found in .env")

client = Groq(api_key=api_key)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_and_transcribe(
    video_input: Union[str, "VideoMeta"],
    output_dir: Path = AUDIO_DIR,
    chunk_duration_sec: int = 360
) -> List[Dict]:

    output_dir.mkdir(parents=True, exist_ok=True)

    # --- resolve input ---
    if hasattr(video_input, "local_path"):
        video_path = Path(video_input.local_path)
        title = getattr(video_input, "title", video_path.stem)
    else:
        video_path = Path(video_input)
        title = video_path.stem

    video_path = video_path.resolve()

    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    print(f"[audio] Processing video: {video_path.name}")

    json_path = output_dir / f"{_sanitize_filename(title)}.json"

    # --- cache check ---
    if json_path.exists():
        print(f"[audio] Using cached transcription: {json_path.name}")
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)

    # --- extract audio ---
    audio_path = output_dir / f"{_sanitize_filename(title)}.wav"

    if not audio_path.exists():
        print(f"[audio] Extracting audio → {audio_path.name}")
        _extract_audio(video_path, audio_path)
    else:
        print(f"[audio] Using cached audio: {audio_path.name}")

    # --- split audio ---
    chunks = _split_audio(audio_path, chunk_duration_sec)

    # --- transcription ---
    segments = []
    time_offset = 0.0

    for i, chunk_path in enumerate(chunks):
        print(f"[audio] Transcribing chunk {i+1}/{len(chunks)}")

        try:
            with open(chunk_path, "rb") as f:
                response = client.audio.transcriptions.create(
                    file=f,
                    model="whisper-large-v3",
                    response_format="verbose_json",
                    temperature=0.0
                )
        except Exception as e:
            raise RuntimeError(f"Groq transcription failed: {e}")

        for seg in response.segments:
            segments.append({
                "start": float(seg["start"]) + time_offset,
                "end": float(seg["end"]) + time_offset,
                "text": seg["text"].strip(),
                "language": response.language
            })

        time_offset += chunk_duration_sec

    print(f"[audio] Total segments: {len(segments)}")

    # --- save JSON ---
    print(f"[audio] Saving JSON → {json_path.name}")
    _save_json(segments, json_path)

    # --- cleanup chunks ---
    shutil.rmtree(audio_path.parent / "chunks", ignore_errors=True)

    return segments


# ---------------------------------------------------------------------------
# Audio extraction
# ---------------------------------------------------------------------------

def _extract_audio(src: Path, dst: Path) -> None:
    _check_ffmpeg_installed()

    try:
        (
            ffmpeg
            .input(str(src))
            .output(
                str(dst),
                format="wav",
                acodec="pcm_s16le",
                ac=1,
                ar="16000"
            )
            .overwrite_output()
            .run(quiet=True)
        )
    except Exception as e:
        raise RuntimeError(f"ffmpeg extraction failed: {e}")


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def _split_audio(audio_path: Path, chunk_duration_sec: int) -> List[Path]:
    chunks = []

    chunk_dir = audio_path.parent / "chunks"
    chunk_dir.mkdir(exist_ok=True)

    probe = ffmpeg.probe(str(audio_path))
    duration = float(probe["format"]["duration"])

    num_chunks = math.ceil(duration / chunk_duration_sec)

    for i in range(num_chunks):
        start = i * chunk_duration_sec
        out_path = chunk_dir / f"{audio_path.stem}_{i:03d}.wav"

        (
            ffmpeg
            .input(str(audio_path), ss=start, t=chunk_duration_sec)
            .output(str(out_path), acodec="pcm_s16le", ac=1, ar="16000")
            .overwrite_output()
            .run(quiet=True)
        )

        chunks.append(out_path)

    print(f"[audio] Split into {len(chunks)} chunks")

    return chunks


# ---------------------------------------------------------------------------
# Save JSON
# ---------------------------------------------------------------------------

def _save_json(data: List[Dict], path: Path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _check_ffmpeg_installed():
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg not found. Install it first.")


def _sanitize_filename(name: str, max_len: int = 80) -> str:
    import re
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = re.sub(r"\s+", "_", name.strip())
    return name[:max_len]


# ---------------------------------------------------------------------------
# CLI test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m app.services.audio <video_path>")
        sys.exit(1)

    video_input = sys.argv[1]

    print(f"\n[LectureLens] Audio + Groq Transcription\n")

    try:
        segments = extract_and_transcribe(video_input)

        print("\n--- SAMPLE ---")
        for seg in segments[:5]:
            print(f"[{seg['start']:.2f}-{seg['end']:.2f}] {seg['text']}")

        print(f"\n[OK] Segments: {len(segments)}")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)