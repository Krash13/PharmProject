from __future__ import annotations

from unittest.mock import patch

from pharmproject.config import Config
from pharmproject.pipeline.base import PipelineContext
from pharmproject.stages.stage1_pubchem import Stage1Pubchem
from pharmproject.storage.store import ZINC22_SCHEMA, read_shards


def test_stage1_pubchem_local_file(tmp_path):
    # PubChem CID-SMILES: "CID\tSMILES" (таб, CID первым)
    src = tmp_path / "cid-smiles.txt"
    src.write_text("12345\tCCO\n67890\tc1ccccc1\n", encoding="utf-8")

    cfg = Config(
        data_dir=str(tmp_path),
        pubchem={"files": [str(src)], "output_dir": "raw/pubchem"},
    )
    out = Stage1Pubchem().run(PipelineContext(config=cfg))

    assert out.stats["parsed_records"] == 2
    table = read_shards(tmp_path / "raw" / "pubchem" / "shards", schema=ZINC22_SCHEMA)
    rows = table.to_pylist()
    assert rows[0]["zinc_id"] == "12345"
    assert rows[0]["smiles"] == "CCO"
    assert rows[1]["zinc_id"] == "67890"
    assert rows[1]["smiles"] == "c1ccccc1"


def test_stage1_pubchem_manifest(tmp_path):
    manifest = tmp_path / "manifest.txt"
    manifest.write_text("CID-SMILES.gz\n", encoding="utf-8")

    captured = []

    def fake_download(url, dest):
        captured.append(url)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("1\tC\n", encoding="utf-8")

    with patch("pharmproject.stages.stage1_pubchem.PubchemClient") as Mock:
        inst = Mock.return_value
        inst.build_url.side_effect = lambda p: (
            "https://ftp.ncbi.nlm.nih.gov/pubchem/Compound/Extras/" + p.lstrip("/")
        )
        inst.download.side_effect = fake_download

        cfg = Config(
            data_dir=str(tmp_path),
            pubchem={"manifest_path": str(manifest), "output_dir": "raw/pubchem"},
        )
        Stage1Pubchem().run(PipelineContext(config=cfg))

    assert captured == ["https://ftp.ncbi.nlm.nih.gov/pubchem/Compound/Extras/CID-SMILES.gz"]
