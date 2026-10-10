#!/usr/bin/env bash
# =====================================================================
# Настройка боевого окружения PharmProject (Linux + NVIDIA GPU, 2×A100)
# Требуется Python 3.11+.
#
# ВАЖНО: ядро + Boltz ставятся ОДНОЙ командой pip (резолвер видит все
# зависимости сразу). pypharm/krashemit ставятся с --no-deps, потому что
# их пин scipy<=1.13.0 конфликтует с Boltz (scipy==1.13.1).
# =====================================================================
set -euo pipefail

# --- Авто-выбор Python 3.11+ -----------------------------------------
PYTHON="${PYTHON:-}"
if [ -z "$PYTHON" ]; then
    for cand in python3.13 python3.12 python3.11 python3; do
        if command -v "$cand" >/dev/null 2>&1 \
           && "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
            PYTHON="$cand"
            break
        fi
    done
fi

if [ -z "$PYTHON" ] || ! "$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    echo "===================================================================="
    echo "ОШИБКА: не найден Python 3.11+."
    echo "Найденные интерпретаторы:"
    for c in python3.13 python3.12 python3.11 python3; do
        command -v "$c" >/dev/null 2>&1 && printf '  %-12s %s\n' "$c" "$($c --version 2>&1)"
    done
    echo ""
    echo "Как получить Python 3.11+:"
    echo "  1) conda/mamba: conda create -n pharm python=3.12 -y && conda activate pharm"
    echo "     PYTHON=python bash scripts/setup_prod.sh"
    echo "  2) модульная система: module avail python && module load python/3.12"
    echo "  3) Ubuntu deadsnakes: sudo add-apt-repository ppa:deadsnakes/ppa && sudo apt update"
    echo "     sudo apt install -y python3.11 python3.11-venv"
    echo "  4) uv: curl -LsSf https://astral.sh/uv/install.sh | sh && uv python install 3.12"
    echo "===================================================================="
    exit 1
fi

echo "==> Использую: $PYTHON ($("$PYTHON" --version 2>&1))"

# --- Чистое окружение -------------------------------------------------
echo "==> Пересоздаю .venv"
rm -rf .venv
"$PYTHON" -m venv .venv
source .venv/bin/activate

echo "==> Python в venv: $(python --version)"

# --- 1) Ядро + Boltz одной командой ----------------------------------
echo "==> Устанавливаю ядро + Boltz одной командой"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -e . "boltz[cuda]"

# --- 2) KrasheMit (--no-deps: пин scipy<=1.13.0 конфликтует с Boltz) ---
#    setup.py собирает C++-модуль krashemit.ico (нужны компилятор C++ и pybind11).
echo "==> KrasheMit (--no-deps)"
python -m pip install --no-deps "git+https://github.com/Krash13/KrasheMit.git@testing"

# --- 3) PyPharm (--no-deps по той же причине; krashemit уже стоит) ----
echo "==> PyPharm (--no-deps)"
python -m pip install --no-deps "git+https://github.com/Krash13/PyPharm.git"

# --- 4) nvMolKit (этап 2 GPU; опционально) ---------------------------
echo "==> nvMolKit (опционально)"
python -m pip install nvmolkit || echo "    (nvMolKit пропущен — этап 2 на RDKit/CPU)"

echo ""
echo "Готово. Проверьте:"
echo "  python --version"
echo "  python -c 'import torch, rdkit, scipy; print(\"torch\", torch.__version__, \"cuda\", torch.cuda.is_available(), \"rdkit\", rdkit.__version__, \"scipy\", scipy.__version__)'"
echo "  python -c 'from PyPharm import BaseCompartmentModel; import krashemit; print(\"pypharm + krashemit OK\")'"
echo "  nvidia-smi"
echo ""
echo "Дальше: cp config/config.prod.yaml config/config.yaml  и заполните target.sequence."
