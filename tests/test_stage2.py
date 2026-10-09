from __future__ import annotations

from pharmproject.config import Config
from pharmproject.pipeline.base import PipelineContext
from pharmproject.stages.stage2_descriptors import Stage2Descriptors
from pharmproject.storage.store import (
    STAGE2_SCHEMA,
    ZINC22_SCHEMA,
    ParquetShardWriter,
    read_shards,
)


def _make_input_shards(in_dir, rows, shard_rows=2):
    writer = ParquetShardWriter(in_dir, shard_rows=shard_rows, schema=ZINC22_SCHEMA)
    for zinc_id, smiles in rows:
        writer.add({"zinc_id": zinc_id, "smiles": smiles, "tranche": "t.smi"})
    writer.close()


def test_stage2_end_to_end(tmp_path):
    in_dir = tmp_path / "in"
    _make_input_shards(
        in_dir,
        [
            ("ZINC1", "CCO"),  # этанол: MW 46 → отфильтрован (MW < 150)
            ("ZINC2", "CC(=O)Oc1ccccc1C(=O)O"),  # аспирин → оставлен
            ("ZINC3", "CC(=O)Nc1ccc(O)cc1"),  # парацетамол → оставлен
            ("ZINC4", "not_a_smiles"),  # битый SMILES → пропущен
        ],
    )

    cfg = Config(
        data_dir=str(tmp_path),
        stage2={"input_dir": str(in_dir), "output_dir": "stage2", "shard_rows": 1},
    )
    out = Stage2Descriptors().run(PipelineContext(config=cfg))

    assert out.stats["kept"] == 2
    assert out.stats["filtered"] == 1
    assert out.stats["invalid"] == 1

    table = read_shards(tmp_path / "stage2", schema=STAGE2_SCHEMA)
    assert set(table.column("zinc_id").to_pylist()) == {"ZINC2", "ZINC3"}
    # у всех оставленных есть InChIKey и дескрипторы
    assert all(table.column("inchi_key").to_pylist())


def test_stage2_dedup(tmp_path):
    in_dir = tmp_path / "in"
    _make_input_shards(
        in_dir,
        [
            ("ZINC1", "CC(=O)Oc1ccccc1C(=O)O"),
            ("ZINC2", "CC(=O)Oc1ccccc1C(=O)O"),  # дубль аспирина
        ],
        shard_rows=1,  # разложить по разным шардам
    )

    cfg = Config(
        data_dir=str(tmp_path),
        stage2={"input_dir": str(in_dir), "output_dir": "stage2"},
    )
    out = Stage2Descriptors().run(PipelineContext(config=cfg))

    assert out.stats["kept"] == 1
    assert out.stats["dup"] == 1


def test_stage2_resume(tmp_path):
    in_dir = tmp_path / "in"
    _make_input_shards(in_dir, [("ZINC1", "CC(=O)Oc1ccccc1C(=O)O")])

    cfg = Config(
        data_dir=str(tmp_path),
        stage2={"input_dir": str(in_dir), "output_dir": "stage2"},
    )
    ctx = PipelineContext(config=cfg)
    Stage2Descriptors().run(ctx)
    out2 = Stage2Descriptors(resume=True).run(ctx)

    assert out2.stats["skipped"] == 1
    assert out2.stats["kept"] == 0


def test_stage2_filter_rule_none(tmp_path):
    in_dir = tmp_path / "in"
    _make_input_shards(
        in_dir,
        [
            ("ZINC1", "CCO"),  # был бы отфильтрован, но rule=none
        ],
    )

    cfg = Config(
        data_dir=str(tmp_path),
        stage2={
            "input_dir": str(in_dir),
            "output_dir": "stage2",
            "filter_rule": "none",
        },
    )
    out = Stage2Descriptors().run(PipelineContext(config=cfg))

    assert out.stats["kept"] == 1
