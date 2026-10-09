from __future__ import annotations

import pytest

from pharmproject.config import Config
from pharmproject.pipeline.base import PipelineContext
from pharmproject.stages.stage4_chemberta import Stage4Chemberta
from pharmproject.storage.store import (
    STAGE3_SCHEMA,
    STAGE4_SCHEMA,
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
    }


def _make_input(in_dir, rows):
    w = ParquetShardWriter(in_dir, 10, schema=STAGE3_SCHEMA)
    for r in rows:
        w.add(r)
    w.close()


def test_stage4_requires_checkpoint():
    cfg = Config(data_dir=".", stage4={"checkpoint_path": "definitely_nonexistent_xyz"})
    with pytest.raises(FileNotFoundError):
        Stage4Chemberta(adapter=FakeAdapter({})).run(PipelineContext(config=cfg))


def test_stage4_top_n(tmp_path):
    in_dir = tmp_path / "in"
    ckpt = tmp_path / "ckpt"
    ckpt.mkdir(parents=True)
    _make_input(in_dir, [_row("Z1", "CCO"), _row("Z2", "CCN"), _row("Z3", "CCC")])
    adapter = FakeAdapter({"CCO": 8.0, "CCN": 7.0, "CCC": 5.0})

    cfg = Config(
        data_dir=str(tmp_path),
        stage4={
            "input_dir": str(in_dir),
            "output_dir": "out",
            "checkpoint_path": str(ckpt),
            "top_n": 2,
            "batch_size": 3,
        },
    )
    out = Stage4Chemberta(adapter=adapter).run(PipelineContext(config=cfg))

    assert out.stats["kept"] == 2
    assert out.stats["above_threshold"] == 2  # 8.0 и 7.0 >= 6.0; 5.0 отсекается

    table = read_shards(tmp_path / "out", schema=STAGE4_SCHEMA)
    rows = table.to_pylist()
    assert [r["zinc_id"] for r in rows] == ["Z1", "Z2"]  # по убыванию pIC50
    assert [r["pic50"] for r in rows] == [8.0, 7.0]
