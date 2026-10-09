from __future__ import annotations

import json

from pharmproject.config import Config
from pharmproject.pipeline.base import PipelineContext
from pharmproject.stages.stage6_admetlab import Stage6Admetlab
from pharmproject.storage.store import (
    STAGE5_SCHEMA,
    STAGE6_SCHEMA,
    ParquetShardWriter,
    read_shards,
)

PASS = {
    "hERG": 0.1, "H-HT": 0.1, "DILI": 0.1, "Ames": 0.1,
    "CYP3A4-inh": 0.1, "CYP2D6-inh": 0.1, "PAINS": 0.0,
    "Lipinski": "Accepted", "Pfizer": "Accepted", "GSK": "Accepted",
}
FAIL = {**PASS, "hERG": 0.9}  # высокая кардиотоксичность


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
        "pic50": 7.0, "affinity_pred_value": -1.0, "affinity_probability_binary": 0.9,
    }


def _make_input(in_dir, rows):
    w = ParquetShardWriter(in_dir, 10, schema=STAGE5_SCHEMA)
    for r in rows:
        w.add(r)
    w.close()


def test_stage6_end_to_end(tmp_path):
    in_dir = tmp_path / "in"
    _make_input(in_dir, [_row("Z1", "CCO"), _row("Z2", "CCN")])
    adapter = FakeAdapter({"CCO": PASS, "CCN": FAIL})

    cfg = Config(
        data_dir=str(tmp_path),
        stage6={"input_dir": str(in_dir), "output_dir": "out", "batch_size": 2},
    )
    out = Stage6Admetlab(adapter=adapter).run(PipelineContext(config=cfg))

    assert out.stats["kept"] == 1
    assert out.stats["filtered"] == 1

    table = read_shards(tmp_path / "out", schema=STAGE6_SCHEMA)
    assert set(table.column("zinc_id").to_pylist()) == {"Z1"}
    admetlab = json.loads(table.column("admetlab").to_pylist()[0])
    assert admetlab["hERG"] == 0.1
    assert admetlab["Lipinski"] == "Accepted"
