"""Адаптер скачивания файлов PubChem."""

from __future__ import annotations

from pharmproject.adapters.zinc22 import Zinc22Client


class PubchemClient(Zinc22Client):
    """Скачивает файлы PubChem (тот же HTTP-механизм с докачкой, что и ZINC22)."""
