"""Адаптер Boltz (предсказание комплекса белок–лиганд и аффинности).

Boltz запускается на Linux-сервере с NVIDIA GPU. На dev-машине используется мок.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml


def build_boltz_yaml(
    protein_sequence: str, smiles: str, protein_id: str = "A", ligand_id: str = "B"
) -> str:
    """Собирает YAML-вход для Boltz: белок (последовательность) + лиганд (SMILES)."""
    doc = {
        "version": 1,
        "sequences": [
            {"protein": {"id": protein_id, "sequence": protein_sequence}},
            {"ligand": {"id": ligand_id, "smiles": smiles}},
        ],
    }
    return yaml.safe_dump(doc, sort_keys=False)


def parse_affinity(data: dict) -> dict | None:
    """Извлекает аффинность из результата Boltz (JSON-объект).

    Boltz-2 отдаёт affinity_pred_value (log10(IC50) в мкМ; меньше = сильнее)
    и affinity_probability_binary (вероятность «это биндер», 0..1).
    """
    pred = data.get("affinity_pred_value")
    prob = data.get("affinity_probability_binary")
    if pred is None and prob is None:
        return None
    return {
        "affinity_pred_value": float(pred) if pred is not None else None,
        "affinity_probability_binary": float(prob) if prob is not None else None,
    }


class BoltzAdapter:
    """Запускает Boltz через CLI и возвращает аффинность для списка SMILES."""

    def __init__(
        self, protein_sequence: str, boltz_command: str = "boltz", device: str = "cuda"
    ) -> None:
        self.protein_sequence = protein_sequence
        self.boltz_command = boltz_command
        self.device = device

    def predict(self, smiles_list: list[str]) -> list[dict | None]:
        """Предсказывает аффинность для списка SMILES (выровнено по входу).

        Внимание: формат входных/выходных файлов Boltz проверяется на GPU-сервере
        (на dev-машине Boltz не запускается, стадия тестируется моком).
        """
        import json
        import subprocess
        import tempfile

        work = Path(tempfile.mkdtemp(prefix="boltz_"))
        inputs_dir = work / "inputs"
        inputs_dir.mkdir(parents=True)
        for i, s in enumerate(smiles_list):
            (inputs_dir / f"{i:05d}.yaml").write_text(
                build_boltz_yaml(self.protein_sequence, s), encoding="utf-8"
            )

        out_dir = work / "out"
        cmd = [self.boltz_command, "predict", str(inputs_dir), "--out_dir", str(out_dir)]
        env = dict(os.environ)
        if self.device == "cpu":
            env["CUDA_VISIBLE_DEVICES"] = ""
        subprocess.run(cmd, check=True, env=env)

        # Сопоставляем результаты обратно с входными SMILES (best-effort, проверить на сервере).
        results: list[dict | None] = [None] * len(smiles_list)
        for f in sorted(out_dir.rglob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            aff = parse_affinity(data)
            if aff is None:
                continue
            idx = _index_from_stem(f.stem)
            if idx is not None and 0 <= idx < len(results):
                results[idx] = aff
        return results


def _index_from_stem(stem: str) -> int | None:
    """Из имени файла вида '00000_...' извлекает индекс входной молекулы."""
    digits = ""
    for ch in stem:
        if ch.isdigit():
            digits += ch
        else:
            break
    return int(digits) if digits else None
