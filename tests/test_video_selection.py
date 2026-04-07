from pathlib import Path
from types import SimpleNamespace

import pytest

from calewood_movie_preview.qbittorrent import QBittorrentClient


def _client(files):
    client = QBittorrentClient("http://qb", "u", "p", True, 30)
    client._client = SimpleNamespace(torrents_files=lambda torrent_hash: files)  # noqa: SLF001
    return client


def test_selects_largest_of_two() -> None:
    torrent = SimpleNamespace(hash="abc", content_path="/media")
    files = [SimpleNamespace(name="a.mkv", size=10), SimpleNamespace(name="b.mkv", size=20)]
    candidate = _client(files).select_video(torrent)
    assert candidate.path == Path("/media/b.mkv")


def test_selects_largest_of_three() -> None:
    torrent = SimpleNamespace(hash="abc", content_path="/media")
    files = [
        SimpleNamespace(name="a.mkv", size=10),
        SimpleNamespace(name="b.mkv", size=50),
        SimpleNamespace(name="c.mkv", size=20),
    ]
    candidate = _client(files).select_video(torrent)
    assert candidate.path == Path("/media/b.mkv")


def test_more_than_three_warns() -> None:
    torrent = SimpleNamespace(hash="abc", content_path="/media")
    files = [SimpleNamespace(name=f"{idx}.mkv", size=idx) for idx in range(4)]
    with pytest.raises(RuntimeError):
        _client(files).select_video(torrent)
