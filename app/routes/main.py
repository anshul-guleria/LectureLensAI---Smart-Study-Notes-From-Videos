"""
app/routes/main.py
LectureLensAI — HTML Page Routes
"""

from flask import Blueprint, render_template

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    return render_template("index.html")


@main_bp.route("/results/<job_id>")
def results(job_id):
    return render_template("results.html", job_id=job_id)
