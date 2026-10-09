"""Модели данных воронки."""

from __future__ import annotations

from pydantic import BaseModel


class MoleculeRecord(BaseModel):
    """Центральная модель данных.

    Заполняется по мере прохождения воронки. На этапе 1 — только базовые поля;
    канонизация SMILES и InChIKey добавляются на этапе 2.
    """

    zinc_id: str
    smiles: str
    tranche: str | None = None
