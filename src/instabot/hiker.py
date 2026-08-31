from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

import httpx

HIKER_BASE = "https://api.hikerapi.com"


class HikerError(Exception):
    pass


@dataclass(frozen=True)
class Post:
    pk: str
    taken_at: datetime
    caption: str | None = None
    image_url: str | None = None
    recent_comments: tuple[str, ...] = field(default_factory=tuple)


class WatchListReader(Protocol):
    def fetch_posts(self, watched_profile_pk: str) -> list[Post]: ...


class HikerApiClient:
    def __init__(self, access_key: str) -> None:
        self._access_key = access_key

    def fetch_posts(self, watched_profile_pk: str) -> list[Post]:
        try:
            response = httpx.get(
                f"{HIKER_BASE}/v1/user/medias/chunk",
                headers={"x-access-key": self._access_key},
                params={"user_id": watched_profile_pk},
                timeout=30.0,
            )
        except httpx.HTTPError as exc:
            raise HikerError(str(exc)) from exc
        if response.status_code != 200:
            raise HikerError(f"HikerAPI HTTP {response.status_code}")
        try:
            payload: Any = response.json()
        except ValueError as exc:
            raise HikerError("HikerAPI unreadable") from exc
        return [_parse_post(item) for item in _items(payload)]


def _items(payload: Any) -> list[Any]:
    if isinstance(payload, list) and payload and isinstance(payload[0], list):
        return list(payload[0])
    if isinstance(payload, dict) and isinstance(payload.get("items"), list):
        return list(payload["items"])
    raise HikerError("HikerAPI unreadable")


def _parse_post(item: Any) -> Post:
    if not isinstance(item, dict) or item.get("pk") is None:
        raise HikerError("HikerAPI unreadable")
    taken_at = _taken_at(item)
    caption = item.get("caption_text")
    if caption is None and isinstance(item.get("caption"), dict):
        caption = item["caption"].get("text")
    image_url = item.get("thumbnail_url")
    if not image_url:
        versions = item.get("image_versions") or []
        if versions and isinstance(versions[0], dict):
            image_url = versions[0].get("url")
    return Post(
        pk=str(item["pk"]),
        taken_at=taken_at,
        caption=str(caption) if caption else None,
        image_url=str(image_url) if image_url else None,
    )


def _taken_at(item: dict[str, Any]) -> datetime:
    ts = item.get("taken_at_ts")
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    raw = item.get("taken_at")
    if isinstance(raw, (int, float)):
        return datetime.fromtimestamp(raw, tz=timezone.utc)
    if isinstance(raw, str):
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    raise HikerError("HikerAPI unreadable")
