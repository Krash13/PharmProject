#!/usr/bin/env bash
# =====================================================================
# Настройка боевого окружения PharmProject (Linux + NVIDIA GPU, 2×A100)
# Требуется Python 3.11+ (иначе ADMET-AI v2 и nvMolKit не встанут).
# =====================================================================
set -euo pipefail

PYTHON=${PYTHON:-python3.11}

# Проверка версии Python: нужен 3.11+
if ! "$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    echo "ОШИБКА: нужен Python 3.11+, а '$PYTHON' — это:"
    "$PYTHON" --version 2>/dev/null || true
    echo "Укажите интерпретатор явно, например:"
    echo "  PYTHON=python3.12 bash scripts/setup_prod.sh"
    exit 1
fi

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
