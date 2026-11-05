"""The plugin's own HTML templates (statement and annual accounts PDFs)."""

from __future__ import annotations

from pathlib import Path

from flask import render_template_string

_DIR = Path(__file__).parent / "templates"


def render(name: str, **context) -> str:
    """Render templates/<name> with Flask's Jinja environment."""
    return render_template_string((_DIR / name).read_text(encoding="utf-8"), **context)
