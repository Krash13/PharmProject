"""Реестр стадий воронки."""

from __future__ import annotations

from pharmproject.pipeline.base import Stage
from pharmproject.stages.stage1_zinc22 import Stage1Zinc22
from pharmproject.stages.stage1_enamine import Stage1Enamine
from pharmproject.stages.stage1_pubchem import Stage1Pubchem
from pharmproject.stages.stage2_descriptors import Stage2Descriptors
from pharmproject.stages.stage3_admet import Stage3Admet
from pharmproject.stages.stage4_chemberta import Stage4Chemberta
from pharmproject.stages.stage5_boltz import Stage5Boltz
from pharmproject.stages.stage6_admetlab import Stage6Admetlab
from pharmproject.stages.stage7_pk import Stage7Pk

STAGES: dict[str, type[Stage]] = {
    "stage1": Stage1Zinc22,
    "stage1_enamine": Stage1Enamine,
    "stage1_pubchem": Stage1Pubchem,
    "stage2": Stage2Descriptors,
    "stage3": Stage3Admet,
    "stage4": Stage4Chemberta,
    "stage5": Stage5Boltz,
    "stage6": Stage6Admetlab,
    "stage7": Stage7Pk,
}


def get_stage_class(name: str) -> type[Stage]:
    if name not in STAGES:
        raise KeyError(f"Неизвестная стадия '{name}'. Доступны: {', '.join(STAGES)}")
    return STAGES[name]
