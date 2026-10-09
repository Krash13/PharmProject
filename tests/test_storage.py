from __future__ import annotations

from pharmproject.storage.store import ParquetShardWriter, read_shards


def test_write_and_read_shards(tmp_path):
    writer = ParquetShardWriter(tmp_path, shard_rows=2)
    for i in range(5):
        writer.add({"zinc_id": f"ZINC{i}", "smiles": "CCO", "tranche": "t.smi"})
    paths = writer.close()

    assert len(paths) == 3  # 2 + 2 + 1
    table = read_shards(tmp_path)
    assert table.num_rows == 5
    assert set(table.column("zinc_id").to_pylist()) == {f"ZINC{i}" for i in range(5)}


def test_read_empty_shards(tmp_path):
    table = read_shards(tmp_path)
    assert table.num_rows == 0
