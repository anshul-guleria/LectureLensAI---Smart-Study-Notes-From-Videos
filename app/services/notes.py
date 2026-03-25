"""
app/services/notes.py
LectureLens — Notes Generator (Groq LLM)

Input:
  aligned segments

Output:
  structured notes
"""

import os
import json
from pathlib import Path
from typing import List, Dict

from groq import Groq
from dotenv import load_dotenv


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

OUTPUT_DIR = Path("data/notes")

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise RuntimeError("GROQ_API_KEY not found in .env")

client = Groq(api_key=api_key)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_notes(
    aligned_segments: List[Dict],
    output_dir: Path = OUTPUT_DIR,
    chunk_size: int = 20
) -> List[Dict]:
    """
    Generate structured notes using Groq LLM.

    Args:
        aligned_segments: output of aligner
        output_dir: where to save notes
        chunk_size: segments per LLM call

    Returns:
        List of notes
    """

    output_dir.mkdir(parents=True, exist_ok=True)

    if not aligned_segments:
        raise ValueError("No segments provided")

    print(f"[notes] Generating notes from {len(aligned_segments)} segments")

    all_notes = []

    # --- chunk input (avoid token limits) ---
    for i in range(0, len(aligned_segments), chunk_size):
        chunk = aligned_segments[i:i + chunk_size]

        print(f"[notes] Processing chunk {i//chunk_size + 1}")

        prompt = _build_prompt(chunk)

        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": _system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
        except Exception as e:
            raise RuntimeError(f"Groq notes generation failed: {e}")

        content = response.choices[0].message.content

        try:
            parsed = _parse_response(content)
        except Exception as e:
            print("[notes] Failed parsing chunk, skipping...")
            continue
        all_notes.extend(parsed)

    # --- save JSON ---
    json_path = output_dir / "notes.json"
    print(f"[notes] Saving notes → {json_path}")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_notes, f, ensure_ascii=False, indent=2)

    return all_notes


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def _system_prompt() -> str:
    return """
You are an expert teacher.

Convert lecture transcript into structured study notes.

Rules:
- Keep it concise and clear
- Use bullet points
- Extract key concepts, definitions, formulas
- Preserve Hindi, English, Hinglish naturally
- Add a short TL;DR

Output MUST be valid JSON list:
[
  {
    "timestamp": float,
    "title": "...",
    "bullets": ["...", "..."],
    "tldr": "..."
  }
]
"""


def _build_prompt(chunk: List[Dict]) -> str:
    text_blocks = []

    for seg in chunk:
        timestamp = seg.get("timestamp", seg.get("start", 0.0))
        text = seg.get("spoken_text", seg.get("text", ""))

        text_blocks.append(
            f"[{timestamp:.2f}] {text}"
        )

    return "Lecture transcript:\n\n" + "\n".join(text_blocks)


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------

def _parse_response(content: str) -> List[Dict]:
    """
    Parse LLM JSON safely.
    """
    try:
        return json.loads(content)
    except Exception:
        # fallback: try to extract JSON block
        import re
        match = re.search(r"\[.*\]", content, re.DOTALL)
        if match:
            return json.loads(match.group())
        else:
            raise RuntimeError("Failed to parse LLM response")


# ---------------------------------------------------------------------------
# CLI test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m app.services.notes <aligned_json>")
        sys.exit(1)

    input_path = Path(sys.argv[1])

    if not input_path.exists():
        print(f"[ERROR] File not found: {input_path}")
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        aligned = json.load(f)

    print("\n[LectureLens] Generating Notes\n")

    try:
        notes = generate_notes(aligned)

        print("\n--- SAMPLE ---")
        for n in notes[:3]:
            print(n)

        print(f"\n[OK] Notes generated: {len(notes)}")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)