"""Оптимизация дозирования (доза d и интервал τ)."""

from __future__ import annotations

import numpy as np


def simulate_repeated(single_dose_response, dose: float, tau: float, horizon: float, n_points: int = 300):
    """Повторное дозирование через суперпозицию одной дозы (линейная PK).

    single_dose_response(t) — концентрация центральной камеры на единицу дозы.
    Возвращает (t_grid, c_grid).
    """
    tgrid = np.linspace(0.0, horizon, n_points)
    c = np.zeros_like(tgrid)
    k = 0
    while k * tau <= horizon:
        mask = tgrid >= k * tau  # доза действует только с момента введения
        contrib = np.asarray(single_dose_response(tgrid - k * tau), dtype=float)
        c += dose * np.where(mask, contrib, 0.0)
        k += 1
    return tgrid, c


def outside_fraction(c, cmin: float, cmax: float) -> float:
    """Доля времени, когда концентрация вне окна [cmin, cmax]."""
    c = np.asarray(c, dtype=float)
    return float(((c < cmin) | (c > cmax)).mean())


def dosing_objective(x, single_dose_response, cmin: float, cmax: float, horizon: float) -> float:
    """Целевая функция: минимизировать долю времени вне терапевтического окна.

    x = [dose, tau].
    """
    dose, tau = float(x[0]), float(x[1])
    _, c = simulate_repeated(single_dose_response, dose, tau, horizon)
    return outside_fraction(c, cmin, cmax)
