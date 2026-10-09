"""CLI: python -m pharmproject run <stage> [--resume] [--config PATH]."""

from __future__ import annotations

import typer

from pharmproject.config import load_config
from pharmproject.pipeline.runner import run_stage

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.command()
def run(
    stage: str = typer.Argument(..., help="Имя стадии, например stage1"),
    resume: bool = typer.Option(False, "--resume", help="Пропускать уже обработанные tranche"),
    config: str = typer.Option("config/config.yaml", "--config", help="Путь к YAML-конфигу"),
) -> None:
    """Запускает стадию воронки."""
    cfg = load_config(config)
    out = run_stage(stage, cfg, resume=resume)
    typer.echo(f"Стадия {stage} завершена. Шардов: {len(out.paths)}. Статистика: {out.stats}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
