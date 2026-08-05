"""Flask application factory."""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask

from app.routes import bp
from app.session_store import SessionStore


def create_app() -> Flask:
    app = Flask(__name__)
    root = Path(os.environ.get("DEFN_PROJECT_ROOT", "/data/templates"))
    app.config["PROJECT_ROOT"] = root
    app.config["SESSION_STORE"] = SessionStore()
    app.register_blueprint(bp)
    return app
