from __future__ import annotations

import logging
import random
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from .calewood_api import CalewoodApiClient
from .config import Settings
from .imgbb import ImgbbClient
from .media import capture_frames_at_positions, evenly_spaced_positions, midpoint_positions, probe_duration
from .qbittorrent import QBittorrentClient
from .utils import find_imgbb_links


def _capture_prefix(torrent, part_index: int | None = None) -> str:
    base = torrent.sharewood_hash or torrent.lacale_hash or str(torrent.torrent_id)
    if part_index is None:
        return base
    return f"{base}_part{part_index}"


def _build_capture_jobs(torrent, candidates: list[Any]) -> list[dict[str, object]]:
    if len(candidates) == 1:
        return [{"candidate": candidates[0], "positions": evenly_spaced_positions(9), "prefix": _capture_prefix(torrent)}]

    if len(candidates) == 2:
        return [
            {"candidate": candidate, "positions": evenly_spaced_positions(9), "prefix": _capture_prefix(torrent, index)}
            for index, candidate in enumerate(candidates, start=1)
        ]

    if len(candidates) == 3:
        return [
            {"candidate": candidate, "positions": evenly_spaced_positions(6), "prefix": _capture_prefix(torrent, index)}
            for index, candidate in enumerate(candidates, start=1)
        ]

    sample_size = min(18, len(candidates) - (len(candidates) % 3))
    if sample_size <= 0:
        sample_size = min(3, len(candidates))
    seed_value = torrent.sharewood_hash or torrent.lacale_hash or str(torrent.torrent_id)
    rng = random.Random(seed_value)
    selected = rng.sample(candidates, k=sample_size)
    return [
        {
            "candidate": candidate,
            "positions": midpoint_positions(1),
            "prefix": _capture_prefix(torrent, index),
        }
        for index, candidate in enumerate(selected, start=1)
    ]


def _build_prepended_comment(urls: list[str], existing_comment: str) -> str:
    existing_comment = existing_comment.strip()
    urls_block = "\n".join(urls)
    if not existing_comment:
        return urls_block
    return f"{urls_block}\n\n{existing_comment}"


def _ensure_capture_files_exist(captures: list[Path]) -> None:
    missing = [str(path) for path in captures if not path.exists()]
    if missing:
        raise RuntimeError(f"capture_files_missing count={len(missing)} files={missing}")


def _build_source_table(calewood: CalewoodApiClient, settings: Settings) -> list[dict[str, object]]:
    return [
        {
            "name": "archives",
            "list_fn": lambda: calewood.list_torrents(
                status="my-archives",
                category=settings.calewood_api_category,
                per_page=settings.calewood_api_per_page,
            ),
        },
        {
            "name": "upload",
            "list_fn": lambda: calewood.list_upload_mine_torrents(
                status="my-uploads",
                category=settings.calewood_api_category,
                per_page=settings.calewood_api_per_page,
            ),
        },
        {
            "name": "uploading",
            "list_fn": lambda: calewood.list_upload_mine_torrents(
                status="my-uploading",
                category=settings.calewood_api_category,
                per_page=settings.calewood_api_per_page,
            ),
        },
    ]


def run(
    settings: Settings,
    force_live: bool = False,
    force_id: int | None = None,
    force_hash: str | None = None,
    skip_qb: bool = False,
) -> int:
    log = logging.getLogger("calewood_movie_preview.workflow")
    dry_run = settings.dry_run and not force_live

    calewood = CalewoodApiClient(
        settings.calewood_api_base_url,
        settings.calewood_api_token,
        settings.calewood_api_timeout_seconds,
        settings.calewood_api_verify_tls,
    )
    qb = None
    if not skip_qb:
        qb = QBittorrentClient(
            settings.qbittorrent_base_url,
            settings.qbittorrent_username,
            settings.qbittorrent_password,
            settings.qbittorrent_verify_tls,
            settings.qbittorrent_timeout_seconds,
        )
        qb.login()
    imgbb = ImgbbClient(settings.imgbb_api_key, settings.imgbb_timeout_seconds, settings.imgbb_album_id)

    exit_code = 0
    log.info("Stage 1/4: fetching CALEWOOD sources", extra={"event": "stage_fetch_sources"})
    force_mode = force_id is not None and force_hash is not None
    if force_mode:
        raw_items = [{"id": force_id, "status": "forced", "sharewood_hash": force_hash}]
    else:
        source_table = _build_source_table(calewood, settings)
        staged: list[tuple[str, dict]] = []
        for source in source_table:
            list_fn = source["list_fn"]
            name = str(source["name"])
            for item in list_fn():
                if not isinstance(item, dict):
                    continue
                staged.append((name, item))

        seen_ids: set[int] = set()
        raw_items = []
        for source_name, item in staged:
            torrent_id = item.get("id")
            if not isinstance(torrent_id, int) or torrent_id in seen_ids:
                continue
            seen_ids.add(torrent_id)
            raw = item
            if isinstance(raw, dict) and raw:
                raw["_source"] = source_name
                raw_items.append(raw)
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
    detailed_preflight_enabled = False
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
            "raw_status_counts": dict(raw_status_counts),
            "missing_id_or_status": missing_id_or_status,
            "detailed_preflight_enabled": detailed_preflight_enabled,
            "preflight_max_items": settings.preflight_max_items,
        },
    )
    log.info(
        "Stage 2/4: filtering and matching torrents",
        extra={
            "event": "stage_preflight",
            "detailed_preflight_enabled": detailed_preflight_enabled,
            "items_fetched": len(raw_items),
        },
    )
    for raw in raw_items:
        torrent = calewood.to_model(raw, settings.hash_field_name)
        if torrent is None:
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
            if len(links) >= 9:
                stats["existing_comments"] += 1
                log.info(
                    "Skipping torrent with existing imgbb links",
                    extra={"event": "skip_existing_imgbb_links", "imgbb_link_count": len(links), **context},
                )
                continue
            if skip_qb:
                log.info(
                    "Candidate requires image generation (qBittorrent skipped)",
                    extra={"event": "skip_qb_candidate", **context},
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

            candidates = qb.select_videos(qb_torrent, settings.path_map_source, settings.path_map_target)
            log.info(
                "Selected video candidates",
                extra={
                    "event": "selected_video_candidate",
                    "qb_hash": str(getattr(qb_torrent, "hash", "")),
                    "qb_name": str(getattr(qb_torrent, "name", "")),
                    "video_count": len(candidates),
                    "file_paths": [str(candidate.path) for candidate in candidates],
                    **context,
                },
            )
            temp_dir = settings.temp_dir / str(torrent.torrent_id)
            capture_jobs = _build_capture_jobs(torrent, candidates)
            captures = []
            for job in capture_jobs:
                duration = probe_duration(settings.ffprobe_bin, job["candidate"].path)
                captures.extend(
                    capture_frames_at_positions(
                        settings.ffmpeg_bin,
                        job["candidate"].path,
                        duration,
                        temp_dir,
                        settings.image_format,
                        job["prefix"],
                        job["positions"],
                    )
                )
            log.info(
                "Generated capture set",
                extra={
                    "event": "captures_generated",
                    "capture_count": len(captures),
                    "capture_dir": str(temp_dir),
                    "video_count": len(candidates),
                    **context,
                },
            )
            _ensure_capture_files_exist(captures)
            if dry_run:
                stats["processed"] += 1
                log.info(
                    "Dry-run active, skipping imgbb upload and comment post",
                    extra={
                        "event": "dry_run_no_remote_write",
                        "capture_count": len(captures),
                        "capture_dir": str(temp_dir),
                        "video_count": len(candidates),
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
            calewood.post_comment(torrent.torrent_id, _build_prepended_comment(urls, comment))
            stats["processed"] += 1
            log.info(
                "Posted comment to CALEWOOD_API",
                extra={"event": "comment_posted", "posted_link_count": len(urls), "prepended_to_existing_comment": bool(comment.strip()), **context},
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

    log.info("Stage 3/4: generating captures", extra={"event": "stage_generate_captures"})
    if not dry_run:
        log.info("Stage 4/4: uploading and posting comments", extra={"event": "stage_remote_publish"})
    log.info(
        "Workflow finished",
        extra={
            "event": "workflow_finished",
            "dry_run": dry_run,
            **stats,
        },
    )
    return exit_code
