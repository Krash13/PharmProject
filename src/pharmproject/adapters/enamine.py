"""Адаптер скачивания файлов Enamine REAL (make-on-demand)."""

from __future__ import annotations

from pharmproject.adapters.zinc22 import Zinc22Client


class EnamineClient(Zinc22Client):
    """Скачивает файлы Enamine REAL.

    Механизм идентичен ZINC22: HTTP + докачка (Range) + ретраи.
    """
