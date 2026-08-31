# insta-bot

Single-Account Instagram commenter HTTP service.

```bash
cp .env.example .env
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn instabot.app:create_production_app --factory
```

`POST /run` performs one check-and-comment cycle for the Account in `.env`.
The Watch list is seeded from `src/instabot/watch_list.json` into the SQLite file at `DATABASE_PATH`.
