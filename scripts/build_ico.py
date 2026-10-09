"""Сборка C++-модуля `ico` из src/ico.cpp (KrasheMit) через pybind11.

Использование:
    python scripts/build_ico.py path/to/ico.cpp

Результат: модуль `ico` (ico.pyd на Windows / ico.so на Linux) в текущей папке.
Требования: pip install pybind11 + C++-компилятор (MSVC на Windows, gcc/clang на Linux).
После сборки оптимизатор IcoOptimizer автоматически подхватит C++-бэкенд.
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    cpp = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("ico.cpp")
    if not cpp.exists():
        raise SystemExit(f"Не найден {cpp}")

    # setuptools читает sys.argv как команду сборки
    sys.argv = ["build_ico.py", "build_ext", "--inplace"]

    from pybind11.setup_helpers import Pybind11Extension, build_ext
    from setuptools import setup

    setup(
        name="ico",
        ext_modules=[Pybind11Extension("ico", [str(cpp)], cxx_std=17)],
        cmdclass={"build_ext": build_ext},
        zip_safe=False,
    )


if __name__ == "__main__":
    main()
