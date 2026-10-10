#!/usr/bin/env bash
# =====================================================================
# Запуск воронки PharmProject (этапы 1–6, основное окружение .venv).
#   ./scripts/run_funnel.sh [path/to/config.yaml]
#
# Этап 7 (PK) запускается отдельно в .venv-stage7 (PyPharm/KrasheMit):
#   source .venv-stage7/bin/activate
#   python -m pharmproject stage7 --config config/config.yaml --resume
# =====================================================================
set -euo pipefail

CONFIG=${1:-config/config.yaml}

run() {
    echo ""
    echo "==================== $1 ===================="
    python -m pharmproject "$1" --config "$CONFIG" --resume
}

run stage1
run stage2
run stage3
run stage4
run stage5
run stage6

echo ""
echo "Этапы 1–6 завершены. Результаты:"
echo "  data/raw/zinc22/                     — скачанные SMILES (Parquet)"
echo "  data/intermediate/stage2_filtered/   — дескрипторы + фильтры"
echo "  data/intermediate/stage3_admet/      — ADMET-AI"
echo "  data/intermediate/stage4_scored/     — pIC50 (топ-N)"
echo "  data/intermediate/stage5_boltz/      — Boltz (аффинность)"
echo "  data/intermediate/stage6_final_admet/— финальный ADMET (ADMETlab 2.0)"
echo ""
echo "Этап 7 (PK) — отдельно:"
echo "  source .venv-stage7/bin/activate"
echo "  python -m pharmproject stage7 --config $CONFIG --resume"
