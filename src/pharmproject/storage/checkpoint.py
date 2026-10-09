"""Чекпоинты прогресса (JSON)."""

from __future__ import annotations

import json
from pathlib import Path


def load_progress(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_progress(path: Path, progress: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(progress, indent=2, ensure_ascii=False), encoding="utf-8")
