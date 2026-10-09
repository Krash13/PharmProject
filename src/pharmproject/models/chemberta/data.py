"""Загрузка и подготовка данных BindingDB."""

from __future__ import annotations

import csv
import math
import statistics
from collections import defaultdict
from pathlib import Path

BINDINGDB_URL = "https://www.bindingdb.org/bind/downloads/BindingDB_All.tsv.zip"

# Имена колонок BindingDB TSV (проверить на реальном файле).
COL_SMILES = "Ligand SMILES"
COL_UNIPROT = "UniProt (SwissProt) Primary ID of Target Chain"
COL_IC50 = "IC50 (nM)"
COL_KI = "Ki (nM)"


def download_bindingdb(output_zip: Path) -> Path:
    """Скачивает архив BindingDB (не распаковывает)."""
    import httpx

    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream(
        "GET", BINDINGDB_URL, timeout=60.0, follow_redirects=True, trust_env=False
    ) as resp:
        resp.raise_for_status()
        with output_zip.open("wb") as f:
            for chunk in resp.iter_bytes():
                f.write(chunk)
    return output_zip


def extract_tsv(zip_path: Path, out_dir: Path) -> Path:
    """Распаковывает архив и возвращает путь к TSV."""
    import zipfile

    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        name = z.namelist()[0]
        z.extract(name, out_dir)
        return out_dir / name


def _to_pic50(rec: dict) -> float | None:
    """Конвертирует IC50/Ki (в нМ) в pIC50. Предпочитает IC50, затем Ki."""
    for col in (COL_IC50, COL_KI):
        raw = (rec.get(col) or "").strip()
        if not raw:
            continue
        try:
            value_nm = float(raw)
        except ValueError:
            continue
        if value_nm <= 0:
            continue
        return -math.log10(value_nm * 1e-9)
    return None


def filter_bindingdb_records(records, uniprot_id: str) -> list[tuple[str, float]]:
    """Из строк TSV (dict) оставляет записи нужной мишени: (smiles, pic50)."""
    rows: list[tuple[str, float]] = []
    for rec in records:
        if rec.get(COL_UNIPROT) != uniprot_id:
            continue
        smiles = (rec.get(COL_SMILES) or "").strip()
        if not smiles:
            continue
        pic50 = _to_pic50(rec)
        if pic50 is None:
            continue
        rows.append((smiles, pic50))
    return rows


def filter_bindingdb_for_target(tsv_path: Path, uniprot_id: str) -> list[tuple[str, float]]:
    """Читает TSV и фильтрует по мишени."""
    with tsv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        return filter_bindingdb_records(reader, uniprot_id)


def aggregate_by_smiles(rows: list[tuple[str, float]]) -> list[tuple[str, float]]:
    """Дедуплицирует по SMILES, беря медиану pIC50."""
    groups: dict[str, list[float]] = defaultdict(list)
    for smiles, pic50 in rows:
        groups[smiles].append(pic50)
    return [(s, statistics.median(v)) for s, v in groups.items()]
