"""Адаптер ADMET-AI (Chemprop v2): ленивая загрузка модели, батч-предсказание."""

from __future__ import annotations

import os

import structlog

logger = structlog.get_logger()


class AdmetAiAdapter:
    """Обёртка над ADMET-AI.

    Модель загружается лениво (на первый predict), чтобы юнит-тесты с моком
    не импортировали тяжёлые зависимости. По умолчанию работает на CPU.
    """

    def __init__(self, device: str = "cpu", num_workers: int = 16) -> None:
        self.device = device
        self.num_workers = num_workers
        self._model = None

    def _load_model(self):
        if self._model is None:
            if self.device == "cpu":
                os.environ["CUDA_VISIBLE_DEVICES"] = ""
            from admet_ai import ADMETModel

            self._model = ADMETModel(
                num_workers=self.num_workers,
                include_physchem=False,  # физико-химия уже посчитана на этапе 2
                drugbank_path=None,      # перцентили DrugBank не нужны (главный тормоз)
            )

            cuda = False
            try:
                import torch

                cuda = bool(torch.cuda.is_available())
            except Exception:
                pass
            logger.info(
                "admet.model_loaded",
                device=self.device,
                cuda_available=cuda,
                num_workers=self.num_workers,
            )
        return self._model

    def predict(self, smiles_list: list[str]) -> list[dict | None]:
        """Предсказывает ADMET для списка SMILES.

        Возвращает список словарей предсказаний, выровненный по порядку входных
        SMILES; None — если молекула выпала из результата (например, ADMET-AI
        отбросил последний батч размера 1).
        """
        df = self._load_model().predict(smiles=smiles_list)
        preds_by_smiles = df.to_dict(orient="index")
        return [preds_by_smiles.get(s) for s in smiles_list]
