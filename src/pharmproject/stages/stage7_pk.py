"""Этап 7 — фармакокинетическое моделирование (PyPharm + KrasheMit)."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pyarrow.parquet as pq
import structlog

from pharmproject.adapters.krashemit import IcoOptimizer
from pharmproject.pipeline.base import PipelineContext, Stage, StageOutput
from pharmproject.pk import compartmental as pk
from pharmproject.pk.dosing import dosing_objective
from pharmproject.storage.checkpoint import load_progress, save_progress
from pharmproject.storage.store import STAGE7_SCHEMA, ParquetShardWriter

logger = structlog.get_logger()


class Stage7Pk(Stage):
    name = "stage7"

    def __init__(self, resume: bool = False, pk_backend=None, optimizer=None) -> None:
        super().__init__(resume)
        self._pk = pk_backend or pk
        self._optimizer = optimizer  # None → IcoOptimizer (лениво)

    def run(self, ctx: PipelineContext) -> StageOutput:
        cfg = ctx.config.stage7
        in_dir = _resolve(cfg.input_dir, ctx.data_dir)
        out_dir = _resolve(cfg.output_dir, ctx.data_dir)
        progress_path = out_dir / "progress.json"
        progress = load_progress(progress_path)

        optimizer = self._optimizer or IcoOptimizer(tmax=cfg.ico_tmax)
        writer = ParquetShardWriter(out_dir, cfg.shard_rows, schema=STAGE7_SCHEMA)
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
                for row in rows:
                    record = self._process_row(row, cfg, optimizer)
                    if record is None:
                        counters["invalid"] += 1
                        continue
                    writer.add(record)
                    counters["kept"] += 1
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
            "invalid": counters["invalid"],
            "parquet_shards": len(written),
        }
        logger.info("stage7.done", **stats)
        return StageOutput(paths=written, stats=stats)

    def _process_row(self, row: dict, cfg, optimizer):
        preds = json.loads(row.get("admetlab") or "{}")
        cl, vss, fu = _extract_pk_input(preds, cfg)
        if cl is None or vss is None or fu is None:
            return None

        p = self._pk.compute_microconstants(cl, vss, fu, cfg.vc, cfg.qfast, cfg.qslow)
        model = self._pk.build_model(p)
        t, y = self._pk.simulate(model, cfg.max_time, cfg.dose)

        record = dict(row)
        record["pk_params"] = json.dumps(pk.pk_params_to_dict(p))
        record["pk_curve"] = json.dumps({"t": t, "c": y[0]})
        record["pk_dose"] = None
        record["pk_tau"] = None

        if cfg.optimize_dosing:
            single = self._pk.make_single_dose_response(model, cfg.max_time)
            obj = lambda x: dosing_objective(x, single, cfg.cmin, cfg.cmax, cfg.horizon)
            res = optimizer.optimize(obj, [cfg.dose_min, cfg.tau_min], [cfg.dose_max, cfg.tau_max])
            record["pk_dose"] = float(res["x"][0])
            record["pk_tau"] = float(res["x"][1])

        return record


def _extract_pk_input(preds: dict, cfg):
    """Достаёт CL (л/ч), Vss (л), fu (доля) из предсказаний ADMETlab.

    Предполагаемые единицы ADMETlab: CL — мл/мин/кг, VDss — л/кг, Fu — %.
    """
    cl = preds.get(cfg.cl_column)
    vss = preds.get(cfg.vss_column)
    fu = preds.get(cfg.fu_column)
    if cl is None or vss is None or fu is None:
        return None, None, None
    try:
        fu_frac = _as_fraction(fu)
        cl_lh = float(cl) * 60.0 / 1000.0 * cfg.body_weight_kg  # мл/мин/кг → л/ч
        vss_l = float(vss) * cfg.body_weight_kg  # л/кг → л
    except (TypeError, ValueError):
        return None, None, None
    if cl_lh <= 0 or vss_l <= 0 or not (0.0 < fu_frac <= 1.0):
        return None, None, None
    return cl_lh, vss_l, fu_frac


def _as_fraction(v) -> float:
    s = str(v).strip()
    if s.endswith("%"):
        return float(s[:-1]) / 100.0
    x = float(s)
    return x / 100.0 if x > 1.0 else x


def _resolve(path: str, data_dir: Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else data_dir / p
