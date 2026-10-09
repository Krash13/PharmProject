from __future__ import annotations

import pytest

from pharmproject.chemistry.descriptors import DescriptorSet
from pharmproject.chemistry.filters import lead_like, lipinski, make_filter
from pharmproject.config import ThresholdsConfig


def _desc(mw=250.0, logp=2.0, hbd=0, hba=2, tpsa=40.0, rot=3, qed=0.6):
    return DescriptorSet(
        mw=mw, logp=logp, hbd=hbd, hba=hba, tpsa=tpsa, rot_bonds=rot, qed=qed
    )


def test_lead_like_defaults():
    th = ThresholdsConfig()
    assert lead_like(_desc(), th) is True
    assert lead_like(_desc(mw=100.0), th) is False  # < 150
    assert lead_like(_desc(mw=400.0), th) is False  # > 350
    assert lead_like(_desc(logp=4.0), th) is False  # > 3.5
    assert lead_like(_desc(rot=8), th) is False  # > 7


def test_lead_like_custom_thresholds():
    th = ThresholdsConfig(mw_min=100.0, mw_max=500.0, logp_max=5.0, rot_bonds_max=10)
    assert lead_like(_desc(mw=120.0), th) is True
    assert lead_like(_desc(logp=4.5), th) is True


def test_lipinski():
    assert lipinski(_desc()) is True
    assert lipinski(_desc(mw=600.0)) is False
    assert lipinski(_desc(logp=6.0)) is False
    assert lipinski(_desc(hbd=6)) is False
    assert lipinski(_desc(hba=11)) is False


def test_make_filter_none():
    f = make_filter("none", ThresholdsConfig())
    assert f(_desc(mw=1000.0)) is True


def test_make_filter_unknown():
    with pytest.raises(ValueError):
        make_filter("bogus", ThresholdsConfig())
