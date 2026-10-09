#!/usr/bin/env bash
# =====================================================================
# Настройка боевого окружения PharmProject (Linux + NVIDIA GPU, 2×A100)
# =====================================================================
set -euo pipefail

PYTHON=${PYTHON:-python3}

echo "==> Создаю виртуальное окружение (.venv) на Python 3.11+"
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
