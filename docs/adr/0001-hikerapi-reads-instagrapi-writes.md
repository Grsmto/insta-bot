# HikerAPI for Watch list reads, instagrapi for Comment writes

Hourly Watch list polling is high-volume and would put the Account at ban risk if it talked to Instagram directly. Posting a Comment must still happen as the Account. We read public Watch list Posts (caption, image, recent Comments) through HikerAPI, and post Comments through instagrapi with a persisted Session identity. If HikerAPI fails, the run fails or skips — we do not fall back to reading as the Account. Camoufox is not in the spec. Private Watch list profiles are out of scope.

## Considered Options

- **instagrapi for reads and writes** — one client, but the hourly poll uses the Account.
- **Camoufox** — anti-detect browser, not an Instagram API; reads and comments would be custom automation.
- **HikerAPI for reads and writes** — HikerAPI is GET-only; it cannot post a Comment.
