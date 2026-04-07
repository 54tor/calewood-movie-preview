from __future__ import annotations

import base64
from pathlib import Path

import httpx


class ImgbbClient:
    def __init__(self, api_key: str, timeout: float) -> None:
        self._client = httpx.Client(timeout=timeout)
        self._api_key = api_key

    def upload(self, path: Path) -> str:
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        response = self._client.post(
            "https://api.imgbb.com/1/upload",
            data={"key": self._api_key, "image": encoded},
        )
        response.raise_for_status()
        data = response.json()
        return str(data["data"]["url"])
