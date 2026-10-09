"""CLI дообучения ChemBERTa на BindingDB.

Пример:
    python scripts/finetune_chemberta.py --config config/config.yaml --max-samples 500 --epochs 2
"""

from __future__ import annotations

import argparse
from pathlib import Path

from pharmproject.config import load_config
from pharmproject.models.chemberta import data, finetune


def main() -> None:
    p = argparse.ArgumentParser(description="Дообучить ChemBERTa на BindingDB")
    p.add_argument("--config", default="config/config.yaml")
    p.add_argument("--bindingdb-tsv", help="Путь к уже скачанному BindingDB TSV (иначе скачаем)")
    p.add_argument("--max-samples", type=int, default=None, help="Ограничить выборку (dev)")
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--batch-size", type=int, default=16)
    p.add_argument("--device", default="cuda", choices=["cpu", "cuda", "auto"],
                   help="Устройство: cuda для GPU-сервера, cpu для отладки")
    args = p.parse_args()

    cfg = load_config(args.config)
    data_dir = Path(cfg.data_dir)
    uniprot = cfg.target.uniprot_id or "P9WGR1"

    if args.bindingdb_tsv:
        tsv = Path(args.bindingdb_tsv)
    else:
        zip_path = data_dir / "raw" / "bindingdb" / "BindingDB_All.tsv.zip"
        zip_path = data.download_bindingdb(zip_path)
        tsv = data.extract_tsv(zip_path, zip_path.parent)

    rows = data.filter_bindingdb_for_target(tsv, uniprot)
    rows = data.aggregate_by_smiles(rows)
    if args.max_samples:
        rows = rows[: args.max_samples]
    print(f"Выборка: {len(rows)} соединений для мишени {uniprot}")

    out_dir = data_dir / "artifacts" / f"chemberta_{cfg.target.name}"
    final = finetune.fine_tune(
        rows,
        cfg.stage4.model_name,
        out_dir,
        device=args.device,
        epochs=args.epochs,
        batch_size=args.batch_size,
    )
    print(f"Чекпоинт сохранён: {final}")


if __name__ == "__main__":
    main()
