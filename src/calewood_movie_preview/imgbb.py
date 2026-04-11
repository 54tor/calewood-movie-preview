from __future__ import annotations

import base64
from pathlib import Path

import httpx


class ImgbbClient:
    def __init__(self, api_key: str, timeout: float, album_id: str | None = None) -> None:
        self._client = httpx.Client(timeout=timeout)
        self._api_key = api_key
        self._album_id = album_id

    def upload(self, path: Path) -> str:
        try:
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        except FileNotFoundError as exc:
            raise RuntimeError(f"imgbb_upload_missing_file path={path}") from exc
        payload = {"key": self._api_key, "image": encoded}
        if self._album_id:
            payload["album_id"] = self._album_id
        response = self._client.post("https://api.imgbb.com/1/upload", data=payload)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = response.text.strip().replace("\n", " ")
            if len(body) > 500:
                body = body[:500] + "..."
            raise RuntimeError(
                f"imgbb_upload_error status_code={response.status_code} image_path={path} response_body={body}"
            ) from exc
        data = response.json()
        return str(data["data"]["url"])
