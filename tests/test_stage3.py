from __future__ import annotations

import json

from pharmproject.config import Config
from pharmproject.pipeline.base import PipelineContext
from pharmproject.stages.stage3_admet import Stage3Admet
from pharmproject.storage.store import (
    STAGE2_SCHEMA,
    STAGE3_SCHEMA,
    ParquetShardWriter,
    read_shards,
)

PASS = {
    "hERG": 0.1, "DILI": 0.1, "ClinTox": 0.1, "AMES": 0.1,
    "Carcinogens_Lagunin": 0.1, "CYP3A4_Veith": 0.1, "CYP2D6_Veith": 0.1,
    "PAINS_alert": 0.0, "BRENK_alert": 0.0, "HIA_Hou": 0.8,
}
FAIL = {**PASS, "hERG": 0.9}  # высокая кардиотоксичность


class FakeAdapter:
    """Мок адаптера: возвращает список словарей, выровненный по входу."""

    def __init__(self, mapping):
        self.mapping = mapping

    def predict(self, smiles_list):
        return [self.mapping.get(s) for s in smiles_list]


def _row(zinc_id, smiles):
    return {
        "zinc_id": zinc_id, "smiles": smiles, "inchi_key": "K" + zinc_id,
        "mw": 200.0, "logp": 2.0, "hbd": 0, "hba": 2, "tpsa": 40.0,
        "rot_bonds": 3, "qed": 0.6, "tranche": "t",
    }


def _make_input(in_dir, rows):
    w = ParquetShardWriter(in_dir, 10, schema=STAGE2_SCHEMA)
    for r in rows:
        w.add(r)
    w.close()


def test_stage3_end_to_end(tmp_path):
    in_dir = tmp_path / "in"
    _make_input(in_dir, [_row("Z1", "CCO"), _row("Z2", "CCN")])
    adapter = FakeAdapter({"CCO": PASS, "CCN": FAIL})

    cfg = Config(
        data_dir=str(tmp_path),
        stage3={"input_dir": str(in_dir), "output_dir": "stage3", "batch_size": 2},
    )
    out = Stage3Admet(adapter=adapter).run(PipelineContext(config=cfg))

    assert out.stats["kept"] == 1
    assert out.stats["filtered"] == 1
    assert out.stats["failed"] == 0

    table = read_shards(tmp_path / "stage3", schema=STAGE3_SCHEMA)
    assert set(table.column("zinc_id").to_pylist()) == {"Z1"}
    admet = json.loads(table.column("admet").to_pylist()[0])
    assert admet["hERG"] == 0.1


def test_stage3_resume(tmp_path):
    in_dir = tmp_path / "in"
    _make_input(in_dir, [_row("Z1", "CCO")])
    adapter = FakeAdapter({"CCO": PASS})

    cfg = Config(
        data_dir=str(tmp_path),
        stage3={"input_dir": str(in_dir), "output_dir": "stage3"},
    )
    ctx = PipelineContext(config=cfg)
    Stage3Admet(adapter=adapter).run(ctx)
    out2 = Stage3Admet(adapter=adapter, resume=True).run(ctx)

    assert out2.stats["skipped"] == 1
    assert out2.stats["kept"] == 0


def test_stage3_failed_when_prediction_missing(tmp_path):
    in_dir = tmp_path / "in"
    _make_input(in_dir, [_row("Z1", "CCO")])
    adapter = FakeAdapter({})  # предсказания нет → None

    cfg = Config(
        data_dir=str(tmp_path),
        stage3={"input_dir": str(in_dir), "output_dir": "stage3"},
    )
    out = Stage3Admet(adapter=adapter).run(PipelineContext(config=cfg))

    assert out.stats["failed"] == 1
    assert out.stats["kept"] == 0
