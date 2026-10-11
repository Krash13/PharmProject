"""Этап 2 (параллельный) — дескрипторы и фильтры на нескольких CPU-ядрах.

В отличие от stage2 (однопоточный), обрабатывает шарды параллельно через
multiprocessing.Pool. Дедупликация по InChIKey выполняется ВНУТРИ каждого шарда
(глобальная кросс-шардовая дедупликация не делается — это осознанный компромисс
ради скорости; при необходимости выносится отдельным шагом).
"""

from __future__ import annotations

import os
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

import pyarrow.parquet as pq
import structlog

from pharmproject.chemistry.descriptors import parse_and_describe
from pharmproject.chemistry.filters import make_filter
from pharmproject.pipeline.base import PipelineContext, Stage, StageOutput
from pharmproject.storage.checkpoint import load_progress, save_progress
from pharmproject.storage.store import STAGE2_SCHEMA, ParquetShardWriter

logger = structlog.get_logger()


def _process_shard(args):
    """Обрабатывает один шард: дескрипторы + фильтр + дедуп внутри шарда.

    Функция модульного уровня — должна быть picklable для multiprocessing.
    """
    shard_path, filter_rule, thresholds = args
    filter_fn = make_filter(filter_rule, thresholds)
    seen: set[str] = set()
    records = []
    stats: Counter = Counter()

    table = pq.read_table(shard_path)
    for row in table.to_pylist():
        result = parse_and_describe(row["smiles"])
        if result is None:
            stats["invalid"] += 1
            continue
        canonical, inchi_key, desc = result
        if inchi_key in seen:
            stats["dup"] += 1
            continue
        if not filter_fn(desc):
            stats["filtered"] += 1
            continue
        seen.add(inchi_key)
        stats["kept"] += 1
        records.append(
            {
                "zinc_id": row["zinc_id"],
                "smiles": canonical,
                "inchi_key": inchi_key,
                "mw": desc.mw,
                "logp": desc.logp,
                "hbd": desc.hbd,
                "hba": desc.hba,
                "tpsa": desc.tpsa,
                "rot_bonds": desc.rot_bonds,
                "qed": desc.qed,
                "tranche": row.get("tranche"),
            }
        )
    return Path(shard_path).name, records, dict(stats)


class Stage2Parallel(Stage):
    name = "stage2_parallel"

    def run(self, ctx: PipelineContext) -> StageOutput:
        cfg = ctx.config.stage2_parallel
        th = ctx.config.thresholds

        in_dir = _resolve(cfg.input_dir, ctx.data_dir)
        out_dir = _resolve(cfg.output_dir, ctx.data_dir)
        progress_path = out_dir / "progress.json"
        progress = load_progress(progress_path)

        input_shards = sorted(in_dir.glob("*.parquet")) if in_dir.exists() else []
        todo = [s for s in input_shards if not (self.resume and progress.get(s.name) == "done")]
        skipped = len(input_shards) - len(todo)

        workers = cfg.workers or os.cpu_count() or 1
        tasks = [(str(s), cfg.filter_rule, th) for s in todo]

        writer = ParquetShardWriter(out_dir, cfg.shard_rows, schema=STAGE2_SCHEMA)
        counters: Counter = Counter()

        logger.info(
            "stage2_parallel.start",
            input_shards=len(input_shards),
            todo=len(todo),
            workers=workers,
            output=str(out_dir),
            filter=cfg.filter_rule,
        )

        try:
            with Pool(processes=workers) as pool:
                for shard_name, records, stats in pool.imap_unordered(_process_shard, tasks):
                    for rec in records:
                        writer.add(rec)
                    counters.update(stats)
                    progress[shard_name] = "done"
                    save_progress(progress_path, progress)
                    logger.info("shard.done", file=shard_name, **stats)
        finally:
            written = writer.close()

        stats = {
            "input_shards": len(input_shards),
            "processed_shards": len(todo),
            "skipped": skipped,
            "kept": counters["kept"],
            "filtered": counters["filtered"],
            "dup": counters["dup"],
            "invalid": counters["invalid"],
            "parquet_shards": len(written),
        }
        logger.info("stage2_parallel.done", **stats)
        return StageOutput(paths=written, stats=stats)


def _resolve(path: str, data_dir: Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else data_dir / p
