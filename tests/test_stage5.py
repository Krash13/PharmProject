from __future__ import annotations

import pytest

from pharmproject.config import Config
from pharmproject.pipeline.base import PipelineContext
from pharmproject.stages.stage5_boltz import Stage5Boltz
from pharmproject.storage.store import (
    STAGE4_SCHEMA,
    STAGE5_SCHEMA,
    ParquetShardWriter,
    read_shards,
)


class FakeAdapter:
    def __init__(self, mapping):
        self.mapping = mapping

    def predict(self, smiles_list):
        return [self.mapping.get(s) for s in smiles_list]


def _row(zinc_id, smiles):
    return {
        "zinc_id": zinc_id, "smiles": smiles, "inchi_key": "K" + zinc_id,
        "mw": 200.0, "logp": 2.0, "hbd": 0, "hba": 2, "tpsa": 40.0,
        "rot_bonds": 3, "qed": 0.6, "tranche": "t", "admet": '{"hERG": 0.1}',
        "pic50": 7.0,
    }


def _make_input(in_dir, rows):
    w = ParquetShardWriter(in_dir, 10, schema=STAGE4_SCHEMA)
    for r in rows:
        w.add(r)
    w.close()


def test_stage5_requires_sequence():
    cfg = Config(data_dir=".", target={"sequence": None})
    with pytest.raises(RuntimeError):
        Stage5Boltz(adapter=FakeAdapter({})).run(PipelineContext(config=cfg))


def test_stage5_top_n(tmp_path):
    in_dir = tmp_path / "in"
    _make_input(in_dir, [_row("Z1", "CCO"), _row("Z2", "CCN"), _row("Z3", "CCC")])
    # affinity_pred_value меньше = сильнее; prob < 0.5 — не биндер (отсекается)
    adapter = FakeAdapter({
        "CCO": {"affinity_pred_value": -2.0, "affinity_probability_binary": 0.9},
        "CCN": {"affinity_pred_value": -1.0, "affinity_probability_binary": 0.8},
        "CCC": {"affinity_pred_value": -3.0, "affinity_probability_binary": 0.2},  # не биндер
    })

    cfg = Config(
        data_dir=str(tmp_path),
        target={"sequence": "MKTV"},
        stage5={"input_dir": str(in_dir), "output_dir": "out", "top_n": 2, "batch_size": 3},
    )
    out = Stage5Boltz(adapter=adapter).run(PipelineContext(config=cfg))

    assert out.stats["kept"] == 2
    assert out.stats["filtered"] == 1

    table = read_shards(tmp_path / "out", schema=STAGE5_SCHEMA)
    rows = table.to_pylist()
    assert [r["zinc_id"] for r in rows] == ["Z1", "Z2"]  # по возрастанию affinity_pred_value
    assert [r["affinity_pred_value"] for r in rows] == [-2.0, -1.0]
