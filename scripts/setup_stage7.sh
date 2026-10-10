#!/usr/bin/env bash
# =====================================================================
# Отдельное окружение для ЭТАПА 7 (PK): PyPharm + KrasheMit.
#
# Почему отдельно: PyPharm/KrasheMit требуют scipy<=1.13.0, а Boltz —
# scipy==1.13.1. Оба окружения используют numpy 1.26 и pyarrow 15–17,
# различие только в версии scipy. Parquet совместим между ними.
# =====================================================================
set -euo pipefail

PYTHON="${PYTHON:-python3.11}"
if ! "$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
    echo "ОШИБКА: нужен Python 3.10+ (достаточно 3.10/3.11), а '$PYTHON' не подходит."
    exit 1
fi

echo "==> Создаю окружение .venv-stage7"
rm -rf .venv-stage7
"$PYTHON" -m venv .venv-stage7
source .venv-stage7/bin/activate

echo "==> Ядро пакета + зависимости этапа 7"
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install \
    "numpy==1.26.4" \
    "scipy==1.13.0" \
    "pyarrow==17.0.0" \
    "matplotlib>=3.5.1" \
    "numba>=0.58.1" \
    "graycode>=1.0.5" \
    "numbalsoda>=0.3.4" \
    "pyTelegramBotAPI>=4.29.1" \
    "pybind11>=2.12"

echo "==> KrasheMit (--no-deps, собирает krashemit.ico)"
python -m pip install --no-deps "git+https://github.com/Krash13/KrasheMit.git@testing"

echo "==> PyPharm (--no-deps, krashemit уже стоит)"
python -m pip install --no-deps "git+https://github.com/Krash13/PyPharm.git"

echo ""
echo "Готово (этап 7). Запуск:"
echo "  source .venv-stage7/bin/activate"
echo "  python -m pharmproject stage7 --config config/config.yaml --resume"
