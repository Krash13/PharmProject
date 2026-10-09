"""CLI: python -m pharmproject <stage> [--resume] [--config PATH]."""

from __future__ import annotations

import typer

from pharmproject.config import load_config
from pharmproject.pipeline.runner import run_stage


def main(
    stage: str = typer.Argument(..., help="Имя стадии, например stage1"),
    resume: bool = typer.Option(False, "--resume", help="Пропускать уже обработанные шарды"),
    config: str = typer.Option("config/config.yaml", "--config", help="Путь к YAML-конфигу"),
) -> None:
    """Запускает стадию воронки."""
    cfg = load_config(config)
    out = run_stage(stage, cfg, resume=resume)
    typer.echo(f"Стадия {stage} завершена. Шардов: {len(out.paths)}. Статистика: {out.stats}")


def cli() -> None:
    """Точка входа CLI (python -m pharmproject и консольный скрипт)."""
    typer.run(main)


if __name__ == "__main__":
    cli()
