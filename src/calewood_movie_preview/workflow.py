from __future__ import annotations

import logging
from collections import Counter
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
    if settings.calewood_api_include_my_pre_archiving:
        raw_items.extend(
            calewood.list_pre_archiving_torrents(
                status=settings.calewood_api_pre_archiving_status,
                category=settings.calewood_api_category,
                per_page=settings.calewood_api_per_page,
            )
        )
    if settings.calewood_api_include_upload_mine:
        raw_items.extend(
            calewood.list_upload_mine_torrents(
                status=settings.calewood_api_upload_status,
                category=settings.calewood_api_category,
                per_page=settings.calewood_api_per_page,
            )
        )
    if settings.calewood_api_single_id is not None:
        raw_items = [raw for raw in raw_items if raw.get("id") == settings.calewood_api_single_id]

    raw_status_counts = Counter()
    missing_id_or_status = 0
    for raw in raw_items:
        raw_id = raw.get("id")
        raw_status = raw.get("status")
        if raw_id is None or raw_status is None:
            missing_id_or_status += 1
            continue
        raw_status_counts[str(raw_status)] += 1

    seen_ids: set[int] = set()
    planned_jobs: list[dict[str, object]] = []
    stats = {
        "considered": 0,
        "processed": 0,
        "partial_comments": 0,
        "existing_comments": 0,
        "missing_hash": 0,
        "qb_not_found": 0,
        "qb_incomplete": 0,
        "too_many_video_files": 0,
        "warnings": 0,
        "errors": 0,
        "queued_for_capture": 0,
        "queued_bytes": 0,
    }
    log.info(
        "Workflow started",
        extra={
            "event": "workflow_started",
            "dry_run": dry_run,
            "items_fetched": len(raw_items),
            "category": settings.calewood_api_category,
            "single_id": settings.calewood_api_single_id,
            "list_status": settings.calewood_api_list_status,
            "pre_archiving_status": settings.calewood_api_pre_archiving_status,
            "upload_status": settings.calewood_api_upload_status,
            "include_my_pre_archiving": settings.calewood_api_include_my_pre_archiving,
            "include_upload_mine": settings.calewood_api_include_upload_mine,
            "archived_statuses": sorted(settings.archived_statuses()),
            "raw_status_counts": dict(raw_status_counts),
            "missing_id_or_status": missing_id_or_status,
        },
    )
    for raw in raw_items:
        torrent = calewood.to_model(raw, settings.hash_field_name)
        if torrent is None or torrent.status not in settings.archived_statuses():
            continue
        if torrent.torrent_id in seen_ids:
            continue
        seen_ids.add(torrent.torrent_id)
        stats["considered"] += 1
        context = {
            "torrent_id": torrent.torrent_id,
            "status": torrent.status,
            "sharewood_hash": torrent.sharewood_hash,
            "lacale_hash": torrent.lacale_hash,
            "torrent_name": torrent.name,
        }
        try:
            log.info("Processing torrent", extra={"event": "processing_torrent", **context})
            comment = torrent.comment if torrent.comment is not None else calewood.torrent_comment(torrent.torrent_id)
            links = find_imgbb_links(comment)
            if 1 <= len(links) < 9:
                stats["partial_comments"] += 1
                stats["warnings"] += 1
                log.warning(
                    "Partial imgbb links already present in comment",
                    extra={"event": "partial_imgbb_links_warning", "imgbb_link_count": len(links), **context},
                )
                continue
            if links:
                stats["existing_comments"] += 1
                log.info(
                    "Skipping torrent with existing imgbb links",
                    extra={"event": "skip_existing_imgbb_links", "imgbb_link_count": len(links), **context},
                )
                continue
            candidate_hashes = [hash_value for hash_value in [torrent.sharewood_hash, torrent.lacale_hash] if hash_value]
            if not candidate_hashes:
                stats["missing_hash"] += 1
                stats["errors"] += 1
                log.error("No usable source hash found", extra={"event": "missing_source_hash", **context})
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
                stats["qb_not_found"] += 1
                stats["errors"] += 1
                log.error(
                    "qBittorrent torrent not found for provided hashes",
                    extra={"event": "qb_torrent_not_found", "lookup_hashes": candidate_hashes, **context},
                )
                exit_code = 1
                continue
            log.info(
                "Matched torrent in qBittorrent",
                extra={
                    "event": "qb_torrent_matched",
                    "matched_hash": matched_hash,
                    "qb_hash": str(getattr(qb_torrent, "hash", "")),
                    "qb_name": str(getattr(qb_torrent, "name", "")),
                    **context,
                },
            )
            if float(getattr(qb_torrent, "progress", 0.0)) < 1.0:
                stats["qb_incomplete"] += 1
                log.info(
                    "Skipping incomplete qBittorrent torrent",
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
                "Selected video candidate",
                extra={
                    "event": "selected_video_candidate",
                    "qb_hash": str(getattr(qb_torrent, "hash", "")),
                    "qb_name": str(getattr(qb_torrent, "name", "")),
                    "file_path": str(candidate.path),
                    "file_size": candidate.size,
                    **context,
                },
            )
            temp_dir = settings.temp_dir / str(torrent.torrent_id)
            stats["queued_for_capture"] += 1
            stats["queued_bytes"] += candidate.size
            planned_jobs.append(
                {
                    "torrent": torrent,
                    "candidate_path": candidate.path,
                    "candidate_size": candidate.size,
                    "temp_dir": temp_dir,
                    "context": context,
                }
            )
        except RuntimeError as exc:
            if str(exc) == "too_many_video_files_warning":
                stats["too_many_video_files"] += 1
            stats["warnings"] += 1
            log.warning(str(exc), extra={"event": str(exc), **context})
        except Exception as exc:
            stats["errors"] += 1
            log.error(str(exc), extra={"event": "workflow_error", **context})
            exit_code = 1

    log.info(
        "Preflight completed",
        extra={
            "event": "preflight_completed",
            "dry_run": dry_run,
            "queued_for_capture": stats["queued_for_capture"],
            "queued_bytes": stats["queued_bytes"],
            "queued_gib": round(stats["queued_bytes"] / (1024**3), 2),
            "considered": stats["considered"],
            "existing_comments": stats["existing_comments"],
            "partial_comments": stats["partial_comments"],
            "missing_hash": stats["missing_hash"],
            "qb_not_found": stats["qb_not_found"],
            "qb_incomplete": stats["qb_incomplete"],
            "too_many_video_files": stats["too_many_video_files"],
        },
    )

    for job in planned_jobs:
        torrent = job["torrent"]
        candidate_path = job["candidate_path"]
        candidate_size = job["candidate_size"]
        temp_dir = job["temp_dir"]
        context = job["context"]
        try:
            duration = probe_duration(settings.ffprobe_bin, candidate_path)
            captures = capture_frames(
                settings.ffmpeg_bin,
                candidate_path,
                duration,
                temp_dir,
                settings.image_format,
                torrent.sharewood_hash or torrent.lacale_hash or str(torrent.torrent_id),
            )
            log.info(
                "Generated capture set",
                extra={
                    "event": "captures_generated",
                    "capture_count": len(captures),
                    "capture_dir": str(temp_dir),
                    "duration_seconds": duration,
                    "file_path": str(candidate_path),
                    "file_size": candidate_size,
                    **context,
                },
            )
            if dry_run:
                stats["processed"] += 1
                log.info(
                    "Dry-run active, skipping imgbb upload and comment post",
                    extra={
                        "event": "dry_run_no_remote_write",
                        "capture_count": len(captures),
                        "capture_dir": str(temp_dir),
                        "file_path": str(candidate_path),
                        "file_size": candidate_size,
                        **context,
                    },
                )
                continue

            urls = [imgbb.upload(path) for path in captures]
            log.info(
                "Completed imgbb upload",
                extra={
                    "event": "imgbb_upload_completed",
                    "uploaded_count": len(urls),
                    "capture_dir": str(temp_dir),
                    **context,
                },
            )
            calewood.post_comment(torrent.torrent_id, "\n".join(urls))
            stats["processed"] += 1
            log.info(
                "Posted comment to CALEWOOD_API",
                extra={"event": "comment_posted", "posted_link_count": len(urls), **context},
            )
        except Exception as exc:
            stats["errors"] += 1
            log.error(str(exc), extra={"event": "workflow_error", **context})
            exit_code = 1
    log.info(
        "Workflow finished",
        extra={
            "event": "workflow_finished",
            "dry_run": dry_run,
            **stats,
        },
    )
    return exit_code
