"""Дообучение ChemBERTa (регрессия pIC50)."""

from __future__ import annotations

import os
from pathlib import Path

import structlog

logger = structlog.get_logger()


def fine_tune(
    data: list[tuple[str, float]],
    model_name: str,
    output_dir: Path,
    device: str = "cpu",
    epochs: int = 3,
    batch_size: int = 16,
    learning_rate: float = 2e-5,
    max_length: int = 512,
) -> Path:
    """Обучает ChemBERTa регрессии pIC50 и сохраняет чекпоинт в output_dir/final."""
    if device == "cpu":
        os.environ["CUDA_VISIBLE_DEVICES"] = ""

    from datasets import Dataset
    from transformers import (
        AutoModelForSequenceClassification,
        AutoTokenizer,
        Trainer,
        TrainingArguments,
    )

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=1)

    def tokenize(examples):
        return tokenizer(examples["smiles"], truncation=True, max_length=max_length)

    ds = Dataset.from_list([{"smiles": s, "pic50": p} for s, p in data])
    ds = ds.map(tokenize, batched=True)
    ds = ds.train_test_split(test_size=0.2, seed=42)

    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        learning_rate=learning_rate,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        logging_steps=10,
        load_best_model_at_end=True,
        report_to=[],  # отключаем внешние трекеры (wandb и т.п.)
        no_cuda=(device == "cpu"),
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=ds["train"],
        eval_dataset=ds["test"],
    )
    trainer.train()

    final_dir = output_dir / "final"
    model.save_pretrained(final_dir)
    tokenizer.save_pretrained(final_dir)
    logger.info("chemberta.finetuned", final=str(final_dir))
    return final_dir
