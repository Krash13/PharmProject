"""Загрузка и валидация конфигурации (YAML + Pydantic)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class TargetConfig(BaseModel):
    """Мишень. По умолчанию InhA (туберкулёз)."""

    name: str = "InhA"
    uniprot_id: str | None = "P9WGR1"
    structure_path: str | None = None  # путь к PDB-структуре
    sequence: str | None = None  # или последовательность


class Stage1Config(BaseModel):
    """Настройки этапа 1 — загрузка lead-like из ZINC22."""

    base_url: str = "https://files.docking.org/"
    subset: str = "lead-like"
    # Точечная загрузка: список tranche (полный URL, относительный путь или локальный файл).
    tranches: list[str] = Field(default_factory=list)
    # Манифест (локальный файл или URL) со списком tranche — по одной записи на строку.
    manifest_path: str | None = None
    output_dir: str = "data/raw/zinc22"
    shard_rows: int = 1_000_000
    delimiter: str = " "
    column_order: list[str] = Field(default_factory=lambda: ["smiles", "zinc_id"])
    timeout_s: float = 60.0
    max_retries: int = 5
    retry_wait: float = 1.0


class Stage2Config(BaseModel):
    """Настройки этапа 2 — дескрипторы и фильтры (RDKit, CPU)."""

    input_dir: str = "data/raw/zinc22/shards"
    output_dir: str = "data/intermediate/stage2_filtered"
    shard_rows: int = 1_000_000
    filter_rule: str = "lead-like"  # lead-like | lipinski | none


class ThresholdsConfig(BaseModel):
    """Пороги фильтров этапа 2. Настраиваются при запуске (конфиг + флаги CLI)."""

    mw_min: float = 150.0
    mw_max: float = 350.0
    logp_max: float = 3.5
    rot_bonds_max: int = 7
    hbd_max: int = 5
    hba_max: int = 10
    tpsa_max: float | None = None  # None = не проверяем


class Config(BaseModel):
    data_dir: str = "data"
    target: TargetConfig = Field(default_factory=TargetConfig)
    stage1: Stage1Config = Field(default_factory=Stage1Config)
    stage2: Stage2Config = Field(default_factory=Stage2Config)
    thresholds: ThresholdsConfig = Field(default_factory=ThresholdsConfig)


def load_config(
    path: str | Path | None = None, overrides: dict[str, Any] | None = None
) -> Config:
    """Загружает конфиг из YAML (если задан) и применяет поверх CLI-переопределения."""
    data: dict[str, Any] = {}
    if path is not None:
        p = Path(path)
        if p.exists():
            with p.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
    if overrides:
        data = _deep_merge(data, overrides)
    return Config.model_validate(data)


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
