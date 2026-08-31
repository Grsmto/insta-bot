from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Callable

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from instabot import db
from instabot.config import Config
from instabot.hiker import HikerApiClient, HikerError, Post, WatchListReader


class RunOutcome(BaseModel):
    new_posts_found: int
    comments_posted: int
    failed: bool


def create_app(
    *,
    hiker: WatchListReader | None = None,
    now: Callable[[], datetime] | None = None,
) -> FastAPI:
    app = FastAPI()
    clock = now or (lambda: datetime.now(timezone.utc))

    @app.post("/run")
    def run() -> JSONResponse:
        config = Config.from_env()
        conn = db.connect(config.database_path)
        try:
            if not db.bind_or_refuse(conn, config.instagram_username):
                return _outcome(409, 0, failed=True)
            db.seed_watch_list(conn, db.watch_list_seed_path())
            reader = hiker or HikerApiClient(config.hikerapi_key)
            try:
                new_posts = _new_posts(conn, reader, clock(), config.max_post_age_hours)
            except HikerError:
                return _outcome(502, 0, failed=True)
            return _outcome(200, len(new_posts), failed=False)
        finally:
            conn.close()

    return app


def create_production_app() -> FastAPI:
    from dotenv import load_dotenv

    load_dotenv()
    return create_app()


def _outcome(status: int, new_posts_found: int, *, failed: bool) -> JSONResponse:
    body = RunOutcome(
        new_posts_found=new_posts_found,
        comments_posted=0,
        failed=failed,
    )
    return JSONResponse(body.model_dump(), status_code=status)


def _new_posts(
    conn: sqlite3.Connection,
    reader: WatchListReader,
    now: datetime,
    max_post_age_hours: int,
) -> list[Post]:
    cutoff = now - timedelta(hours=max_post_age_hours)
    seen = db.commented_post_pks(conn)
    found: list[Post] = []
    for pk, _username in db.watch_list(conn):
        for post in reader.fetch_posts(pk):
            taken = post.taken_at
            if taken.tzinfo is None:
                taken = taken.replace(tzinfo=now.tzinfo)
            if taken >= cutoff and post.pk not in seen:
                found.append(post)
    return found
