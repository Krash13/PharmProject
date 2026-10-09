from __future__ import annotations

import gzip

from pharmproject.config import Config
from pharmproject.pipeline.base import PipelineContext
from pharmproject.stages.stage1_zinc22 import Stage1Zinc22, iter_records


def test_iter_records_plain(sample_smi_path):
    rows = list(iter_records(sample_smi_path))
    assert len(rows) == 4
    assert rows[0] == ("CCO", "ZINC000000000001")


def test_iter_records_gz(tmp_path, sample_smi_path):
    gz = tmp_path / "sample.smi.gz"
    with gzip.open(gz, "wb") as f:
        f.write(sample_smi_path.read_bytes())
    rows = list(iter_records(gz))
    assert len(rows) == 4
    assert rows[0] == ("CCO", "ZINC000000000001")


def test_stage1_local_file(tmp_path, sample_smi_path):
    cfg = Config(
        data_dir=str(tmp_path / "data"),
        stage1={"tranches": [str(sample_smi_path)], "shard_rows": 2},
    )
    out = Stage1Zinc22(resume=False).run(PipelineContext(config=cfg))

    assert out.stats["parsed_records"] == 4
    assert len(out.paths) == 2  # 2 + 2
    shard_dir = tmp_path / "data" / "raw" / "zinc22" / "shards"
    assert shard_dir.exists()
    assert len(list(shard_dir.glob("*.parquet"))) == 2


def test_stage1_resume_skips(tmp_path, sample_smi_path):
    cfg = Config(
        data_dir=str(tmp_path / "data"),
        stage1={"tranches": [str(sample_smi_path)], "shard_rows": 10},
    )
    ctx = PipelineContext(config=cfg)
    Stage1Zinc22(resume=False).run(ctx)
    out = Stage1Zinc22(resume=True).run(ctx)

    assert out.stats["skipped"] == 1
    assert out.stats["parsed_records"] == 0


def test_stage1_no_sources_raises(tmp_path):
    cfg = Config(data_dir=str(tmp_path / "data"), stage1={"tranches": []})
    try:
        Stage1Zinc22(resume=False).run(PipelineContext(config=cfg))
        assert False, "ожидалась ошибка при отсутствии tranche"
    except RuntimeError as exc:
        assert "tranche" in str(exc)
