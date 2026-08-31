from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from instabot.app import create_app
from instabot.db import watch_list_seed_path
from instabot.hiker import HikerError, Post

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)

_seed = json.loads(watch_list_seed_path().read_text())
SEEDED_ONE_PK = str(_seed[0]["pk"])
SEEDED_TWO_PK = str(_seed[1]["pk"])


class FakeHiker:
    def __init__(
        self,
        posts_by_pk: dict[str, list[Post]] | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self.posts_by_pk = posts_by_pk or {}
        self.error = error
        self.requested_pks: list[str] = []

    def fetch_posts(self, watched_profile_pk: str) -> list[Post]:
        if self.error is not None:
            raise self.error
        self.requested_pks.append(watched_profile_pk)
        return list(self.posts_by_pk.get(watched_profile_pk, []))


def _env(tmp_path: Path, username: str = "alice") -> dict[str, str]:
    return {
        "INSTAGRAM_USERNAME": username,
        "INSTAGRAM_PASSWORD": "secret",
        "HIKERAPI_KEY": "hiker-test",
        "OPENROUTER_API_KEY": "or-test",
        "DATABASE_PATH": str(tmp_path / "account.db"),
        "SESSION_PATH": str(tmp_path / "session.json"),
        "COMMENTS_PER_HOUR": "2",
        "MAX_POST_AGE_HOURS": "24",
    }


def _client(tmp_path: Path, monkeypatch, hiker: FakeHiker, username: str = "alice") -> TestClient:
    for key, value in _env(tmp_path, username).items():
        monkeypatch.setenv(key, value)
    return TestClient(create_app(hiker=hiker, now=lambda: NOW))


def _write_session(tmp_path: Path, body: bytes = b'{"sentinel": true}') -> Path:
    path = tmp_path / "session.json"
    path.write_bytes(body)
    return path


def _sqlite(tmp_path: Path) -> dict:
    db = sqlite3.connect(tmp_path / "account.db")
    db.row_factory = sqlite3.Row
    return {
        "account": list(db.execute("SELECT username FROM account")),
        "watch_list": list(db.execute("SELECT pk, username FROM watched_profile ORDER BY pk")),
        "comment_records": list(db.execute("SELECT post_pk FROM comment_record")),
    }


def test_quiet_watch_list_returns_counts_and_does_not_touch_session(tmp_path, monkeypatch) -> None:
    session = _write_session(tmp_path)
    before = session.read_bytes()
    hiker = FakeHiker(
        {
            SEEDED_ONE_PK: [
                Post(pk="old1", taken_at=NOW - timedelta(hours=25), caption="old"),
            ],
            SEEDED_TWO_PK: [],
        }
    )
    client = _client(tmp_path, monkeypatch, hiker)

    response = client.post("/run")

    assert response.status_code == 200
    assert response.json() == {
        "new_posts_found": 0,
        "comments_posted": 0,
        "failed": False,
    }
    assert session.read_bytes() == before
    rows = _sqlite(tmp_path)
    assert rows["account"][0]["username"] == "alice"
    assert [tuple(r) for r in rows["watch_list"]] == [
        (str(p["pk"]), str(p["username"])) for p in _seed
    ]
    assert hiker.requested_pks == [SEEDED_ONE_PK, SEEDED_TWO_PK]


def test_refuses_when_env_username_does_not_match_bound_username(tmp_path, monkeypatch) -> None:
    hiker = FakeHiker()
    _client(tmp_path, monkeypatch, hiker, username="alice").post("/run")
    hiker.requested_pks.clear()
    session = _write_session(tmp_path)
    before = session.read_bytes()
    client = _client(tmp_path, monkeypatch, hiker, username="bob")

    response = client.post("/run")

    assert response.status_code == 409
    body = response.json()
    assert body["failed"] is True
    assert body["new_posts_found"] == 0
    assert body["comments_posted"] == 0
    assert hiker.requested_pks == []
    assert session.read_bytes() == before


def test_hikerapi_failure_fails_the_run_without_touching_session(tmp_path, monkeypatch) -> None:
    session = _write_session(tmp_path)
    before = session.read_bytes()
    hiker = FakeHiker(error=HikerError("down"))
    client = _client(tmp_path, monkeypatch, hiker)

    response = client.post("/run")

    assert response.status_code == 502
    body = response.json()
    assert body["failed"] is True
    assert body["comments_posted"] == 0
    assert session.read_bytes() == before


def test_counts_new_posts_inside_age_window_and_does_not_post(tmp_path, monkeypatch) -> None:
    session = _write_session(tmp_path)
    before = session.read_bytes()
    hiker = FakeHiker(
        {
            SEEDED_ONE_PK: [
                Post(pk="new1", taken_at=NOW - timedelta(hours=23), caption="hi", image_url="http://img"),
                Post(pk="old1", taken_at=NOW - timedelta(hours=24, seconds=1)),
            ],
            SEEDED_TWO_PK: [
                Post(pk="new2", taken_at=NOW - timedelta(hours=1)),
            ],
        }
    )
    client = _client(tmp_path, monkeypatch, hiker)

    response = client.post("/run")

    assert response.status_code == 200
    assert response.json() == {
        "new_posts_found": 2,
        "comments_posted": 0,
        "failed": False,
    }
    assert session.read_bytes() == before


def test_post_with_comment_record_is_not_a_new_post(tmp_path, monkeypatch) -> None:
    hiker = FakeHiker(
        {
            SEEDED_ONE_PK: [
                Post(pk="already", taken_at=NOW - timedelta(hours=1)),
                Post(pk="fresh", taken_at=NOW - timedelta(minutes=10)),
            ],
        }
    )
    client = _client(tmp_path, monkeypatch, hiker)
    client.post("/run")
    db = sqlite3.connect(tmp_path / "account.db")
    db.execute(
        """
        INSERT INTO comment_record (post_pk, comment_text, post_url, post_code, comment_pk)
        VALUES ('already', 'bora!', 'https://www.instagram.com/p/AAA/', 'AAA', 'c1')
        """
    )
    db.commit()
    db.close()

    response = client.post("/run")

    assert response.status_code == 200
    assert response.json()["new_posts_found"] == 1
    assert response.json()["comments_posted"] == 0
    assert response.json()["failed"] is False


def test_missing_session_file_stays_missing_on_quiet_run(tmp_path, monkeypatch) -> None:
    hiker = FakeHiker()
    client = _client(tmp_path, monkeypatch, hiker)

    response = client.post("/run")

    assert response.status_code == 200
    assert response.json()["new_posts_found"] == 0
    assert not (tmp_path / "session.json").exists()


def test_age_window_uses_max_post_age_hours_from_env(tmp_path, monkeypatch) -> None:
    hiker = FakeHiker(
        {
            SEEDED_ONE_PK: [
                Post(pk="inside", taken_at=NOW - timedelta(hours=2)),
                Post(pk="outside", taken_at=NOW - timedelta(hours=4)),
            ],
        }
    )
    for key, value in _env(tmp_path).items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("MAX_POST_AGE_HOURS", "3")
    client = TestClient(create_app(hiker=hiker, now=lambda: NOW))

    response = client.post("/run")

    assert response.json()["new_posts_found"] == 1
