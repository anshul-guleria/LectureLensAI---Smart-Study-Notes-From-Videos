"""
app/__init__.py
LectureLensAI — Flask App Factory
"""

from flask import Flask
from .config import config


def create_app(config_name="default"):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Ensure data directories exist
    for key in ["DATA_DIR", "CACHE_DIR", "AUDIO_DIR", "VIDEO_DIR",
                "NOTES_DIR", "FLASHCARDS_DIR", "EXPORTS_DIR"]:
        app.config[key].mkdir(parents=True, exist_ok=True)

    # Register blueprints
    from .routes.main import main_bp
    from .routes.api import api_bp
 
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    return app
