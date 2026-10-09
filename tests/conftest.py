from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_smi_path() -> Path:
    return FIXTURES / "sample.smi"
