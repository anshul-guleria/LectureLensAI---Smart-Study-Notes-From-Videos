"""
app.py
LectureLens — Gradio UI
"""

import json
from pathlib import Path

import gradio as gr

from app.services.video_loader import load_video
from app.services.audio import extract_and_transcribe
from app.services.notes import generate_notes
from app.services.flashcards import generate_flashcards
from app.services.pdf_export import export_pdf


# ---------------------------------------------------------------------------
# Pipeline function
# ---------------------------------------------------------------------------

def process_video(input_data):
    """
    Full pipeline:
    video → audio → align → notes → flashcards → pdf
    """

    if not input_data:
        return "No input provided", None, None, None

    try:
        print("[app] Loading video...")
        meta = load_video(input_data)

        print("[app] Transcribing audio...")
        segments = extract_and_transcribe(meta)

        print("[app] Generating notes...")
        notes = generate_notes(segments)

        print("[app] Generating flashcards...")
        flashcards = generate_flashcards(notes)

        print("[app] Exporting PDF...")
        pdf_path = export_pdf(notes, flashcards, title=meta.title)

        # Pretty outputs
        notes_text = _format_notes(notes)
        flashcards_text = _format_flashcards(flashcards)

        return notes_text, flashcards_text, str(pdf_path), "✅ Done"

    except Exception as e:
        return f"❌ Error: {e}", "", "", ""


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _format_notes(notes):
    lines = []
    for n in notes[:20]:  # limit display
        lines.append(f"## {n.get('title','Topic')} ({_fmt_time(n.get('timestamp',0))})")
        for b in n.get("bullets", []):
            lines.append(f"- {b}")
        lines.append(f"TL;DR: {n.get('tldr','')}")
        lines.append("")
    return "\n".join(lines)


def _format_flashcards(cards):
    lines = []
    for c in cards[:30]:
        lines.append(f"Q: {c.get('question')}")
        lines.append(f"A: {c.get('answer')}")
        lines.append("")
    return "\n".join(lines)


def _fmt_time(seconds):
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

with gr.Blocks(title="LectureLens") as app:

    gr.Markdown("# 🎓 LectureLens — Video to Smart Notes")

    with gr.Tab("Upload"):
        input_box = gr.Textbox(
            label="Enter YouTube URL or local video path",
            placeholder="https://youtube.com/... OR data/videos/sample.mp4"
        )
        run_btn = gr.Button("Process Lecture")
        status = gr.Textbox(label="Status")

    with gr.Tab("Notes"):
        notes_output = gr.Markdown()

    with gr.Tab("Flashcards"):
        flashcards_output = gr.Markdown()

    with gr.Tab("Export"):
        pdf_output = gr.File(label="Download PDF")

    # --- action ---
    run_btn.click(
        fn=process_video,
        inputs=input_box,
        outputs=[notes_output, flashcards_output, pdf_output, status]
    )


# ---------------------------------------------------------------------------
# Run app
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.launch()