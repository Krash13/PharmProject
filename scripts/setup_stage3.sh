#!/usr/bin/env bash
# =====================================================================
# Отдельное окружение для ЭТАПА 3 (ADMET-AI) — torch под CUDA 12.4.
#
# ПОЧЕМУ отдельно: драйвер NVIDIA на машине — CUDA 12.4 (версия 12040,
# т.е. драйвер 550.x), а torch в основном окружении собран под CUDA 13
# (нужен драйвер >=570). Здесь ставим torch cu124 (CUDA 12.4), который
# совместим с драйвером 550.
#
# Совместимость связки:
#   numpy 1.26 + pyarrow 15-17 + rdkit 2026.3.6 + torch cu124 + admet-ai v2
#   (те же numpy/pyarrow/rdkit, что и в основном окружении — Parquet совместим).
# =====================================================================
set -euo pipefail

PYTHON="${PYTHON:-python3.12}"

echo "==> Создаю .venv-stage3"
rm -rf .venv-stage3
"$PYTHON" -m venv .venv-stage3
source .venv-stage3/bin/activate

python -m pip install --upgrade pip

echo "==> Ядро pharmproject (без тяжёлых зависимостей)"
python -m pip install -e . --no-deps
python -m pip install \
    "httpx>=0.27" "tenacity>=8.2" "typer>=0.12" \
    "pydantic>=2.5" "PyYAML>=6.0" "structlog>=24.1"

echo "==> Данные + химия (совместимо с основным окружением)"
python -m pip install \
    "numpy<2.0" \
    "pyarrow>=15.0,<18" \
    "rdkit==2026.3.6"

echo "==> torch под CUDA 12.4 (совместим с драйвером 550)"
python -m pip install torch --index-url https://download.pytorch.org/whl/cu124

echo "==> ADMET-AI v2 (torch уже стоит cu124 — не перезапишется)"
python -m pip install "admet-ai>=2.0"

echo ""
echo "Готово (этап 3). Проверка:"
echo "  python -c 'import torch; print(\"torch\", torch.__version__, \"cuda\", torch.cuda.is_available())'"
echo "  python -c 'from admet_ai import ADMETModel; print(\"admet_ai OK\")'"
echo ""
echo "Запуск этапа 3:"
echo "  source .venv-stage3/bin/activate"
echo "  python -m pharmproject stage3 --config config/config.yaml --resume"
