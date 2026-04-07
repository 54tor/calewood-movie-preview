from __future__ import annotations

from pathlib import Path

import qbittorrentapi

from .models import VideoCandidate

VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".m4v", ".ts"}


class QBittorrentClient:
    def __init__(self, base_url: str, username: str, password: str, verify_tls: bool, timeout: float) -> None:
        self._client = qbittorrentapi.Client(
            host=base_url,
            username=username,
            password=password,
            VERIFY_WEBUI_CERTIFICATE=verify_tls,
            REQUESTS_ARGS={"timeout": timeout},
        )

    def login(self) -> None:
        self._client.auth_log_in()

    def torrent_by_hash(self, hash_value: str):
        for torrent in self._client.torrents_info():
            if str(torrent.hash).lower() == hash_value.lower():
                return torrent
        return None

    def select_video(self, torrent, path_map_source: str | None = None, path_map_target: str | None = None) -> VideoCandidate:
        files = []
        content_path = Path(str(getattr(torrent, "content_path")))
        save_path = Path(str(getattr(torrent, "save_path", content_path.parent)))
        for item in self._client.torrents_files(torrent_hash=torrent.hash):
            path = Path(getattr(item, "name"))
            if path.suffix.lower() not in VIDEO_EXTENSIONS:
                continue
            if path.is_absolute():
                full_path = path
            elif content_path.suffix.lower() in VIDEO_EXTENSIONS:
                # qBittorrent returns the full file path for single-file torrents.
                full_path = content_path
            else:
                full_path = save_path / path
            if path_map_source and path_map_target:
                full_path = Path(str(full_path).replace(path_map_source, path_map_target, 1))
            files.append(VideoCandidate(path=full_path, size=int(getattr(item, "size", 0))))

        if not files:
            raise ValueError("video_not_found")
        if len(files) > 3:
            raise RuntimeError("too_many_video_files_warning")
        files.sort(key=lambda candidate: candidate.size, reverse=True)
        return files[0]
