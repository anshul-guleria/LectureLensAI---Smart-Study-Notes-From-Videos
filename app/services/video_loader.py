"""
app/services/video_loader.py
LectureLens — Media Loader

Accepts:
  - A local video/audio file  (.mp4, .mkv, .avi, .mov, .webm, .m4v,
                               .mp3, .m4a, .wav, .aac, .ogg, .flac)
  - A YouTube URL             (any valid yt-dlp-supported URL)

Returns:
  - Absolute path to a local audio/video file ready for processing
  - VideoMeta dataclass with duration, title, source info
"""

import os
import re
import shutil
import tempfile
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


SUPPORTED_EXTENSIONS = {
    # video
    ".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v",
    # audio
    ".mp3", ".m4a", ".wav", ".aac", ".ogg", ".flac",
}
MAX_FILE_SIZE_GB = 2.0
OUTPUT_DIR = Path("data/audio_dl")  # where downloaded audio files are saved

YOUTUBE_URL_PATTERNS = [
    r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=[\w-]+",
    r"(?:https?://)?(?:www\.)?youtu\.be/[\w-]+",
    r"(?:https?://)?(?:www\.)?youtube\.com/shorts/[\w-]+",
    r"(?:https?://)?(?:www\.)?youtube\.com/live/[\w-]+",
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class VideoMeta:
    title: str
    source: str          # "local" or "youtube"
    original_input: str  # the path or URL the user passed in
    local_path: Path     # final audio/video path on disk
    duration_seconds: float = 0.0
    language_hint: Optional[str] = None   # e.g. "hi", "en" — filled by Whisper later
    extra: dict = field(default_factory=dict)  # raw yt-dlp metadata if available

    def duration_str(self) -> str:
        m, s = divmod(int(self.duration_seconds), 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_video(input_path_or_url: str, output_dir: Optional[Path] = None) -> VideoMeta:
    """
    Main entry point.

    Args:
        input_path_or_url: local file path or YouTube URL string
        output_dir: where to save downloaded audio (default: data/audio_dl/)

    Returns:
        VideoMeta with .local_path pointing to a valid audio/video file

    Raises:
        ValueError: bad input, unsupported format, file too large
        RuntimeError: yt-dlp not found, download failed
        FileNotFoundError: local file doesn't exist
    """
    out_dir = Path(output_dir) if output_dir else OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    inp = input_path_or_url.strip()

    if _is_youtube_url(inp):
        return _load_from_youtube(inp, out_dir)
    else:
        return _load_from_local(inp, out_dir)


# ---------------------------------------------------------------------------
# Local file loader
# ---------------------------------------------------------------------------

def _load_from_local(path_str: str, out_dir: Path) -> VideoMeta:
    path = Path(path_str).expanduser().resolve()

    # --- existence check ---
    if not path.exists():
        raise FileNotFoundError(f"Video file not found: {path}")

    # --- extension check ---
    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{ext}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    # --- size check ---
    size_gb = path.stat().st_size / (1024 ** 3)
    if size_gb > MAX_FILE_SIZE_GB:
        raise ValueError(
            f"File too large ({size_gb:.2f} GB). Max allowed: {MAX_FILE_SIZE_GB} GB"
        )

    # Use the file as-is (ffmpeg in audio.py handles all supported formats)
    out_path = out_dir / path.name
    if not out_path.exists():
        shutil.copy2(path, out_path)

    duration = _get_duration(out_path)

    print(f"[video_loader] Local file ready: {out_path} ({_fmt_size(out_path)}, {_fmt_duration(duration)})")

    return VideoMeta(
        title=path.stem,
        source="local",
        original_input=str(path),
        local_path=out_path,
        duration_seconds=duration,
    )


# ---------------------------------------------------------------------------
# YouTube downloader
# ---------------------------------------------------------------------------

def _load_from_youtube(url: str, out_dir: Path) -> VideoMeta:
    _check_ytdlp_installed()

    print(f"[video_loader] Fetching metadata for: {url}")
    meta = _fetch_yt_metadata(url)

    title_safe = _sanitize_filename(meta.get("title", "lecture"))
    m4a_path = out_dir / f"{title_safe}.m4a"

    if m4a_path.exists():
        print(f"[video_loader] Already downloaded, using cached: {m4a_path}")
    else:
        print(f"[video_loader] Downloading audio: {meta.get('title', url)}")
        _download_audio(url, m4a_path)

    duration = meta.get("duration", 0) or _get_duration(m4a_path)

    print(f"[video_loader] YouTube audio ready: {m4a_path} ({_fmt_duration(duration)})")

    return VideoMeta(
        title=meta.get("title", title_safe),
        source="youtube",
        original_input=url,
        local_path=m4a_path,
        duration_seconds=float(duration),
        extra={
            "uploader": meta.get("uploader", ""),
            "view_count": meta.get("view_count", 0),
            "upload_date": meta.get("upload_date", ""),
            "description": meta.get("description", "")[:500],  # first 500 chars
        }
    )


def _fetch_yt_metadata(url: str) -> dict:
    """Run yt-dlp --dump-json to get video metadata without downloading."""
    try:
        result = subprocess.run(
            ["yt-dlp", "--dump-json", "--no-playlist", url],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            raise RuntimeError(f"yt-dlp metadata fetch failed:\n{result.stderr.strip()}")
        import json
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        raise RuntimeError("yt-dlp metadata fetch timed out (30s). Check your internet connection.")


def _download_audio(url: str, output_path: Path) -> None:
    """Download best audio only, save as m4a — no video stream."""
    tmp_path = output_path.with_suffix(".%(ext)s")

    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--format", "bestaudio[ext=m4a]/bestaudio/best",
        "--extract-audio",
        "--audio-format", "m4a",
        "--output", str(tmp_path),
        "--no-warnings",
        "--progress",
        url,
    ]

    try:
        result = subprocess.run(cmd, timeout=600)  # 10 min max
        if result.returncode != 0:
            raise RuntimeError(f"yt-dlp audio download failed for: {url}")
    except subprocess.TimeoutExpired:
        raise RuntimeError("Download timed out (10 min). Try a shorter video.")

    # yt-dlp may write the final file with the resolved extension
    actual = output_path.with_suffix(".m4a")
    if not actual.exists():
        # search for what yt-dlp actually wrote
        candidates = list(output_path.parent.glob(output_path.stem + ".*"))
        if not candidates:
            raise RuntimeError(f"Downloaded audio file not found in {output_path.parent}")
        actual = candidates[0]
        if actual != output_path:
            actual.rename(output_path)


# ---------------------------------------------------------------------------
# ffmpeg helpers
# ---------------------------------------------------------------------------

def _convert_to_mp4(src: Path, dst: Path) -> None:
    """Re-encode to h264/aac mp4 using ffmpeg."""
    _check_ffmpeg_installed()
    cmd = [
        "ffmpeg", "-y",
        "-i", str(src),
        "-c:v", "libx264", "-crf", "23", "-preset", "fast",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        str(dst)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg conversion failed:\n{result.stderr[-500:]}")


def _get_duration(path: Path) -> float:
    """Return video duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path)
            ],
            capture_output=True, text=True, timeout=10
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Validators & utilities
# ---------------------------------------------------------------------------

def _is_youtube_url(s: str) -> bool:
    return any(re.match(p, s) for p in YOUTUBE_URL_PATTERNS)


def _check_ytdlp_installed() -> None:
    if shutil.which("yt-dlp") is None:
        raise RuntimeError(
            "yt-dlp not found. Install it with:\n"
            "  pip install yt-dlp\n"
            "  or: brew install yt-dlp"
        )


def _check_ffmpeg_installed() -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "ffmpeg not found. Install it with:\n"
            "  brew install ffmpeg       (macOS)\n"
            "  sudo apt install ffmpeg   (Ubuntu/WSL)"
        )


def _sanitize_filename(name: str, max_len: int = 80) -> str:
    """Strip illegal filename characters."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = re.sub(r"\s+", "_", name.strip())
    return name[:max_len]


def _fmt_size(path: Path) -> str:
    mb = path.stat().st_size / (1024 ** 2)
    return f"{mb:.1f} MB"


def _fmt_duration(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}h {m}m {s}s" if h else f"{m}m {s}s"


# ---------------------------------------------------------------------------
# CLI — quick test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m app.services.video_loader <path_or_url>")
        sys.exit(1)

    inp = sys.argv[1]
    print(f"\n[LectureLens] Loading video: {inp}\n")

    try:
        meta = load_video(inp)
        print("\n--- VideoMeta ---")
        print(f"  Title    : {meta.title}")
        print(f"  Source   : {meta.source}")
        print(f"  Path     : {meta.local_path}")
        print(f"  Duration : {meta.duration_str()}")
        if meta.extra:
            print(f"  Uploader : {meta.extra.get('uploader', 'N/A')}")
        print("\n[OK] Video ready for processing.")
    except (ValueError, FileNotFoundError, RuntimeError) as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)