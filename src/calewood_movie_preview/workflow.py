from __future__ import annotations

import logging
from pathlib import Path

from .calewood_api import CalewoodApiClient
from .config import Settings
from .imgbb import ImgbbClient
from .media import capture_frames, probe_duration
from .qbittorrent import QBittorrentClient
from .utils import find_imgbb_links


def run(settings: Settings, force_live: bool = False) -> int:
    log = logging.getLogger("calewood_movie_preview.workflow")
    dry_run = settings.dry_run and not force_live

    calewood = CalewoodApiClient(
        settings.calewood_api_base_url,
        settings.calewood_api_token,
        settings.calewood_api_timeout_seconds,
        settings.calewood_api_verify_tls,
    )
    qb = QBittorrentClient(
        settings.qbittorrent_base_url,
        settings.qbittorrent_username,
        settings.qbittorrent_password,
        settings.qbittorrent_verify_tls,
        settings.qbittorrent_timeout_seconds,
    )
    qb.login()
    imgbb = ImgbbClient(settings.imgbb_api_key, settings.imgbb_timeout_seconds)

    exit_code = 0
    raw_items = calewood.list_torrents(
        status=settings.calewood_api_list_status,
        category=settings.calewood_api_category,
        per_page=settings.calewood_api_per_page,
    )
    if settings.calewood_api_include_awaiting_fiche:
        raw_items.extend(
            calewood.list_awaiting_fiche_torrents(
                category=settings.calewood_api_category,
                per_page=settings.calewood_api_per_page,
            )
        )

    seen_ids: set[int] = set()
    log.info(
        "workflow_started",
        extra={
            "event": "workflow_started",
            "dry_run": dry_run,
            "items_fetched": len(raw_items),
            "category": settings.calewood_api_category,
            "list_status": settings.calewood_api_list_status,
            "include_awaiting_fiche": settings.calewood_api_include_awaiting_fiche,
        },
    )
    for raw in raw_items:
        torrent = calewood.to_model(raw, settings.hash_field_name)
        if torrent is None or torrent.status not in settings.archived_statuses():
            continue
        if torrent.torrent_id in seen_ids:
            continue
        seen_ids.add(torrent.torrent_id)
        context = {
            "torrent_id": torrent.torrent_id,
            "status": torrent.status,
            "sharewood_hash": torrent.sharewood_hash,
            "lacale_hash": torrent.lacale_hash,
            "torrent_name": torrent.name,
        }
        try:
            log.info("processing_torrent", extra={"event": "processing_torrent", **context})
            comment = torrent.comment if torrent.comment is not None else calewood.torrent_comment(torrent.torrent_id)
            links = find_imgbb_links(comment)
            if 1 <= len(links) < 9:
                log.warning(
                    "partial_imgbb_links_warning",
                    extra={"event": "partial_imgbb_links_warning", "imgbb_link_count": len(links), **context},
                )
                continue
            if links:
                log.info(
                    "skip_existing_imgbb_links",
                    extra={"event": "skip_existing_imgbb_links", "imgbb_link_count": len(links), **context},
                )
                continue
            candidate_hashes = [hash_value for hash_value in [torrent.sharewood_hash, torrent.lacale_hash] if hash_value]
            if not candidate_hashes:
                log.error("missing_source_hash", extra={"event": "missing_source_hash", **context})
                exit_code = 1
                continue

            qb_torrent = None
            matched_hash = None
            for hash_value in candidate_hashes:
                qb_torrent = qb.torrent_by_hash(hash_value)
                if qb_torrent is not None:
                    matched_hash = hash_value
                    break
            if qb_torrent is None:
                log.error(
                    "qb_torrent_not_found",
                    extra={"event": "qb_torrent_not_found", "lookup_hashes": candidate_hashes, **context},
                )
                exit_code = 1
                continue
            log.info(
                "qb_torrent_matched",
                extra={
                    "event": "qb_torrent_matched",
                    "matched_hash": matched_hash,
                    "qb_hash": str(getattr(qb_torrent, "hash", "")),
                    "qb_name": str(getattr(qb_torrent, "name", "")),
                    **context,
                },
            )
            if float(getattr(qb_torrent, "progress", 0.0)) < 1.0:
                log.info(
                    "skip_incomplete_qb_torrent",
                    extra={
                        "event": "skip_incomplete_qb_torrent",
                        "qb_hash": str(getattr(qb_torrent, "hash", "")),
                        "qb_name": str(getattr(qb_torrent, "name", "")),
                        "qb_progress": float(getattr(qb_torrent, "progress", 0.0)),
                        **context,
                    },
                )
                continue

            candidate = qb.select_video(qb_torrent, settings.path_map_source, settings.path_map_target)
            log.info(
                "selected_video_candidate",
                extra={
                    "event": "selected_video_candidate",
                    "qb_hash": str(getattr(qb_torrent, "hash", "")),
                    "qb_name": str(getattr(qb_torrent, "name", "")),
                    "file_path": str(candidate.path),
                    "file_size": candidate.size,
                    **context,
                },
            )
            duration = probe_duration(settings.ffprobe_bin, candidate.path)
            temp_dir = settings.temp_dir / str(torrent.torrent_id)
            captures = capture_frames(
                settings.ffmpeg_bin,
                candidate.path,
                duration,
                temp_dir,
                settings.image_format,
                torrent.sharewood_hash or torrent.lacale_hash or str(torrent.torrent_id),
            )
            log.info(
                "captures_generated",
                extra={
                    "event": "captures_generated",
                    "capture_count": len(captures),
                    "capture_dir": str(temp_dir),
                    "duration_seconds": duration,
                    "file_path": str(candidate.path),
                    **context,
                },
            )
            if dry_run:
                log.info(
                    "dry_run_no_remote_write",
                    extra={
                        "event": "dry_run_no_remote_write",
                        "capture_count": len(captures),
                        "capture_dir": str(temp_dir),
                        "file_path": str(candidate.path),
                        **context,
                    },
                )
                continue

            urls = [imgbb.upload(path) for path in captures]
            log.info(
                "imgbb_upload_completed",
                extra={
                    "event": "imgbb_upload_completed",
                    "uploaded_count": len(urls),
                    "capture_dir": str(temp_dir),
                    **context,
                },
            )
            calewood.post_comment(torrent.torrent_id, "\n".join(urls))
            log.info(
                "comment_posted",
                extra={"event": "comment_posted", "posted_link_count": len(urls), **context},
            )
        except RuntimeError as exc:
            log.warning(str(exc), extra={"event": str(exc), **context})
        except Exception as exc:
            log.error(str(exc), extra={"event": "workflow_error", **context})
            exit_code = 1
    return exit_code
