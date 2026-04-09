from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class CalewoodTorrent:
    torrent_id: int
    status: str
    sharewood_hash: str | None
    lacale_hash: str | None = None
    name: str | None = None
    comment: str | None = None


@dataclass(slots=True)
class VideoCandidate:
    path: Path
    size: int
    relative_name: str | None = None
