"""Раскладка data/."""

from __future__ import annotations

from pathlib import Path


def zinc22_root(data_dir: Path) -> Path:
    return data_dir / "raw" / "zinc22"


def downloads_dir(data_dir: Path) -> Path:
    return zinc22_root(data_dir) / "downloads"


def shards_dir(data_dir: Path) -> Path:
    return zinc22_root(data_dir) / "shards"


def progress_file(data_dir: Path) -> Path:
    return zinc22_root(data_dir) / "progress.json"
