from __future__ import annotations

import pytest

from pharmproject.chemistry.filters import passes_admet_filters
from pharmproject.config import AdmetRule, Config


def test_passes_all_rules():
    rules = [
        AdmetRule(property="hERG", op="<=", value=0.5),
        AdmetRule(property="HIA_Hou", op=">=", value=0.5),
    ]
    assert passes_admet_filters({"hERG": 0.1, "HIA_Hou": 0.8}, rules) is True
    assert passes_admet_filters({"hERG": 0.9, "HIA_Hou": 0.8}, rules) is False
    assert passes_admet_filters({"hERG": 0.1, "HIA_Hou": 0.2}, rules) is False


def test_missing_property_fails():
    rules = [AdmetRule(property="hERG", op="<=", value=0.5)]
    assert passes_admet_filters({}, rules) is False


def test_nan_fails():
    rules = [AdmetRule(property="hERG", op="<=", value=0.5)]
    assert passes_admet_filters({"hERG": float("nan")}, rules) is False


def test_unknown_op_raises():
    rules = [AdmetRule(property="hERG", op="<>", value=0.5)]
    with pytest.raises(ValueError):
        passes_admet_filters({"hERG": 0.1}, rules)


def test_default_rules():
    rules = Config().stage3.filters
    assert len(rules) == 10
    good = {
        "hERG": 0.1, "DILI": 0.1, "ClinTox": 0.1, "AMES": 0.1,
        "Carcinogens_Lagunin": 0.1, "CYP3A4_Veith": 0.1, "CYP2D6_Veith": 0.1,
        "PAINS_alert": 0.0, "BRENK_alert": 0.0, "HIA_Hou": 0.8,
    }
    assert passes_admet_filters(good, rules) is True
