from __future__ import annotations

import yaml

from pharmproject.adapters.boltz import build_boltz_yaml, parse_affinity


def test_build_boltz_yaml():
    text = build_boltz_yaml("MKTV", "CCO")
    doc = yaml.safe_load(text)
    seqs = doc["sequences"]
    assert seqs[0]["protein"]["id"] == "A"
    assert seqs[0]["protein"]["sequence"] == "MKTV"
    assert seqs[1]["ligand"]["smiles"] == "CCO"


def test_parse_affinity():
    aff = parse_affinity(
        {"affinity_pred_value": -1.5, "affinity_probability_binary": 0.9}
    )
    assert aff["affinity_pred_value"] == -1.5
    assert aff["affinity_probability_binary"] == 0.9


def test_parse_affinity_missing():
    assert parse_affinity({}) is None
    assert parse_affinity({"other": 1}) is None
