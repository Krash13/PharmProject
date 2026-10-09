"""Этап 4 — предсказание pIC50 (ChemBERTa)."""

from __future__ import annotations

import heapq
import itertools
from pathlib import Path

import pyarrow.parquet as pq
import structlog

from pharmproject.adapters.chemberta import ChembertaAdapter
from pharmproject.pipeline.base import PipelineContext, Stage, StageOutput
from pharmproject.storage.checkpoint import load_progress, save_progress
from pharmproject.storage.store import STAGE4_SCHEMA, ParquetShardWriter

logger = structlog.get_logger()


class Stage4Chemberta(Stage):
    name = "stage4"

    def __init__(self, resume: bool = False, adapter=None) -> None:
        super().__init__(resume)
        self._adapter = adapter  # для тестов — мок

    def run(self, ctx: PipelineContext) -> StageOutput:
        cfg = ctx.config.stage4
        th = ctx.config.thresholds

        in_dir = _resolve(cfg.input_dir, ctx.data_dir)
        out_dir = _resolve(cfg.output_dir, ctx.data_dir)
        ckpt = _resolve(cfg.checkpoint_path, ctx.data_dir)
        if not ckpt.exists():
            raise FileNotFoundError(
                f"Чекпоинт ChemBERTa не найден: {ckpt}. Запустите scripts/finetune_chemberta.py"
            )
        adapter = self._adapter or ChembertaAdapter(checkpoint_path=str(ckpt), device=cfg.device)

        progress_path = out_dir / "progress.json"
        progress = load_progress(progress_path)

        # Топ-N держим в min-heap (память O(top_n)). NOTE: при --resume пропущенные
        # шарды не перечитываются, поэтому топ-N в возобновлённом прогоне считается
        # только по новым шардам — для корректного топ-N запускайте без --resume.
        heap: list[tuple[float, int, dict]] = []
        seq = itertools.count()
        above_threshold = 0
        failed = 0
        invalid = 0
        skipped = 0
        processed_shards = 0
        input_shards = sorted(in_dir.glob("*.parquet")) if in_dir.exists() else []

        for shard in input_shards:
            if self.resume and progress.get(shard.name) == "done":
                skipped += 1
                continue
            rows = pq.read_table(str(shard)).to_pylist()
            for batch in _batches(rows, cfg.batch_size):
                smiles = [r["smiles"] for r in batch]
                try:
                    pic50s = adapter.predict(smiles)
                except Exception:
                    logger.exception("stage4.predict_failed", n=len(smiles))
                    failed += len(smiles)
                    continue
                for row, p in zip(batch, pic50s):
                    if p is None or p != p:  # None или NaN
                        invalid += 1
                        continue
                    p = float(p)
                    if p >= th.pic50_min:
                        above_threshold += 1
                        heapq.heappush(heap, (p, next(seq), dict(row)))
                        if len(heap) > cfg.top_n:
                            heapq.heappop(heap)
            progress[shard.name] = "done"
            save_progress(progress_path, progress)
            processed_shards += 1

        top = sorted(heap, key=lambda x: x[0], reverse=True)
        writer = ParquetShardWriter(out_dir, cfg.shard_rows, schema=STAGE4_SCHEMA)
        for p, _seq, record in top:
            record["pic50"] = p
            writer.add(record)
        written = writer.close()

        stats = {
            "input_shards": len(input_shards),
            "processed_shards": processed_shards,
            "skipped": skipped,
            "above_threshold": above_threshold,
            "kept": len(top),
            "failed": failed,
            "invalid": invalid,
            "parquet_shards": len(written),
        }
        logger.info("stage4.done", **stats)
        return StageOutput(paths=written, stats=stats)


def _batches(rows, size):
    size = max(1, int(size))
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


def _resolve(path: str, data_dir: Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else data_dir / p
