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


def test_more_than_ten_warns() -> None:
    torrent = SimpleNamespace(hash="abc", content_path="/media")
    files = [SimpleNamespace(name=f"{idx}.mkv", size=idx) for idx in range(11)]
    with pytest.raises(RuntimeError):
        _client(files).select_video(torrent)


def test_uses_save_path_for_multi_file_torrent_subfolder() -> None:
    torrent = SimpleNamespace(
        hash="abc",
        save_path="/tank/rtorrent/download",
        content_path="/tank/rtorrent/download/Marc Dorcel Les Gros Seins De l'Infirmiere and Making Of 2013 VOF DVDRip x264 AC3-PPD",
    )
    files = [
        SimpleNamespace(
            name="Marc Dorcel Les Gros Seins De l'Infirmiere and Making Of 2013 VOF DVDRip x264 AC3-PPD/Marc Dorcel Les Gros Seins De l'Infirmiere 2013 VOF DVDRip x264 AC3-PPD.mp4",
            size=20,
        )
    ]
    candidate = _client(files).select_video(torrent)
    assert candidate.path == Path(
        "/tank/rtorrent/download/Marc Dorcel Les Gros Seins De l'Infirmiere and Making Of 2013 VOF DVDRip x264 AC3-PPD/Marc Dorcel Les Gros Seins De l'Infirmiere 2013 VOF DVDRip x264 AC3-PPD.mp4"
    )
