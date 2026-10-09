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
    output_dir: str = "raw/zinc22"  # относительно data_dir
    shard_rows: int = 1_000_000
    delimiter: str = " "
    column_order: list[str] = Field(default_factory=lambda: ["smiles", "zinc_id"])
    timeout_s: float = 60.0
    max_retries: int = 5
    retry_wait: float = 1.0


class Stage2Config(BaseModel):
    """Настройки этапа 2 — дескрипторы и фильтры (RDKit, CPU).

    Пути input_dir/output_dir задаются относительно data_dir.
    """

    input_dir: str = "raw/zinc22/shards"
    output_dir: str = "intermediate/stage2_filtered"
    shard_rows: int = 1_000_000
    filter_rule: str = "lead-like"  # lead-like | lipinski | none


class AdmetRule(BaseModel):
    """Правило ADMET-фильтра: свойство + сравнение + порог."""

    property: str
    op: str = "<="  # <= >= < > == !=
    value: float


def _default_admet_rules() -> list[AdmetRule]:
    return [
        AdmetRule(property="hERG", op="<=", value=0.5),
        AdmetRule(property="DILI", op="<=", value=0.5),
        AdmetRule(property="ClinTox", op="<=", value=0.5),
        AdmetRule(property="AMES", op="<=", value=0.5),
        AdmetRule(property="Carcinogens_Lagunin", op="<=", value=0.5),
        AdmetRule(property="CYP3A4_Veith", op="<=", value=0.5),
        AdmetRule(property="CYP2D6_Veith", op="<=", value=0.5),
        AdmetRule(property="PAINS_alert", op="==", value=0.0),
        AdmetRule(property="BRENK_alert", op="==", value=0.0),
        AdmetRule(property="HIA_Hou", op=">=", value=0.5),
    ]


class Stage3Config(BaseModel):
    """Настройки этапа 3 — ADMET-фильтрация (ADMET-AI).

    Пути input_dir/output_dir задаются относительно data_dir.
    """

    input_dir: str = "intermediate/stage2_filtered"
    output_dir: str = "intermediate/stage3_admet"
    shard_rows: int = 1_000_000
    batch_size: int = 1000
    device: str = "cpu"  # cpu | cuda | auto
    filters: list[AdmetRule] = Field(default_factory=_default_admet_rules)


class Stage4Config(BaseModel):
    """Настройки этапа 4 — предсказание pIC50 (ChemBERTa).

    Пути input_dir/output_dir/checkpoint_path задаются относительно data_dir.
    """

    input_dir: str = "intermediate/stage3_admet"
    output_dir: str = "intermediate/stage4_scored"
    checkpoint_path: str = "artifacts/chemberta_InhA"
    model_name: str = "seyonec/ChemBERTa-zinc-base-v1"
    batch_size: int = 128
    shard_rows: int = 1_000_000
    device: str = "cpu"  # cpu | cuda | auto
    top_n: int = 10000


class Stage5Config(BaseModel):
    """Настройки этапа 5 — докинг/аффинность (Boltz).

    Пути input_dir/output_dir задаются относительно data_dir. Boltz запускается
    на Linux-сервере с NVIDIA GPU; на dev-машине используется мок в тестах.
    """

    input_dir: str = "intermediate/stage4_scored"
    output_dir: str = "intermediate/stage5_boltz"
    boltz_command: str = "boltz"  # путь к CLI boltz (на сервере)
    device: str = "cuda"  # cpu | cuda | auto
    batch_size: int = 32  # молекул за один прогон boltz
    shard_rows: int = 1_000_000
    top_n: int = 1000
    binder_threshold: float = 0.5  # affinity_probability_binary >= порог


class ThresholdsConfig(BaseModel):
    """Пороги фильтров этапов 2 и 4. Настраиваются при запуске (конфиг + флаги CLI)."""

    mw_min: float = 150.0
    mw_max: float = 350.0
    logp_max: float = 3.5
    rot_bonds_max: int = 7
    hbd_max: int = 5
    hba_max: int = 10
    tpsa_max: float | None = None  # None = не проверяем
    pic50_min: float = 6.0  # отсечка по pIC50 (этап 4)


class Config(BaseModel):
    data_dir: str = "data"
    target: TargetConfig = Field(default_factory=TargetConfig)
    stage1: Stage1Config = Field(default_factory=Stage1Config)
    stage2: Stage2Config = Field(default_factory=Stage2Config)
    stage3: Stage3Config = Field(default_factory=Stage3Config)
    stage4: Stage4Config = Field(default_factory=Stage4Config)
    stage5: Stage5Config = Field(default_factory=Stage5Config)
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
