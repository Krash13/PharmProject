from __future__ import annotations

import numpy as np
import pytest

from pharmproject.pk.compartmental import compute_microconstants
from pharmproject.pk.dosing import dosing_objective, outside_fraction, simulate_repeated
from pharmproject.stages.stage7_pk import _as_fraction


def test_compute_microconstants():
    p = compute_microconstants(cl=5.0, vss=200.0, fu=0.5, vc=4.5, qfast=150.0, qslow=30.0)
    assert p.v2 == pytest.approx(0.35 * (200.0 - 4.5))
    assert p.v3 == pytest.approx(0.65 * (200.0 - 4.5))
    assert p.k21 == pytest.approx((150.0 / p.v2) * 0.5)
    assert p.k31 == pytest.approx((30.0 / p.v3) * 0.5)
    assert p.k12 == pytest.approx(p.k21 * p.v2 / 4.5)
    assert p.k13 == pytest.approx(p.k31 * p.v3 / 4.5)
    assert p.kel == pytest.approx(5.0 / 4.5)


def test_simulate_repeated_constant():
    def resp(t):
        return np.where(t >= 0, 1.0, 0.0)

    t, c = simulate_repeated(resp, dose=2.0, tau=1.0, horizon=2.0, n_points=3)
    assert list(t) == pytest.approx([0.0, 1.0, 2.0])
    assert list(c) == pytest.approx([2.0, 4.0, 6.0])


def test_outside_fraction():
    assert outside_fraction(np.array([1.0, 5.0, 10.0]), 1.0, 10.0) == 0.0
    assert outside_fraction(np.array([0.0, 5.0, 20.0]), 1.0, 10.0) == pytest.approx(2 / 3)


def test_dosing_objective():
    def resp(t):
        return np.where(t >= 0, 1.0, 0.0)

    assert dosing_objective([1.0, 1.0], resp, 0.5, 10.0, 2.0) == 0.0
    assert dosing_objective([100.0, 1.0], resp, 0.5, 10.0, 2.0) == 1.0


def test_as_fraction():
    assert _as_fraction("61.15%") == pytest.approx(0.6115)
    assert _as_fraction(0.5) == pytest.approx(0.5)
    assert _as_fraction("50") == pytest.approx(0.5)
