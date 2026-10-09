"""Этап 2 — дескрипторы и фильтры (RDKit, CPU)."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pyarrow.parquet as pq
import structlog

from pharmproject.chemistry.descriptors import parse_and_describe
from pharmproject.chemistry.filters import make_filter
from pharmproject.pipeline.base import PipelineContext, Stage, StageOutput
from pharmproject.storage.checkpoint import load_progress, save_progress
from pharmproject.storage.store import STAGE2_SCHEMA, ParquetShardWriter

logger = structlog.get_logger()


class Stage2Descriptors(Stage):
    name = "stage2"

    def run(self, ctx: PipelineContext) -> StageOutput:
        cfg = ctx.config.stage2
        th = ctx.config.thresholds
        filter_fn = make_filter(cfg.filter_rule, th)

        in_dir = _resolve(cfg.input_dir, ctx.data_dir)
        out_dir = _resolve(cfg.output_dir, ctx.data_dir)
        progress_path = out_dir / "progress.json"
        progress = load_progress(progress_path)

        writer = ParquetShardWriter(out_dir, cfg.shard_rows, schema=STAGE2_SCHEMA)
        # Дедуп в памяти корректен в пределах одного прогона. При --resume пропущенные
        # шарды не перечитываются, поэтому глобальный дедуп между прогонами неполный —
        # для dev этого достаточно (для 24 млрд заменим на масштабируемый способ).
        seen: set[str] = set()
        counters: Counter[str] = Counter()
        skipped = 0
        processed_shards = 0
        input_shards = sorted(in_dir.glob("*.parquet")) if in_dir.exists() else []

        try:
            for shard in input_shards:
                if self.resume and progress.get(shard.name) == "done":
                    skipped += 1
                    continue
                table = pq.read_table(str(shard))
                for row in table.to_pylist():
                    record, status = self._process(
                        row["smiles"], row["zinc_id"], row.get("tranche"), filter_fn, seen
                    )
                    counters[status] += 1
                    if record is not None:
                        writer.add(record)
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
            "dup": counters["dup"],
            "invalid": counters["invalid"],
            "parquet_shards": len(written),
        }
        logger.info("stage2.done", **stats)
        return StageOutput(paths=written, stats=stats)

    @staticmethod
    def _process(smiles: str, zinc_id: str, tranche, filter_fn, seen: set[str]):
        result = parse_and_describe(smiles)
        if result is None:
            return None, "invalid"
        canonical, inchi_key, desc = result
        if inchi_key in seen:
            return None, "dup"
        if not filter_fn(desc):
            return None, "filtered"
        seen.add(inchi_key)
        return {
            "zinc_id": zinc_id,
            "smiles": canonical,
            "inchi_key": inchi_key,
            "mw": desc.mw,
            "logp": desc.logp,
            "hbd": desc.hbd,
            "hba": desc.hba,
            "tpsa": desc.tpsa,
            "rot_bonds": desc.rot_bonds,
            "qed": desc.qed,
            "tranche": tranche,
        }, "kept"


def _resolve(path: str, data_dir: Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else data_dir / p
