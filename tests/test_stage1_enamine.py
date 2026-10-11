from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from pharmproject.config import Config
from pharmproject.pipeline.base import PipelineContext
from pharmproject.stages.stage1_enamine import Stage1Enamine
from pharmproject.storage.store import ZINC22_SCHEMA, read_shards


def test_stage1_enamine_local_file(tmp_path):
    src = tmp_path / "real.smi"
    src.write_text("CCO Z1234567890\nCCN(CC)CC Z9876543210\n", encoding="utf-8")

    cfg = Config(
        data_dir=str(tmp_path),
        enamine={"files": [str(src)], "output_dir": "raw/enamine"},
    )
    out = Stage1Enamine().run(PipelineContext(config=cfg))

    assert out.stats["parsed_records"] == 2
    table = read_shards(tmp_path / "raw" / "enamine" / "shards", schema=ZINC22_SCHEMA)
    rows = table.to_pylist()
    assert rows[0]["zinc_id"] == "Z1234567890"
    assert rows[0]["smiles"] == "CCO"
    assert rows[1]["zinc_id"] == "Z9876543210"
    assert rows[1]["smiles"] == "CCN(CC)CC"


def test_stage1_enamine_relative_manifest(tmp_path):
    manifest = tmp_path / "manifest.txt"
    manifest.write_text("real/AA.smi\nreal/AB.smi\n", encoding="utf-8")

    captured = []

    def fake_download(url, dest):
        captured.append(url)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("CCO Z1\n", encoding="utf-8")

    with patch("pharmproject.stages.stage1_enamine.EnamineClient") as Mock:
        inst = Mock.return_value
        inst.build_url.side_effect = lambda p: "https://enamine.net/" + p.lstrip("/")
        inst.download.side_effect = fake_download

        cfg = Config(
            data_dir=str(tmp_path),
            enamine={"manifest_path": str(manifest), "output_dir": "raw/enamine"},
        )
        Stage1Enamine().run(PipelineContext(config=cfg))

    assert captured == [
        "https://enamine.net/real/AA.smi",
        "https://enamine.net/real/AB.smi",
    ]


def test_stage1_enamine_no_sources(tmp_path):
    cfg = Config(data_dir=str(tmp_path), enamine={"output_dir": "raw/enamine"})
    try:
        Stage1Enamine().run(PipelineContext(config=cfg))
    except RuntimeError as e:
        assert "enamine.manifest_path" in str(e)
    else:
        raise AssertionError("expected RuntimeError")
