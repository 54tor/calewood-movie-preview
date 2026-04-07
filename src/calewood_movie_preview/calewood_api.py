from __future__ import annotations

import logging

import httpx

from .models import CalewoodTorrent


class CalewoodApiClient:
    def __init__(self, base_url: str, token: str, timeout: float, verify_tls: bool) -> None:
        self._log = logging.getLogger("calewood_movie_preview.calewood_api")
        self._client = httpx.Client(
            base_url=base_url.rstrip("/") + "/",
            timeout=timeout,
            verify=verify_tls,
            follow_redirects=True,
            headers={"Authorization": f"Bearer {token}"},
        )

    def list_torrents(self, *, status: str, category: str | None = None, per_page: int = 100) -> list[dict]:
        return self._list_paginated("archive/list", status=status, category=category, per_page=per_page)

    def list_awaiting_fiche_torrents(self, *, category: str | None = None, per_page: int = 100) -> list[dict]:
        return self._list_paginated("upload/pre-archivage/list", status=None, category=category, per_page=per_page)

    def _list_paginated(
        self,
        endpoint: str,
        *,
        status: str | None,
        category: str | None,
        per_page: int,
    ) -> list[dict]:
        page = 1
        items: list[dict] = []
        while True:
            params: dict[str, object] = {"p": page, "per_page": per_page}
            if status:
                params["status"] = status
            if category:
                params["cat"] = category
            response = self._client.get(endpoint, params=params)
            response.raise_for_status()
            batch, has_next = self._extract_paginated_items(response.json())
            items.extend(batch)
            if not has_next or not batch:
                return items
            page += 1

    def torrent_comment(self, torrent_id: int) -> str:
        response = self._client.get(f"torrent/comment/{torrent_id}")
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            if isinstance(data.get("data"), dict):
                return str(data["data"].get("comment") or "")
            return str(data.get("comment") or "")
        return ""

    def post_comment(self, torrent_id: int, comment: str) -> None:
        response = self._client.post(f"torrent/comment/{torrent_id}", json={"comment": comment})
        response.raise_for_status()

    @staticmethod
    def to_model(raw: dict, hash_field_name: str) -> CalewoodTorrent | None:
        torrent_id = raw.get("id")
        status = raw.get("status")
        if torrent_id is None or status is None:
            return None
        configured_hash = raw.get(hash_field_name)
        sharewood_hash = raw.get("sharewood_hash")
        lacale_hash = raw.get("lacale_hash")
        if hash_field_name == "lacale_hash" and configured_hash:
            lacale_hash = configured_hash
        elif configured_hash:
            sharewood_hash = configured_hash
        return CalewoodTorrent(
            torrent_id=int(torrent_id),
            status=str(status),
            sharewood_hash=(str(sharewood_hash).strip() if sharewood_hash else None),
            lacale_hash=(str(lacale_hash).strip() if lacale_hash else None),
            name=(str(raw.get("name")).strip() if raw.get("name") else None),
            comment=(str(raw.get("comment")).strip() if raw.get("comment") else None),
        )

    @staticmethod
    def _extract_paginated_items(data: object) -> tuple[list[dict], bool]:
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)], False
        if not isinstance(data, dict):
            return [], False

        payload = data.get("data", data)
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)], False

        if not isinstance(payload, dict):
            return [], False

        items = payload.get("data", [])
        if not isinstance(items, list):
            items = []

        current_page = payload.get("current_page")
        last_page = payload.get("last_page")
        next_page_url = payload.get("next_page_url")
        has_next = bool(next_page_url)
        if current_page is not None and last_page is not None:
            try:
                has_next = int(current_page) < int(last_page)
            except (TypeError, ValueError):
                pass
        return [item for item in items if isinstance(item, dict)], has_next
