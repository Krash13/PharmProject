"""Оптимизатор ICO (алгоритм взаимодействующих стран).

Использует скомпилированный C++-модуль `ico` (src/ico.cpp, pybind11), иначе —
Python-версию из KrasheMit (ветка testing).
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger()


def _try_import_cpp():
    try:
        import ico  # собранный pybind11-модуль

        return ico
    except Exception:
        return None


class IcoOptimizer:
    """Алгоритм взаимодействующих стран (ICO) с C++-ускорением и Python-fallback."""

    def __init__(
        self,
        M: int = 10,
        N: int = 20,
        n: tuple = (1, 5),
        p: tuple = (0.1, 0.5),
        m: tuple = (1, 3),
        k: int = 3,
        l: int = 3,
        ep: tuple = (0.2, 0.3),
        tmax: int = 300,
        printing: bool = False,
    ) -> None:
        self.M = M
        self.N = N
        self.n = n
        self.p = p
        self.m = m
        self.k = k
        self.l = l
        self.ep = ep
        self.tmax = tmax
        self.printing = printing
        self._cpp = _try_import_cpp()
        if self._cpp is not None:
            logger.info("ico.backend", backend="cpp")
        else:
            logger.info("ico.backend", backend="python")

    def optimize(self, f, x_min, x_max) -> dict:
        """Минимизирует f(x) на [x_min, x_max]; возвращает {x, f, iterations}."""
        if self._cpp is not None:
            return self._optimize_cpp(f, x_min, x_max)
        return self._optimize_python(f, x_min, x_max)

    def _optimize_cpp(self, f, x_min, x_max) -> dict:
        genes = [16] * len(x_min)
        return self._cpp.run_countries_algorithm_pyfunc(
            f=f,
            x_min=list(x_min),
            x_max=list(x_max),
            genes=genes,
            p_min=self.p[0],
            p_max=self.p[1],
            M=self.M,
            N=self.N,
            n_min=self.n[0],
            n_max=self.n[1],
            m_min=self.m[0],
            m_max=self.m[1],
            k=self.k,
            l=self.l,
            ep_elite=self.ep[0],
            ep_dead=self.ep[1],
            max_mutation=3,
            tmax=self.tmax,
            gray_percent=0.5,
            printing=self.printing,
        )

    def _optimize_python(self, f, x_min, x_max) -> dict:
        from krashemit.algorithms.country_optimization import CountriesAlgorithm

        alg = CountriesAlgorithm(
            f=f,
            Xmin=list(x_min),
            Xmax=list(x_max),
            M=self.M,
            N=self.N,
            n=list(self.n),
            p=list(self.p),
            m=list(self.m),
            k=self.k,
            l=self.l,
            ep=list(self.ep),
            tmax=self.tmax,
            printing=self.printing,
        )
        x, fval, _flag, iters = alg.start()
        return {"x": list(x), "f": float(fval), "iterations": int(iters)}
