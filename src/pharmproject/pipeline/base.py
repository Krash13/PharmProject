"""Базовые классы конвейера: Stage, PipelineContext, StageOutput."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pharmproject.config import Config


@dataclass
class StageOutput:
    """Результат выполнения стадии: выходные пути и счётчики."""

    paths: list[Path] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineContext:
    """Общий контекст выполнения: конфиг и производные пути."""

    config: "Config"

    def __post_init__(self) -> None:
        self.data_dir = Path(self.config.data_dir)


class Stage(ABC):
    """Единица конвейера. Каждая стадия идемпотентна и умеет возобновляться."""

    name: str = "stage"

    def __init__(self, resume: bool = False) -> None:
        self.resume = resume

    @abstractmethod
    def run(self, ctx: PipelineContext) -> StageOutput:
        """Выполняет стадию и возвращает выходные пути и счётчики."""
        raise NotImplementedError
