"""Запуск стадий."""

from __future__ import annotations

import structlog

from pharmproject.config import Config
from pharmproject.pipeline.base import PipelineContext, StageOutput
from pharmproject.pipeline.registry import get_stage_class

logger = structlog.get_logger()


def run_stage(name: str, config: Config, resume: bool = False) -> StageOutput:
    """Создаёт стадию по имени и выполняет её."""
    ctx = PipelineContext(config=config)
    stage_cls = get_stage_class(name)
    stage = stage_cls(resume=resume)
    logger.info("run.stage.start", stage=name, resume=resume)
    out = stage.run(ctx)
    logger.info("run.stage.done", stage=name, stats=out.stats)
    return out
