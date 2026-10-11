"""Этап 3 — ADMET-фильтрация (ADMET-AI)."""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

import pyarrow.parquet as pq
import structlog

from pharmproject.adapters.admet_ai import AdmetAiAdapter
from pharmproject.chemistry.filters import passes_admet_filters
from pharmproject.pipeline.base import PipelineContext, Stage, StageOutput
from pharmproject.storage.checkpoint import load_progress, save_progress
from pharmproject.storage.store import STAGE3_SCHEMA, ParquetShardWriter

logger = structlog.get_logger()


class Stage3Admet(Stage):
    name = "stage3"

    def __init__(self, resume: bool = False, adapter: AdmetAiAdapter | None = None) -> None:
        super().__init__(resume)
        self._adapter = adapter  # для тестов — мок

    def run(self, ctx: PipelineContext) -> StageOutput:
        cfg = ctx.config.stage3
        adapter = self._adapter or AdmetAiAdapter(device=cfg.device)

        in_dir = _resolve(cfg.input_dir, ctx.data_dir)
        out_dir = _resolve(cfg.output_dir, ctx.data_dir)
        progress_path = out_dir / "progress.json"
        progress = load_progress(progress_path)

        writer = ParquetShardWriter(out_dir, cfg.shard_rows, schema=STAGE3_SCHEMA)
        counters: Counter[str] = Counter()
        skipped = 0
        processed_shards = 0
        input_shards = sorted(in_dir.glob("*.parquet")) if in_dir.exists() else []

        logger.info(
            "stage3.start",
            input_shards=len(input_shards),
            output=str(out_dir),
            device=cfg.device,
            batch_size=cfg.batch_size,
        )

        try:
            for i, shard in enumerate(input_shards, 1):
                if self.resume and progress.get(shard.name) == "done":
                    logger.info("shard.skip", file=shard.name, index=f"{i}/{len(input_shards)}")
                    skipped += 1
                    continue

                logger.info("shard.begin", file=shard.name, index=f"{i}/{len(input_shards)}")
                rows = pq.read_table(str(shard)).to_pylist()
                shard_kept = shard_filtered = shard_failed = 0
                for batch in _batches(rows, cfg.batch_size):
                    smiles = [r["smiles"] for r in batch]
                    try:
                        preds_list = adapter.predict(smiles)
                    except Exception:
                        logger.exception("stage3.predict_failed", n=len(smiles))
                        counters["failed"] += len(smiles)
                        shard_failed += len(smiles)
                        continue
                    for row, preds in zip(batch, preds_list):
                        if preds is None:
                            counters["failed"] += 1
                            shard_failed += 1
                            continue
                        if passes_admet_filters(preds, cfg.filters):
                            record = dict(row)
                            record["admet"] = _serialize_preds(preds)
                            writer.add(record)
                            counters["kept"] += 1
                            shard_kept += 1
                        else:
                            counters["filtered"] += 1
                            shard_filtered += 1

                logger.info(
                    "shard.done",
                    file=shard.name,
                    kept=shard_kept,
                    filtered=shard_filtered,
                    failed=shard_failed,
                )
                progress[shard.name] = "done"
                save_progress(progress_path, progress)
                processed_shards += 1
        finally:
            written = writer.close()

        stats = {
            "input_shards": len(input_shards),
            "processed_shards": processed_shards,
            "skipped": skipped,
            "kept": counters["kept"],
            "filtered": counters["filtered"],
            "failed": counters["failed"],
            "parquet_shards": len(written),
        }
        logger.info("stage3.done", **stats)
        return StageOutput(paths=written, stats=stats)


def _serialize_preds(preds: dict) -> str:
    """Превращает предсказания (в т.ч. numpy-скаляры) в JSON-строку."""
    clean = {}
    for k, v in preds.items():
        if hasattr(v, "item"):
            v = v.item()
        if isinstance(v, float) and math.isnan(v):
            v = None
        clean[k] = v
    return json.dumps(clean)


def _batches(rows, size):
    size = max(1, int(size))
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


def _resolve(path: str, data_dir: Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else data_dir / p
