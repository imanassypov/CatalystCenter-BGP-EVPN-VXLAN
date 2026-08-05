"""REST API and main page for DEFN editor."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template, request

from defn_core.paths import (
    allowed_roots,
    default_project_folder,
    native_pick_folder,
    resolve_project_path,
)
from defn_core.schema import load_schema, ui_schema
from defn_core.service import (
    load_project,
    load_project_from_files,
    save_session,
    validate_project,
)

bp = Blueprint("defn", __name__)


def _store():
    return current_app.config["SESSION_STORE"]


def _session_folder() -> Path | None:
    session = _store().get()
    if not session or session.get("load_mode") == "browser":
        return None
    folder = session.get("project_folder")
    if not folder:
        return None
    return resolve_project_path(folder)


@bp.get("/")
def index():
    return render_template("index.html")


@bp.get("/api/health")
def health():
    default = default_project_folder()
    return jsonify(
        {
            "status": "ok",
            "default_folder": str(default),
            "default_folder_exists": default.is_dir(),
            "session_loaded": _store().loaded,
            "loaded_folder": (_store().get() or {}).get("project_folder"),
        }
    )


@bp.get("/api/schema")
def api_schema():
    schema = load_schema()
    return jsonify({"schema": schema, "ui": ui_schema(schema)})


@bp.get("/api/config")
def api_config():
    default = default_project_folder()
    defn_count = len(list(default.glob("DEFN-*.j2"))) if default.is_dir() else 0
    roots = [str(r) for r in allowed_roots()]
    return jsonify(
        {
            "default_folder": str(default),
            "defn_file_count": defn_count,
            "session_loaded": _store().loaded,
            "loaded_folder": (_store().get() or {}).get("project_folder"),
            "allowed_roots": roots,
            "folder_picker_modes": ["native", "browser", "path"],
        }
    )


@bp.post("/api/browse-folder")
def api_browse_folder():
    """Native macOS folder picker (fills path field). Unavailable inside Linux Docker."""
    picked = native_pick_folder()
    if not picked:
        return jsonify(
            {
                "error": (
                    "Native folder picker unavailable (use Browse in Chrome or paste path)"
                )
            }
        ), 501
    try:
        resolved = resolve_project_path(picked)
        return jsonify({"folder": str(resolved)})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@bp.post("/api/project/load")
def api_load():
    body = request.get_json(silent=True) or {}
    folder = body.get("folder") or str(default_project_folder())
    try:
        root = resolve_project_path(folder)
        session = load_project(root)
        session["project_folder"] = str(root)
        _store().set(session)
        return jsonify(session)
    except (ValueError, FileNotFoundError) as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@bp.post("/api/project/load-files")
def api_load_files():
    body = request.get_json(silent=True) or {}
    files = body.get("files") or {}
    folder_label = body.get("folder_label") or "picked-folder"
    try:
        session = load_project_from_files(files, folder_label)
        _store().set(session)
        return jsonify(session)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@bp.get("/api/session")
def api_get_session():
    session = _store().get()
    if not session:
        return jsonify({"error": "No project loaded"}), 404
    return jsonify(session)


@bp.put("/api/session")
def api_put_session():
    payload = request.get_json(silent=True)
    if not payload or "files" not in payload:
        return jsonify({"error": "Invalid session payload"}), 400
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    _store().set(payload)
    return jsonify({"status": "ok"})


@bp.post("/api/validate")
def api_validate():
    session = _store().get()
    if not session:
        return jsonify({"error": "Load a project before validating"}), 400
    try:
        root = _session_folder()
        issues = validate_project(root, session)
        return jsonify({"issues": issues, "ok": not any(i["level"] == "error" for i in issues)})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@bp.post("/api/save")
def api_save():
    session = _store().get()
    if not session:
        return jsonify({"error": "Load a project before saving"}), 400

    strict = bool(request.json.get("strict")) if request.is_json else False

    try:
        result = save_session(session, strict=strict)
        session["saved_at"] = datetime.now(timezone.utc).isoformat()
        _store().set(session)
        folder = session.get("project_folder", "")
        message = (
            f"Saved {len(result['written'])} file(s) to {folder}."
            if result["written"]
            else f"Rendered {len(result['files'])} file(s) — write back via folder picker."
        )
        return jsonify(
            {
                "status": "ok",
                "written": result["written"],
                "backups": result["backups"],
                "issues": result["issues"],
                "files": result["files"],
                "load_mode": session.get("load_mode", "path"),
                "message": message,
            }
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400
