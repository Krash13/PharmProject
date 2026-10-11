"""Этап 1 (альтернатива) — загрузка Enamine REAL.

Скачивает файлы Enamine REAL (make-on-demand, ~10 млрд drug-like соединений)
и пишет Parquet-шарды в том же формате, что и ZINC22-этап: поле `zinc_id`
хранит ID соединения (для Enamine это его catalog ID). Благодаря этому
этапы 2–7 работают без изменений.
"""

from __future__ import annotations

from pathlib import Path

import structlog

from pharmproject.adapters.enamine import EnamineClient
from pharmproject.pipeline.base import PipelineContext, Stage, StageOutput
from pharmproject.stages.stage1_zinc22 import _read_manifest, _source_key, compound_id_of, iter_records
from pharmproject.storage.checkpoint import load_progress, save_progress
from pharmproject.storage.store import ParquetShardWriter

logger = structlog.get_logger()


class Stage1Enamine(Stage):
    name = "stage1_enamine"

    def _get_config(self, ctx: PipelineContext):
        return ctx.config.enamine

    def _make_client(self, cfg) -> EnamineClient:
        return EnamineClient(
            base_url=cfg.base_url,
            timeout=cfg.timeout_s,
            max_retries=cfg.max_retries,
            retry_wait=cfg.retry_wait,
        )

    def run(self, ctx: PipelineContext) -> StageOutput:
        cfg = self._get_config(ctx)
        client = self._make_client(cfg)
        sources = self._resolve_sources(cfg)

        out_root = Path(cfg.output_dir)
        if not out_root.is_absolute():
            out_root = ctx.data_dir / out_root
        dl_dir = out_root / "downloads"
        shard_dir = out_root / "shards"
        progress_path = out_root / "progress.json"
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
            "sources": len(sources),
            "downloaded_files": downloaded_files,
            "parsed_records": parsed_records,
            "skipped": skipped,
            "parquet_shards": len(written),
        }
        logger.info(f"{self.name}.done", **stats)
        return StageOutput(paths=written, stats=stats)

    @staticmethod
    def _resolve_sources(cfg) -> list[str]:
        sources: list[str] = []
        if cfg.manifest_path:
            sources.extend(_read_manifest(cfg.manifest_path))
        sources.extend(cfg.files)
        if not sources:
            raise RuntimeError(
                "Нет файлов для загрузки: задайте manifest_path или files"
            )
        return sources
