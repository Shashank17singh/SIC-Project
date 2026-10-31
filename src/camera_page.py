"""
Builds the self-contained page that runs the camera and pose detection in the
browser. The exercise rules are embedded as JSON, so exercise_rules.py stays
the single place thresholds are defined.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from src.exercise_rules import EXERCISES

WEB_DIR = Path(__file__).parent / "web"
SIDES = ["LEFT", "RIGHT"]


def build_config(exercise_labels: dict[str, str]) -> dict:
    """Collects every exercise spec, for both sides, in the shape camera.js reads."""
    specs = {
        key: {side: asdict(EXERCISES[key](side)) for side in SIDES}
        for key in exercise_labels
    }
    return {"exercises": exercise_labels, "sides": SIDES, "specs": specs}


def embed_json(value: object) -> str:
    """Serializes a value for a <script> tag. Escaped so no text can close the tag."""
    return json.dumps(value).replace("</", "<\\/")


def build_page(exercise_labels: dict[str, str]) -> str:
    """Returns the full HTML page, with its styles and scripts inlined."""
    page = (WEB_DIR / "page.html").read_text(encoding="utf-8")
    worker = (WEB_DIR / "pose_worker.js").read_text(encoding="utf-8")
    replacements = {
        "/*__CSS__*/": (WEB_DIR / "camera.css").read_text(encoding="utf-8"),
        "/*__CONFIG__*/null": embed_json(build_config(exercise_labels)),
        "/*__WORKER__*/null": embed_json(worker),
        "/*__FORM_LOGIC__*/": (WEB_DIR / "form_logic.js").read_text(encoding="utf-8"),
        "/*__CAMERA__*/": (WEB_DIR / "camera.js").read_text(encoding="utf-8"),
    }
    for marker, content in replacements.items():
        page = page.replace(marker, content)
    return page
