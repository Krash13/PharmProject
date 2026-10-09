"""Этап 5 — докинг/аффинность (Boltz)."""

from __future__ import annotations

import heapq
import itertools
from pathlib import Path

import pyarrow.parquet as pq
import structlog

from pharmproject.adapters.boltz import BoltzAdapter
from pharmproject.pipeline.base import PipelineContext, Stage, StageOutput
from pharmproject.storage.checkpoint import load_progress, save_progress
from pharmproject.storage.store import STAGE5_SCHEMA, ParquetShardWriter

logger = structlog.get_logger()


class Stage5Boltz(Stage):
    name = "stage5"

    def __init__(self, resume: bool = False, adapter=None) -> None:
        super().__init__(resume)
        self._adapter = adapter  # для тестов — мок

    def run(self, ctx: PipelineContext) -> StageOutput:
        cfg = ctx.config.stage5
        seq = ctx.config.target.sequence
        if not seq:
            raise RuntimeError(
                "Для Boltz нужна последовательность белка: задайте target.sequence в конфиге"
            )

        in_dir = _resolve(cfg.input_dir, ctx.data_dir)
        out_dir = _resolve(cfg.output_dir, ctx.data_dir)
        adapter = self._adapter or BoltzAdapter(
            protein_sequence=seq, boltz_command=cfg.boltz_command, device=cfg.device
        )

        progress_path = out_dir / "progress.json"
        progress = load_progress(progress_path)

        # Топ-N по affinity_pred_value (меньше = сильнее): max-heap через отрицание.
        heap: list[tuple[float, int, dict]] = []
        seq_counter = itertools.count()
        filtered = 0
        invalid = 0
        failed = 0
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
                    affs = adapter.predict(smiles)
                except Exception:
                    logger.exception("stage5.predict_failed", n=len(smiles))
                    failed += len(smiles)
                    continue
                for row, aff in zip(batch, affs):
                    if aff is None:
                        invalid += 1
                        continue
                    prob = aff.get("affinity_probability_binary")
                    pred = aff.get("affinity_pred_value")
                    if prob is None or prob != prob or prob < cfg.binder_threshold:
                        filtered += 1
                        continue
                    if pred is None or pred != pred:  # NaN
                        invalid += 1
                        continue
                    record = dict(row)
                    record["affinity_pred_value"] = float(pred)
                    record["affinity_probability_binary"] = float(prob)
                    heapq.heappush(heap, (-float(pred), next(seq_counter), record))
                    if len(heap) > cfg.top_n:
                        heapq.heappop(heap)
            progress[shard.name] = "done"
            save_progress(progress_path, progress)
            processed_shards += 1

        top = sorted(heap, key=lambda x: x[0], reverse=True)  # -pred по убыванию = pred по возрастанию
        writer = ParquetShardWriter(out_dir, cfg.shard_rows, schema=STAGE5_SCHEMA)
        for _neg_pred, _seq, record in top:
            writer.add(record)
        written = writer.close()

        stats = {
            "input_shards": len(input_shards),
            "processed_shards": processed_shards,
            "skipped": skipped,
            "kept": len(top),
            "filtered": filtered,
            "invalid": invalid,
            "failed": failed,
            "parquet_shards": len(written),
        }
        logger.info("stage5.done", **stats)
        return StageOutput(paths=written, stats=stats)


def _batches(rows, size):
    size = max(1, int(size))
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


def _resolve(path: str, data_dir: Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else data_dir / p
