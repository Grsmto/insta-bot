from __future__ import annotations

import json
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS account (
    username TEXT NOT NULL PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS watched_profile (
    pk TEXT NOT NULL PRIMARY KEY,
    username TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS comment_record (
    post_pk TEXT NOT NULL PRIMARY KEY,
    comment_text TEXT NOT NULL,
    post_url TEXT NOT NULL,
    post_code TEXT NOT NULL,
    comment_pk TEXT NOT NULL
);
"""


def connect(database_path: Path) -> sqlite3.Connection:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def bind_or_refuse(conn: sqlite3.Connection, username: str) -> bool:
    row = conn.execute("SELECT username FROM account LIMIT 1").fetchone()
    if row is None:
        conn.execute("INSERT INTO account (username) VALUES (?)", (username,))
        conn.commit()
        return True
    return str(row["username"]) == username


def seed_watch_list(conn: sqlite3.Connection, seed_path: Path) -> None:
    existing = conn.execute("SELECT COUNT(*) AS n FROM watched_profile").fetchone()
    if existing is not None and int(existing["n"]) > 0:
        return
    profiles = json.loads(seed_path.read_text())
    conn.executemany(
        "INSERT INTO watched_profile (pk, username) VALUES (?, ?)",
        [(str(p["pk"]), str(p["username"])) for p in profiles],
    )
    conn.commit()


def watch_list(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    rows = conn.execute(
        "SELECT pk, username FROM watched_profile ORDER BY pk"
    ).fetchall()
    return [(str(r["pk"]), str(r["username"])) for r in rows]


def commented_post_pks(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT post_pk FROM comment_record").fetchall()
    return {str(r["post_pk"]) for r in rows}


def watch_list_seed_path() -> Path:
    return Path(__file__).with_name("watch_list.json")
