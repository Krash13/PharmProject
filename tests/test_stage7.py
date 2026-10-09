from __future__ import annotations

import json

import numpy as np

from pharmproject.config import Config
from pharmproject.pipeline.base import PipelineContext
from pharmproject.pk import compartmental as real_pk
from pharmproject.stages.stage7_pk import Stage7Pk
from pharmproject.storage.store import (
    STAGE6_SCHEMA,
    STAGE7_SCHEMA,
    ParquetShardWriter,
    read_shards,
)


class FakePkBackend:
    """Реальный расчёт микроконстант + фейковая PyPharm-модель."""

    def compute_microconstants(self, cl, vss, fu, vc, qfast, qslow):
        return real_pk.compute_microconstants(cl, vss, fu, vc, qfast, qslow)

    def build_model(self, p):
        return "fake_model"

    def simulate(self, model, max_time, dose):
        return [0.0, 1.0, 2.0], [[0.0, 5.0, 3.0], [0.0, 1.0, 1.0], [0.0, 0.5, 0.5]]

    def make_single_dose_response(self, model, max_time):
        return lambda t: np.ones_like(t)


class FakeOptimizer:
    def optimize(self, f, x_min, x_max):
        return {"x": [42.0, 8.0], "f": 0.0, "iterations": 1}


def _row(zinc_id, smiles):
    return {
        "zinc_id": zinc_id, "smiles": smiles, "inchi_key": "K" + zinc_id,
        "mw": 200.0, "logp": 2.0, "hbd": 0, "hba": 2, "tpsa": 40.0,
        "rot_bonds": 3, "qed": 0.6, "tranche": "t", "admet": '{"hERG": 0.1}',
        "pic50": 7.0, "affinity_pred_value": -1.0, "affinity_probability_binary": 0.9,
        "admetlab": '{"CL": "5.0", "VDss": "2.0", "Fu": "50%"}',
    }


def _make_input(in_dir, rows):
    w = ParquetShardWriter(in_dir, 10, schema=STAGE6_SCHEMA)
    for r in rows:
        w.add(r)
    w.close()


def test_stage7_end_to_end(tmp_path):
    in_dir = tmp_path / "in"
    _make_input(in_dir, [_row("Z1", "CCO")])

    cfg = Config(
        data_dir=str(tmp_path),
        stage7={"input_dir": str(in_dir), "output_dir": "out", "optimize_dosing": True},
    )
    out = Stage7Pk(pk_backend=FakePkBackend(), optimizer=FakeOptimizer()).run(
        PipelineContext(config=cfg)
    )

    assert out.stats["kept"] == 1

    table = read_shards(tmp_path / "out", schema=STAGE7_SCHEMA)
    row = table.to_pylist()[0]
    pk_params = json.loads(row["pk_params"])
    assert pk_params["fu"] == pytest.approx(0.5)
    assert "kel" in pk_params
    assert row["pk_dose"] == 42.0
    assert row["pk_tau"] == 8.0
    curve = json.loads(row["pk_curve"])
    assert curve["t"] == [0.0, 1.0, 2.0]
