"""Реестр стадий воронки."""

from __future__ import annotations

from pharmproject.pipeline.base import Stage
from pharmproject.stages.stage1_zinc22 import Stage1Zinc22
from pharmproject.stages.stage2_descriptors import Stage2Descriptors
from pharmproject.stages.stage3_admet import Stage3Admet

STAGES: dict[str, type[Stage]] = {
    "stage1": Stage1Zinc22,
    "stage2": Stage2Descriptors,
    "stage3": Stage3Admet,
}


def get_stage_class(name: str) -> type[Stage]:
    if name not in STAGES:
        raise KeyError(f"Неизвестная стадия '{name}'. Доступны: {', '.join(STAGES)}")
    return STAGES[name]
