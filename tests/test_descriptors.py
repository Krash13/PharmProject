from __future__ import annotations

import pytest
from rdkit import Chem

from pharmproject.chemistry.descriptors import compute_descriptors, parse_and_describe


def test_descriptors_ethanol():
    mol = Chem.MolFromSmiles("CCO")
    d = compute_descriptors(mol)
    assert d.mw == pytest.approx(46.07, rel=1e-2)
    assert d.hbd == 1
    assert d.hba == 1
    assert d.rot_bonds == 0
    assert 0.0 <= d.qed <= 1.0


def test_descriptors_aspirin():
    mol = Chem.MolFromSmiles("CC(=O)Oc1ccccc1C(=O)O")
    d = compute_descriptors(mol)
    assert d.mw == pytest.approx(180.16, rel=1e-2)
    assert d.hbd == 1
    assert d.hba == 3
    assert d.rot_bonds == 2


def test_parse_and_describe():
    canonical, inchi_key, d = parse_and_describe("CC(=O)Oc1ccccc1C(=O)O")
    assert canonical == "CC(=O)Oc1ccccc1C(=O)O"
    assert inchi_key == "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"
    assert d.mw == pytest.approx(180.16, rel=1e-2)


def test_parse_invalid_returns_none():
    assert parse_and_describe("") is None
    assert parse_and_describe("not_a_smiles") is None
    assert parse_and_describe("C1CC") is None  # незамкнутое кольцо
