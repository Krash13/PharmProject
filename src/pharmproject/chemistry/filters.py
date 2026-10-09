"""Правила-фильтры для этапов 2–3."""

from __future__ import annotations

import operator
from typing import Callable

from pharmproject.chemistry.descriptors import DescriptorSet
from pharmproject.config import ThresholdsConfig


def lead_like(d: DescriptorSet, th: ThresholdsConfig) -> bool:
    """Lead-like: MW 150–350, LogP ≤ 3.5, мало вращающихся связей."""
    return th.mw_min <= d.mw <= th.mw_max and d.logp <= th.logp_max and d.rot_bonds <= th.rot_bonds_max


def lipinski(d: DescriptorSet) -> bool:
    """Правило пяти Липински (канонические значения)."""
    return d.mw <= 500.0 and d.logp <= 5.0 and d.hbd <= 5 and d.hba <= 10


def make_filter(rule: str, th: ThresholdsConfig) -> Callable[[DescriptorSet], bool]:
    """Возвращает предикат по имени правила."""
    rule = (rule or "none").strip().lower()
    if rule in ("lead-like", "leadlike", "lead_like"):
        return lambda d: lead_like(d, th)
    if rule == "lipinski":
        return lipinski
    if rule in ("none", ""):
        return lambda d: True
    raise ValueError(f"Неизвестное правило фильтра: {rule!r}")


_OPS = {
    "<=": operator.le,
    ">=": operator.ge,
    "<": operator.lt,
    ">": operator.gt,
    "==": operator.eq,
    "!=": operator.ne,
}


def passes_admet_filters(preds: dict, rules) -> bool:
    """Проверяет предсказания ADMET-AI по набору правил (AND).

    Возвращает False, если свойство отсутствует, равно NaN или нарушает правило.
    """
    for rule in rules:
        op = _OPS.get(rule.op)
        if op is None:
            raise ValueError(f"Неизвестный оператор в правиле ADMET: {rule.op!r}")
        val = preds.get(rule.property)
        if val is None or val != val:  # отсутствует или NaN
            return False
        if not op(float(val), rule.value):
            return False
    return True
