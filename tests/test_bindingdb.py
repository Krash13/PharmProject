from __future__ import annotations

import pytest

from pharmproject.models.chemberta import data


def test_to_pic50_prefers_ic50():
    rec = {data.COL_IC50: "1000", data.COL_KI: "2000"}  # 1000 нМ = 1e-6 М → 6.0
    assert data._to_pic50(rec) == pytest.approx(6.0)


def test_to_pic50_falls_back_to_ki():
    rec = {data.COL_IC50: "", data.COL_KI: "100"}  # 100 нМ = 1e-7 М → 7.0
    assert data._to_pic50(rec) == pytest.approx(7.0)


def test_to_pic50_skips_invalid():
    assert data._to_pic50({}) is None
    assert data._to_pic50({data.COL_IC50: "abc"}) is None
    assert data._to_pic50({data.COL_IC50: "-5"}) is None


def test_filter_bindingdb_records():
    recs = [
        {data.COL_SMILES: "CCO", data.COL_UNIPROT: "P9WGR1", data.COL_IC50: "1000"},
        {data.COL_SMILES: "CCN", data.COL_UNIPROT: "OTHER", data.COL_IC50: "1000"},  # другая мишень
        {data.COL_SMILES: "", data.COL_UNIPROT: "P9WGR1", data.COL_IC50: "1000"},  # нет SMILES
        {data.COL_SMILES: "CCC", data.COL_UNIPROT: "P9WGR1", data.COL_IC50: "bad"},  # битый IC50
    ]
    rows = data.filter_bindingdb_records(recs, "P9WGR1")
    assert len(rows) == 1
    assert rows[0][0] == "CCO"
    assert rows[0][1] == pytest.approx(6.0)


def test_aggregate_by_smiles_median():
    rows = [("CCO", 6.0), ("CCO", 8.0), ("CCN", 7.0)]
    agg = dict(data.aggregate_by_smiles(rows))
    assert agg["CCO"] == pytest.approx(7.0)  # медиана 6 и 8
    assert agg["CCN"] == pytest.approx(7.0)
