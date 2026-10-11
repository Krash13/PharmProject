from __future__ import annotations

from pharmproject.config import ThresholdsConfig
from pharmproject.stages.stage2_parallel import _process_shard
from pharmproject.storage.store import ZINC22_SCHEMA, ParquetShardWriter


def test_process_shard(tmp_path):
    shard = tmp_path / "part-00000.parquet"
    w = ParquetShardWriter(tmp_path, 10, schema=ZINC22_SCHEMA)
    w.add({"zinc_id": "1", "smiles": "CC(=O)Oc1ccccc1C(=O)O", "tranche": "t"})  # kept (MW 180)
    w.add({"zinc_id": "2", "smiles": "CCO", "tranche": "t"})  # filtered (MW 46 < 150)
    w.add({"zinc_id": "3", "smiles": "not_a_smiles", "tranche": "t"})  # invalid
    w.close()

    name, records, stats = _process_shard((str(shard), "lead-like", ThresholdsConfig()))

    assert name == "part-00000.parquet"
    assert stats == {"kept": 1, "filtered": 1, "invalid": 1}
    assert len(records) == 1
    assert records[0]["zinc_id"] == "1"
    assert records[0]["smiles"] == "CC(=O)Oc1ccccc1C(=O)O"
    assert records[0]["inchi_key"] != ""
