"""
app/routes/api.py
LectureLensAI — REST API Routes
"""

import os
import json
from pathlib import Path
from flask import Blueprint, request, jsonify, send_file, current_app

from ..services.pipeline import start_pipeline, get_job

api_bp = Blueprint("api", __name__)


@api_bp.route("/process", methods=["POST"])
def process():
    """Start the processing pipeline."""
    data = request.get_json(force=True) or {}
    input_data = data.get("input", "").strip()
    demo = data.get("demo", False) or current_app.config.get("DEMO_MODE", False)

    if not input_data and not demo:
        return jsonify({"error": "No input provided"}), 400

    if demo:
        input_data = input_data or "demo"

    job_id = start_pipeline(input_data, demo=demo)
    return jsonify({"job_id": job_id})


@api_bp.route("/status/<job_id>", methods=["GET"])
def status(job_id):
    """Poll job status and progress."""
    job = get_job(job_id)
    if job.get("status") == "not_found":
        return jsonify({"error": "Job not found"}), 404

    return jsonify({
        "status":   job["status"],
        "step":     job.get("step", ""),
        "progress": job.get("progress", 0),
        "error":    job.get("error"),
        "title":    job.get("title", ""),
    })


@api_bp.route("/results/<job_id>", methods=["GET"])
def results(job_id):
    """Return the full notes + flashcards JSON."""
    job = get_job(job_id)
    if job.get("status") == "not_found":
        return jsonify({"error": "Job not found"}), 404
    if job.get("status") == "running":
        return jsonify({"error": "Job not finished yet"}), 202
    if job.get("status") == "error":
        return jsonify({"error": job.get("error", "Unknown error")}), 500

    return jsonify({
        "title":      job.get("title", "Lecture"),
        "notes":      job.get("notes", []),
        "flashcards": job.get("flashcards", []),
        "pdf_ready":  job.get("pdf_path") is not None and Path(job["pdf_path"]).exists(),
        "video_url":  job.get("video_url"),
        "video_type": job.get("video_type"),
    })


@api_bp.route("/export/<job_id>", methods=["GET"])
def export(job_id):
    """Serve the generated PDF for download."""
    job = get_job(job_id)

    if job.get("status") == "not_found":
        return jsonify({"error": "Job not found — please re-process the lecture"}), 404

    if job.get("status") != "done":
        return jsonify({"error": "Job is still processing, please wait"}), 202

    pdf_path = job.get("pdf_path")
    if not pdf_path or not Path(pdf_path).exists():
        return jsonify({"error": "PDF not available — export may have failed"}), 404

    safe_title = job.get("title", "lecture").replace(" ", "_")[:60]
    return send_file(
        pdf_path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"{safe_title}.pdf"
    )



@api_bp.route("/video/<job_id>", methods=["GET"])
def video(job_id):
    """Stream the local video file for the given job."""
    job = get_job(job_id)
    if job.get("status") == "not_found":
        return jsonify({"error": "Job not found"}), 404

    local_path = job.get("_local_path")
    if not local_path or not Path(local_path).exists():
        return jsonify({"error": "Video file not available"}), 404

    return send_file(local_path, mimetype="video/mp4", conditional=True)


@api_bp.route("/chat/<job_id>", methods=["POST"])
def chat(job_id):
    """Answer a question about the lecture using the job's transcript segments."""
    from ..services.chatbot import answer_question
    from ..utils.helpers import sanitize_filename

    job = get_job(job_id)
    if job.get("status") == "not_found":
        return jsonify({"error": "Job not found"}), 404
    if job.get("status") not in ("done",):
        return jsonify({"error": "Job not ready"}), 202

    data = request.get_json(force=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "No message provided"}), 400

    # --- Load transcript segments ---
    # Try disk cache first (segments saved during transcription)
    title = job.get("title", "")
    segments = None

    if title:
        cache_path = Path("data/audio") / f"{sanitize_filename(title)}.json"
        if cache_path.exists():
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    segments = json.load(f)
            except Exception:
                segments = None

    # Fall back to notes bullets as pseudo-segments (demo mode)
    if not segments:
        notes = job.get("notes", [])
        segments = [
            {
                "text": " ".join(n.get("bullets", [])),
                "start": n.get("timestamp", 0),
                "end": n.get("timestamp", 0) + 60,
            }
            for n in notes if n.get("bullets")
        ]

    if not segments:
        return jsonify({"error": "No transcript available for this job"}), 404

    try:
        result = answer_question(job_id, segments, message)
        return jsonify(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
