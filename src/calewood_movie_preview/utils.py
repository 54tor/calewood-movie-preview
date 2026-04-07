from __future__ import annotations

import re


IMGBB_RE = re.compile(r"(?:https?://)?(?:imgbb\.com|i\.ibb\.co)/\S+", re.IGNORECASE)


def find_imgbb_links(comment: str) -> list[str]:
    return IMGBB_RE.findall(comment or "")
