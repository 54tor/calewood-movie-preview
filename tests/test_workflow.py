from pathlib import Path

from calewood_movie_preview.calewood_api import CalewoodApiClient
from calewood_movie_preview.models import CalewoodTorrent, VideoCandidate
from calewood_movie_preview.workflow import _build_capture_jobs


def test_to_model_missing_required_fields_returns_none() -> None:
    assert CalewoodApiClient.to_model({}, "info_hash") is None


def test_build_capture_jobs_uses_six_positions_each_for_three_videos() -> None:
    torrent = CalewoodTorrent(torrent_id=1, status="awaiting_fiche", sharewood_hash="abc")
    candidates = [
        VideoCandidate(path=Path(f"/tmp/video_{index}.mp4"), size=100 - index)
        for index in range(3)
    ]

    jobs = _build_capture_jobs(torrent, candidates)

    assert len(jobs) == 3
    assert all(len(job["positions"]) == 6 for job in jobs)
    assert sum(len(job["positions"]) for job in jobs) == 18


def test_build_capture_jobs_samples_multiple_of_three_for_large_collections() -> None:
    torrent = CalewoodTorrent(torrent_id=1, status="awaiting_fiche", sharewood_hash="abc")
    candidates = [
        VideoCandidate(path=Path(f"/tmp/video_{index}.mp4"), size=1000 - index)
        for index in range(200)
    ]

    jobs = _build_capture_jobs(torrent, candidates)

    assert len(jobs) == 18
    assert all(job["positions"] == [0.5] for job in jobs)
