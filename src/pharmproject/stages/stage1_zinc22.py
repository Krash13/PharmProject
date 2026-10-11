"""Этап 1 — загрузка lead-like подмножества ZINC22.

Скачивает tranche-файлы (SMILES, .smi/.smi.gz), парсит их и пишет в Parquet-шарды.
Канонизация SMILES и расчёт InChIKey — на этапе 2.
"""

from __future__ import annotations

import gzip
from pathlib import Path
from urllib.parse import urlparse

import httpx
import structlog

from pharmproject.adapters.zinc22 import Zinc22Client
from pharmproject.pipeline.base import PipelineContext, Stage, StageOutput
from pharmproject.storage.checkpoint import load_progress, save_progress
from pharmproject.storage.paths import downloads_dir, progress_file, shards_dir
from pharmproject.storage.store import ParquetShardWriter

logger = structlog.get_logger()


class Stage1Zinc22(Stage):
    name = "stage1"

    def run(self, ctx: PipelineContext) -> StageOutput:
        cfg = ctx.config.stage1
        client = Zinc22Client(
            base_url=cfg.base_url,
            timeout=cfg.timeout_s,
            max_retries=cfg.max_retries,
            retry_wait=cfg.retry_wait,
        )
        sources = self._resolve_sources(cfg)

        dl_dir = downloads_dir(ctx.data_dir)
        shard_dir = shards_dir(ctx.data_dir)
        progress_path = progress_file(ctx.data_dir)
        progress = load_progress(progress_path)

        writer = ParquetShardWriter(shard_dir, cfg.shard_rows)
        downloaded_files = 0
        parsed_records = 0
        skipped = 0

        try:
            for source in sources:
                if source.startswith(("http://", "https://")):
                    url = source
                elif Path(source).exists():
                    url = None  # локальный файл
                else:
                    url = client.build_url(source)  # относительный путь -> base_url + path

                key = _source_key(url or source)
                if self.resume and progress.get(key) == "done":
                    skipped += 1
                    continue

                if url is not None:
                    dest = dl_dir / key
                    if not dest.exists():
                        client.download(url, dest)
                        downloaded_files += 1
                    path = dest
                else:
                    path = Path(source)

                for rec in iter_records(path, cfg.delimiter, cfg.column_order):
                    writer.add({"zinc_id": compound_id_of(rec), "smiles": rec["smiles"], "tranche": key})
                    parsed_records += 1

                progress[key] = "done"
                save_progress(progress_path, progress)
        finally:
            written = writer.close()

        stats = {
            "urls": len(sources),
            "downloaded_files": downloaded_files,
            "parsed_records": parsed_records,
            "skipped": skipped,
            "parquet_shards": len(written),
        }
        logger.info("stage1.done", **stats)
        return StageOutput(paths=written, stats=stats)

    @staticmethod
    def _resolve_sources(cfg) -> list[str]:
        sources: list[str] = []
        if cfg.manifest_path:
            sources.extend(_read_manifest(cfg.manifest_path))
        sources.extend(cfg.tranches)
        if not sources:
            raise RuntimeError(
                "Нет tranche для загрузки: задайте stage1.manifest_path или stage1.tranches"
            )
        return sources


def _source_key(source: str) -> str:
    if source.startswith(("http://", "https://")):
        return Path(urlparse(source).path).name or "download"
    return Path(source).name


def compound_id_of(rec: dict) -> str:
    """Возвращает ID соединения из записи (колонка, отличная от 'smiles')."""
    return next(v for k, v in rec.items() if k != "smiles")


def _read_manifest(manifest_path: str) -> list[str]:
    if manifest_path.startswith(("http://", "https://")):
        resp = httpx.get(manifest_path, timeout=60.0, follow_redirects=True, trust_env=False)
        resp.raise_for_status()
        text = resp.text
    else:
        text = Path(manifest_path).read_text(encoding="utf-8")
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def iter_records(
    path: Path, delimiter: str = " ", column_order: list[str] | None = None
):
    """Построчно читает файл и отдаёт словари {колонка: значение}."""
    column_order = column_order or ["smiles", "zinc_id"]
    opener = gzip.open if path.name.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(delimiter)
            if len(parts) < len(column_order):
                logger.warning("stage1.skip_line", line=line[:80])
                continue
            yield dict(zip(column_order, parts[: len(column_order)]))
