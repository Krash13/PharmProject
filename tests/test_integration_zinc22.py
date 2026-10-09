"""Интеграционный тест: реальная загрузка из ZINC.

Запуск: pytest -m integration
URL можно переопределить переменной окружения ZINC_TEST_URL
(например, указать конкретный маленький .smi.gz tranche на files.docking.org).
По умолчанию проверяется, что хост docking.org отвечает и что-то отдаёт.
"""

from __future__ import annotations

import os

import pytest

from pharmproject.adapters.zinc22 import Zinc22Client

pytestmark = pytest.mark.integration

DEFAULT_URL = os.environ.get("ZINC_TEST_URL", "https://zinc22.docking.org/")


def test_download_something_real(tmp_path):
    client = Zinc22Client(timeout=30.0, max_retries=2, retry_wait=1.0)
    dest = tmp_path / "probe"
    result = client.download(DEFAULT_URL, dest)

    assert result.bytes > 0
    assert dest.stat().st_size > 0
