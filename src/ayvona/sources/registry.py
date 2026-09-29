"""Maps ``sources.type`` (``"telegram"``, later ``"web:hh_uz"``) to a source class.

Adding a new kind of source = write a class + ``@register("web:xyz")``. The pipeline never changes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ayvona.config import CollectorConfig
from ayvona.db.models import Source
from ayvona.sources.base import BaseSource
from ayvona.sources.telegram_source import TelegramSource


@dataclass(slots=True)
class SourceDeps:
    """Shared things sources may need (one Telegram connection for all channels, settings...)."""

    collector: CollectorConfig
    telegram_client: Any | None = None


SourceFactory = Callable[[Source, SourceDeps], BaseSource]
_REGISTRY: dict[str, SourceFactory] = {}


class UnknownSourceTypeError(LookupError):
    pass


def register(type_key: str) -> Callable[[SourceFactory], SourceFactory]:
    def deco(factory: SourceFactory) -> SourceFactory:
        _REGISTRY[type_key] = factory
        return factory

    return deco


def registered_types() -> list[str]:
    return sorted(_REGISTRY)


def create_source(row: Source, deps: SourceDeps) -> BaseSource:
    factory = _REGISTRY.get(row.type)
    if factory is None:
        raise UnknownSourceTypeError(
            f"{row.identifier}: unknown source type {row.type!r}; known: {registered_types()}"
        )
    return factory(row, deps)


@register("telegram")
def _telegram(row: Source, deps: SourceDeps) -> BaseSource:
    if deps.telegram_client is None:
        raise RuntimeError("Telegram client is not connected")
    return TelegramSource(
        row.identifier,
        deps.telegram_client,
        initial_backfill=deps.collector.initial_backfill,
        fetch_limit=deps.collector.fetch_limit,
    )
