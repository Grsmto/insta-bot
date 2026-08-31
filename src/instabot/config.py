from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    instagram_username: str
    instagram_password: str
    hikerapi_key: str
    openrouter_api_key: str
    database_path: Path
    session_path: Path
    comments_per_hour: int
    max_post_age_hours: int

    @classmethod
    def from_env(cls) -> Config:
        return cls(
            instagram_username=_required("INSTAGRAM_USERNAME"),
            instagram_password=_required("INSTAGRAM_PASSWORD"),
            hikerapi_key=_required("HIKERAPI_KEY"),
            openrouter_api_key=_required("OPENROUTER_API_KEY"),
            database_path=Path(_required("DATABASE_PATH")),
            session_path=Path(_required("SESSION_PATH")),
            comments_per_hour=_int("COMMENTS_PER_HOUR", 2),
            max_post_age_hours=_int("MAX_POST_AGE_HOURS", 24),
        )


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"missing {name}")
    return value


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return int(raw)
