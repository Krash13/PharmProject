#!/usr/bin/env bash
# =====================================================================
# Настройка боевого окружения PharmProject (Linux + NVIDIA GPU, 2×A100)
# Требуется Python 3.11+ (иначе ADMET-AI v2 и nvMolKit не встанут).
# =====================================================================
set -euo pipefail

# --- Авто-выбор Python 3.11+ -----------------------------------------
# Можно задать явно: PYTHON=python3.12 bash scripts/setup_prod.sh
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
    echo ""
    echo "Найденные интерпретаторы:"
    for c in python3.13 python3.12 python3.11 python3; do
        if command -v "$c" >/dev/null 2>&1; then
            printf '  %-12s %s\n' "$c" "$($c --version 2>&1)"
        fi
    done
    echo ""
    echo "Как получить Python 3.11+:"
    echo "  1) conda/mamba (рекомендуется для HPC):"
    echo "     conda create -n pharm python=3.12 -y && conda activate pharm"
    echo "     PYTHON=python bash scripts/setup_prod.sh"
    echo ""
    echo "  2) модульная система (Lmod):"
    echo "     module avail python && module load python/3.12"
    echo "     PYTHON=python bash scripts/setup_prod.sh"
    echo ""
    echo "  3) Ubuntu — PPA deadsnakes (python3.12 в старых версиях нет):"
    echo "     sudo add-apt-repository ppa:deadsnakes/ppa && sudo apt update"
    echo "     sudo apt install -y python3.11 python3.11-venv"
    echo ""
    echo "  4) uv:"
    echo "     curl -LsSf https://astral.sh/uv/install.sh | sh && uv python install 3.12"
    echo "===================================================================="
    exit 1
fi

echo "==> Использую: $PYTHON ($("$PYTHON" --version 2>&1))"

echo "==> Создаю виртуальное окружение (.venv)"
"$PYTHON" -m venv .venv
source .venv/bin/activate

echo "==> Устанавливаю зависимости"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .

echo "==> KrasheMit (оптимизация дозирования, ветка testing)"
python -m pip install "git+https://github.com/Krash13/KrasheMit.git@testing"

echo "==> Boltz (этап 5, GPU)"
python -m pip install "boltz[cuda]"

echo "==> nvMolKit (этап 2 на GPU; только Linux+NVIDIA, опционально)"
python -m pip install nvmolkit || echo "    (nvMolKit пропущен — этап 2 пойдёт на RDKit/CPU)"

echo "==> pybind11 (для C++-ускорения ICO, опционально)"
python -m pip install pybind11 || true

echo ""
echo "Готово. Проверьте GPU:"
echo "  python -c 'import torch; print(torch.cuda.is_available(), torch.cuda.device_count())'"
echo "  nvidia-smi"
echo ""
echo "Дальше: cp config/config.prod.yaml config/config.yaml  и заполните target.sequence."
