"""Этап 6 — финальный ADMET (ADMETlab 2.0)."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pyarrow.parquet as pq
import structlog

from pharmproject.adapters.admetlab import AdmetlabAdapter
from pharmproject.chemistry.filters import passes_admet_filters
from pharmproject.pipeline.base import PipelineContext, Stage, StageOutput
from pharmproject.storage.checkpoint import load_progress, save_progress
from pharmproject.storage.store import STAGE6_SCHEMA, ParquetShardWriter

logger = structlog.get_logger()


class Stage6Admetlab(Stage):
    name = "stage6"

    def __init__(self, resume: bool = False, adapter=None) -> None:
        super().__init__(resume)
        self._adapter = adapter  # для тестов — мок

    def run(self, ctx: PipelineContext) -> StageOutput:
        cfg = ctx.config.stage6
        adapter = self._adapter or AdmetlabAdapter(
            base_url=cfg.base_url, timeout=cfg.timeout_s, max_retries=cfg.max_retries
        )

        in_dir = _resolve(cfg.input_dir, ctx.data_dir)
        out_dir = _resolve(cfg.output_dir, ctx.data_dir)
        progress_path = out_dir / "progress.json"
        progress = load_progress(progress_path)

        writer = ParquetShardWriter(out_dir, cfg.shard_rows, schema=STAGE6_SCHEMA)
        counters: Counter[str] = Counter()
        skipped = 0
        processed_shards = 0
        input_shards = sorted(in_dir.glob("*.parquet")) if in_dir.exists() else []

        try:
            for shard in input_shards:
                if self.resume and progress.get(shard.name) == "done":
                    skipped += 1
                    continue
                rows = pq.read_table(str(shard)).to_pylist()
                for batch in _batches(rows, cfg.batch_size):
                    smiles = [r["smiles"] for r in batch]
                    try:
                        preds_list = adapter.predict(smiles)
                    except Exception:
                        logger.exception("stage6.predict_failed", n=len(smiles))
                        counters["failed"] += len(smiles)
                        continue
                    for row, preds in zip(batch, preds_list):
                        if preds is None:
                            counters["failed"] += 1
                            continue
                        if passes_admet_filters(preds, cfg.filters):
                            record = dict(row)
                            record["admetlab"] = json.dumps(preds)
                            writer.add(record)
                            counters["kept"] += 1
                        else:
                            counters["filtered"] += 1
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
        logger.info("stage6.done", **stats)
        return StageOutput(paths=written, stats=stats)


def _batches(rows, size):
    size = max(1, int(size))
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


def _resolve(path: str, data_dir: Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else data_dir / p
