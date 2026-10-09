"""Трёхкамерная PK-модель на PyPharm.

Микроконстанты считаются по формулам из плана (CL, Vss, fu → камеры).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class PKParams:
    cl: float
    vss: float
    fu: float
    vc: float
    v2: float
    v3: float
    k12: float
    k13: float
    k21: float
    k31: float
    kel: float


def compute_microconstants(
    cl: float, vss: float, fu: float, vc: float = 4.5, qfast: float = 150.0, qslow: float = 30.0
) -> PKParams:
    """Считает микроконстанты трёхкамерной модели (формулы из плана)."""
    v2 = 0.35 * (vss - vc)
    v3 = 0.65 * (vss - vc)
    k21 = (qfast / v2) * fu
    k31 = (qslow / v3) * fu
    k12 = k21 * (v2 / vc)
    k13 = k31 * (v3 / vc)
    kel = cl / vc
    return PKParams(
        cl=cl, vss=vss, fu=fu, vc=vc, v2=v2, v3=v3,
        k12=k12, k13=k13, k21=k21, k31=k31, kel=kel,
    )


def build_model(p: PKParams):
    """Собирает трёхкамерную модель PyPharm."""
    from PyPharm import BaseCompartmentModel

    matrix = [
        [0.0, p.k12, p.k13],
        [p.k21, 0.0, 0.0],
        [p.k31, 0.0, 0.0],
    ]
    outputs = [p.kel, 0.0, 0.0]
    return BaseCompartmentModel(matrix, outputs, volumes=[p.vc, p.v2, p.v3])


def simulate(model, max_time: float, dose: float, compartment_number: int = 0):
    """Решает модель для одной дозы; возвращает (t, y) — списки."""
    res = model(max_time, d=dose, compartment_number=compartment_number)
    return res.t.tolist(), res.y.tolist()


def make_single_dose_response(model, max_time: float):
    """Возвращает функцию C(t) на единицу дозы (для суперпозиции)."""
    from scipy.interpolate import interp1d

    res = model(max_time, d=1.0, compartment_number=0)
    return interp1d(res.t, res.y[0], bounds_error=False, fill_value=0.0)


def pk_params_to_dict(p: PKParams) -> dict:
    return asdict(p)
