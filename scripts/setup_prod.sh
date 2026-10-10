#!/usr/bin/env bash
# =====================================================================
# Настройка боевого окружения PharmProject (этапы 1–6, Linux + NVIDIA GPU)
# Требуется Python 3.11 или 3.12 (Boltz требует <3.13).
#
# Этап 7 (PK, PyPharm + KrasheMit) — отдельное окружение:
#   bash scripts/setup_stage7.sh
# =====================================================================
set -euo pipefail

# --- Авто-выбор Python 3.11/3.12 (Boltz: >=3.10,<3.13) ---------------
PYTHON="${PYTHON:-}"
if [ -z "$PYTHON" ]; then
    for cand in python3.12 python3.11 python3; do
        if command -v "$cand" >/dev/null 2>&1 \
           && "$cand" -c 'import sys; sys.exit(0 if (3,11) <= sys.version_info[:2] < (3,13) else 1)' 2>/dev/null; then
            PYTHON="$cand"
            break
        fi
    done
fi

if [ -z "$PYTHON" ] || ! "$PYTHON" -c 'import sys; sys.exit(0 if (3,11) <= sys.version_info[:2] < (3,13) else 1)' 2>/dev/null; then
    echo "===================================================================="
    echo "ОШИБКА: нужен Python 3.11 или 3.12 (Boltz не поддерживает 3.13+)."
    echo "Найденные интерпретаторы:"
    for c in python3.12 python3.11 python3.10 python3; do
        command -v "$c" >/dev/null 2>&1 && printf '  %-12s %s\n' "$c" "$($c --version 2>&1)"
    done
    echo ""
    echo "Как получить Python 3.11/3.12:"
    echo "  1) conda/mamba: conda create -n pharm python=3.12 -y && conda activate pharm"
    echo "     PYTHON=python bash scripts/setup_prod.sh"
    echo "  2) модульная система: module avail python && module load python/3.12"
    echo "  3) Ubuntu deadsnakes: sudo add-apt-repository ppa:deadsnakes/ppa && sudo apt update"
    echo "     sudo apt install -y python3.12 python3.12-venv"
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

# --- Установка всего ОДНОЙ командой (резолвер видит все зависимости) ---
echo "==> Устанавливаю этапы 1–6 одной командой"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -e . "boltz[cuda]"

echo ""
echo "Готово (этапы 1–6). Проверьте:"
echo "  python --version"
echo "  python -c 'import torch, rdkit, scipy, numpy, pyarrow, datasets; print(\"numpy\", numpy.__version__, \"pyarrow\", pyarrow.__version__, \"scipy\", scipy.__version__, \"rdkit\", rdkit.__version__, \"datasets\", datasets.__version__, \"cuda\", torch.cuda.is_available())'"
echo "  nvidia-smi"
echo ""
echo "Этап 7 (PK) запускается в отдельном окружении: bash scripts/setup_stage7.sh"
echo "Дальше: cp config/config.prod.yaml config/config.yaml"
