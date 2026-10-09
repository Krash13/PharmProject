"""Этап 1 — загрузка lead-like подмножества ZINC22.

Скачивает tranche-файлы (SMILES, .smi/.smi.gz), парсит их и пишет в Parquet-шарды.
Канонизация SMILES и расчёт InChIKey — на этапе 2.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from urllib.parse import urlparse

import httpx
import structlog

from pharmproject.adapters.zinc22 import Zinc22Client
from pharmproject.pipeline.base import PipelineContext, Stage, StageOutput
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
        progress = _load_progress(progress_path)

        writer = ParquetShardWriter(shard_dir, cfg.shard_rows)
        downloaded_files = 0
        parsed_records = 0
        skipped = 0

        try:
            for source in sources:
                remote = source.startswith(("http://", "https://"))
                key = _source_key(source)
                if self.resume and progress.get(key) == "done":
                    skipped += 1
                    continue

                if remote:
                    url = client.build_url(source)
                    dest = dl_dir / key
                    if not dest.exists():
                        client.download(url, dest)
                        downloaded_files += 1
                    path = dest
                else:
                    path = Path(source)
                    if not path.exists():
                        raise FileNotFoundError(f"Локальный tranche не найден: {source}")

                for smiles, zinc_id in iter_records(path, cfg.delimiter, cfg.column_order):
                    writer.add({"zinc_id": zinc_id, "smiles": smiles, "tranche": key})
                    parsed_records += 1

                progress[key] = "done"
                _save_progress(progress_path, progress)
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


def _load_progress(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _save_progress(path: Path, progress: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(progress, indent=2, ensure_ascii=False), encoding="utf-8")


def iter_records(
    path: Path, delimiter: str = " ", column_order: list[str] | None = None
):
    """Построчно читает tranche-файл и отдаёт кортежи (smiles, zinc_id)."""
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
            values = dict(zip(column_order, parts[: len(column_order)]))
            yield values["smiles"], values["zinc_id"]
