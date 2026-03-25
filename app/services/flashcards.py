"""
app/services/flashcards.py
LectureLens — Flashcard Generator (Groq LLM)

Input:
  aligned segments OR notes

Output:
  flashcards (Q&A)
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

OUTPUT_DIR = Path("data/flashcards")

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise RuntimeError("GROQ_API_KEY not found in .env")

client = Groq(api_key=api_key)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_flashcards(
    input_data: List[Dict],
    output_dir: Path = OUTPUT_DIR,
    chunk_size: int = 20
) -> List[Dict]:
    """
    Generate flashcards from aligned segments or notes.

    Args:
        input_data: aligned segments OR notes
        output_dir: save location
        chunk_size: batch size for LLM

    Returns:
        List of flashcards
    """

    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_data:
        raise ValueError("No input data provided")

    print(f"[flashcards] Generating from {len(input_data)} items")

    all_cards = []

    for i in range(0, len(input_data), chunk_size):
        chunk = input_data[i:i + chunk_size]

        print(f"[flashcards] Processing chunk {i//chunk_size + 1}")

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
            raise RuntimeError(f"Groq flashcard generation failed: {e}")

        content = response.choices[0].message.content

        try:
            parsed = _parse_response(content)
            all_cards.extend(parsed)
        except Exception:
            print("[flashcards] Failed parsing chunk, skipping...")

    # --- save JSON ---
    json_path = output_dir / "flashcards.json"
    print(f"[flashcards] Saving → {json_path}")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_cards, f, ensure_ascii=False, indent=2)

    return all_cards


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

def _system_prompt() -> str:
    return """
You are an expert teacher.

Generate high-quality flashcards from lecture content.

Rules:
- Focus on concepts, definitions, formulas
- Keep questions clear and concise
- Answers should be short but informative
- Support Hindi, English, Hinglish
- Avoid duplicates

Output MUST be valid JSON list:
[
  {
    "question": "...",
    "answer": "...",
    "timestamp": float,
    "source": "spoken"
  }
]
"""


def _build_prompt(chunk: List[Dict]) -> str:
    lines = []

    for item in chunk:
        timestamp = item.get("timestamp", item.get("start", 0.0))

        # support both aligned + notes
        if "spoken_text" in item:
            text = item["spoken_text"]
        elif "text" in item:
            text = item["text"]
        elif "bullets" in item:
            text = " ".join(item["bullets"])
        else:
            text = ""

        lines.append(f"[{timestamp:.2f}] {text}")

    return "Lecture content:\n\n" + "\n".join(lines)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def _parse_response(content: str) -> List[Dict]:
    try:
        return json.loads(content)
    except Exception:
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
        print("Usage: python -m app.services.flashcards <input_json>")
        sys.exit(1)

    input_path = Path(sys.argv[1])

    if not input_path.exists():
        print(f"[ERROR] File not found: {input_path}")
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print("\n[LectureLens] Generating Flashcards\n")

    try:
        cards = generate_flashcards(data)

        print("\n--- SAMPLE ---")
        for c in cards[:5]:
            print(c)

        print(f"\n[OK] Flashcards generated: {len(cards)}")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)