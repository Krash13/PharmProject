"""Запись и чтение Parquet-шардов."""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

ZINC22_SCHEMA = pa.schema(
    [
        ("zinc_id", pa.string()),
        ("smiles", pa.string()),
        ("tranche", pa.string()),
    ]
)


class ParquetShardWriter:
    """Пишет записи в Parquet-шарды фиксированного размера."""

    def __init__(self, out_dir: Path, shard_rows: int, prefix: str = "part") -> None:
        self.out_dir = out_dir
        self.shard_rows = shard_rows
        self.prefix = prefix
        self._buffer: list[dict] = []
        self._counter = 0
        self.written_paths: list[Path] = []
        out_dir.mkdir(parents=True, exist_ok=True)

    def add(self, record: dict) -> None:
        self._buffer.append(record)
        if len(self._buffer) >= self.shard_rows:
            self.flush()

    def flush(self) -> None:
        if not self._buffer:
            return
        path = self.out_dir / f"{self.prefix}-{self._counter:05d}.parquet"
        table = pa.Table.from_pylist(self._buffer, schema=ZINC22_SCHEMA)
        pq.write_table(table, path)
        self.written_paths.append(path)
        self._counter += 1
        self._buffer.clear()

    def close(self) -> list[Path]:
        self.flush()
        return self.written_paths


def read_shards(shards_dir: Path) -> pa.Table:
    """Читает все Parquet-шарды из директории в одну таблицу (для малых данных/тестов)."""
    files = sorted(shards_dir.glob("*.parquet"))
    if not files:
        return pa.Table.from_batches([], schema=ZINC22_SCHEMA)
    return pq.read_table([str(f) for f in files])
