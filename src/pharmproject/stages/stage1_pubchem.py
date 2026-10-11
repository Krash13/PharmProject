"""Этап 1 (альтернатива) — загрузка PubChem.

Скачивает файл PubChem CID-SMILES (все ~110 млн соединений, tab-разделённый
`CID\\tSMILES`) и пишет Parquet-шарды в том же формате, что и ZINC22: поле
`zinc_id` хранит PubChem CID. Этапы 2–7 работают без изменений.
"""

from __future__ import annotations

from pharmproject.adapters.pubchem import PubchemClient
from pharmproject.pipeline.base import PipelineContext
from pharmproject.stages.stage1_enamine import Stage1Enamine


class Stage1Pubchem(Stage1Enamine):
    name = "stage1_pubchem"

    def _get_config(self, ctx: PipelineContext):
        return ctx.config.pubchem

    def _make_client(self, cfg) -> PubchemClient:
        return PubchemClient(
            base_url=cfg.base_url,
            timeout=cfg.timeout_s,
            max_retries=cfg.max_retries,
            retry_wait=cfg.retry_wait,
        )
