from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime

from ..models import Ammo


@dataclass(frozen=True)
class FieldProvenance:
    source: str
    fetched_at: str
    source_path: str


@dataclass(frozen=True)
class SourceManifest:
    source: str
    url: str
    fetched_at: str
    priority: int
    record_count: int
    etag: str | None = None
    source_revision: str | None = None


@dataclass
class AdapterResult:
    manifest: SourceManifest
    ammo: list[Ammo]
    provenance: dict[str, dict[str, FieldProvenance]] = field(default_factory=dict)


class DataSourceAdapter(ABC):
    name: str
    priority: int

    @abstractmethod
    async def fetch(self) -> AdapterResult:
        """Fetch and normalize a source without writing application state."""


def utc_now() -> str:
    return datetime.now(UTC).isoformat()
