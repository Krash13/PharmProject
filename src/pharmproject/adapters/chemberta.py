"""Адаптер ChemBERTa (HuggingFace Transformers)."""

from __future__ import annotations

import os


class ChembertaAdapter:
    """Загружает дообученную ChemBERTa и предсказывает pIC50 (лениво, CPU по умолчанию)."""

    def __init__(self, checkpoint_path: str, device: str = "cpu") -> None:
        self.checkpoint_path = checkpoint_path
        self.device = device
        self._tokenizer = None
        self._model = None

    def _load(self):
        if self._model is None:
            if self.device == "cpu":
                os.environ["CUDA_VISIBLE_DEVICES"] = ""
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            self._tokenizer = AutoTokenizer.from_pretrained(self.checkpoint_path)
            self._model = AutoModelForSequenceClassification.from_pretrained(
                self.checkpoint_path
            )
            self._model.eval()
            if self.device != "cpu":
                self._model.to(self.device)
        return self._tokenizer, self._model

    def predict(self, smiles_list: list[str]) -> list[float]:
        """Предсказывает pIC50 для списка SMILES (один батч)."""
        tokenizer, model = self._load()
        import torch

        enc = tokenizer(smiles_list, padding=True, truncation=True, return_tensors="pt")
        if self.device != "cpu":
            enc = {k: v.to(self.device) for k, v in enc.items()}
        with torch.no_grad():
            logits = model(**enc).logits
        return logits.squeeze(-1).detach().cpu().tolist()
