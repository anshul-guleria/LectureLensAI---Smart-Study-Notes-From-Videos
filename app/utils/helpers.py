"""
app/utils/helpers.py
LectureLensAI — Shared Utility Functions
"""

import re


def sanitize_filename(name: str, max_len: int = 80) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = re.sub(r"\s+", "_", name.strip())
    return name[:max_len]


def fmt_time(seconds: float) -> str:
    """Convert seconds to MM:SS."""
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def fmt_duration(seconds: float) -> str:
    """Convert seconds to human-readable Xh Xm Xs."""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}h {m}m {s}s" if h else f"{m}m {s}s"
