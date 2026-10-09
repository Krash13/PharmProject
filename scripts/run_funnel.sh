#!/usr/bin/env bash
# =====================================================================
# Запуск полной воронки PharmProject.
#   ./scripts/run_funnel.sh [path/to/config.yaml]
# По умолчанию берёт config/config.yaml. Каждая стадия запускается
# с --resume (пропускает уже обработанные шарды).
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
run stage7

echo ""
echo "Воронка завершена. Результаты:"
echo "  data/raw/zinc22/                     — скачанные SMILES (Parquet)"
echo "  data/intermediate/stage2_filtered/   — дескрипторы + фильтры"
echo "  data/intermediate/stage3_admet/      — ADMET-AI"
echo "  data/intermediate/stage4_scored/     — pIC50 (топ-N)"
echo "  data/intermediate/stage5_boltz/      — Boltz (аффинность)"
echo "  data/intermediate/stage6_final_admet/— финальный ADMET (ADMETlab 2.0)"
echo "  data/intermediate/stage7_pk/         — PK-модели и дозирование"
