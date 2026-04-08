from __future__ import annotations

from .calewood_api import CalewoodApiClient
from .config import Settings


def list_pre_archiving_video(settings: Settings) -> int:
    client = CalewoodApiClient(
        settings.calewood_api_base_url,
        settings.calewood_api_token,
        settings.calewood_api_timeout_seconds,
        settings.calewood_api_verify_tls,
    )
    items = client.list_pre_archiving_torrents(
        status="awaiting_fiche",
        category="XXX",
        per_page=settings.calewood_api_per_page,
    )
    for raw in items:
        torrent = client.to_model(raw, settings.hash_field_name)
        if torrent is None:
            continue
        print(f"{torrent.torrent_id}\t{torrent.status}\t{torrent.name or ''}")
    return 0
