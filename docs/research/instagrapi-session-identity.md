# Can instagrapi persist Session identity and read a Post?

**Ticket:** [Can instagrapi persist Session identity and read a Post?](https://github.com/Grsmto/insta-bot/issues/2)
**Map:** [Unofficial Instagram commenter](https://github.com/Grsmto/insta-bot/issues/1)
**Library:** [subzeroid/instagrapi](https://github.com/subzeroid/instagrapi) (unofficial Instagram private/web API wrapper)
**Pinned revision:** [`d5b72324b2b00cc0c922b4c7a631d96f42e7b88e`](https://github.com/subzeroid/instagrapi/commit/d5b72324b2b00cc0c922b4c7a631d96f42e7b88e) — tagged in-repo as **2.18.17** (2026-08-22). Docs pages below are the first-party GitHub Pages site generated from that repo.

This note reports what the library **actually exposes**. It is not a recommendation to pick it. No live Instagram client was run.

Domain words used as in `CONTEXT.md`: **Account**, **Session identity**, **Post**, **Comment**.

## Verdict

| Need | Result | One line |
| --- | --- | --- |
| Persist Session identity across process restarts | **Yes** | `dump_settings` / `load_settings` reuse device UUIDs, user agent, cookies, and authorization data. |
| Log in as an Account | **Yes** | `login(username, password)` is the documented long-lived path; `login_by_sessionid` is a compatibility path. |
| 2FA / challenge handling | **Partial** | TOTP and 8-digit backup codes are supported on `login()`; email/SMS challenge handlers exist; several newer checkpoints are documented as manual. |
| Read Post caption | **Yes** | `Media.caption_text` from `media_info` / `user_medias`. |
| Read Post image URL(s) | **Yes** | `Media.thumbnail_url`, `image_versions2.candidates[].url`, album `Media.resources[].thumbnail_url`. |
| Read recent Comments | **Yes** | `media_comments` (default 20) plus chunked / GraphQL variants. |
| Post a Comment | **Yes** | `media_comment(...)` returns a `Comment` with `pk`. |
| Post permalink | **Partial** | Library documents `/p/{code}/` and returns `Media.code`; no `url` / permalink field on `Media`. |
| Comment permalink | **Partial** | `Comment.pk` is returned; no Comment URL helper is documented. |
| Stable Session identity (no rotating fingerprint) | **Yes, if you persist and do not reset** | A fresh `Client()` without `load_settings` generates new UUIDs; `set_device(reset=True)` / `set_user_agent(reset=True)` also regenerate them. |

**Overall:** **Yes, with gaps.** instagrapi can log in as an Account, persist a Session identity across hourly process restarts, read a Post's caption, image URL(s), and recent Comments, and post a Comment whose `pk` is returned. Post URL is constructible from the documented `code`. Comment URL is not returned or documented. The maintainers treat this as an unofficial private API and document rate limits, challenges, and ban/trust risk.

## Sources

First-party only:

- Repo README: <https://github.com/subzeroid/instagrapi/blob/d5b72324b2b00cc0c922b4c7a631d96f42e7b88e/README.md>
- Official docs index: <https://subzeroid.github.io/instagrapi/>
- Interactions (login + settings): <https://subzeroid.github.io/instagrapi/usage-guide/interactions.html>
- Best practices (sessions, rate limits, bans): <https://subzeroid.github.io/instagrapi/usage-guide/best-practices.html>
- Media (Post): <https://subzeroid.github.io/instagrapi/usage-guide/media.html>
- Comment: <https://subzeroid.github.io/instagrapi/usage-guide/comment.html>
- TOTP / 2FA: <https://subzeroid.github.io/instagrapi/usage-guide/totp.html>
- Challenge resolver: <https://subzeroid.github.io/instagrapi/usage-guide/challenge_resolver.html>
- Handle exceptions: <https://github.com/subzeroid/instagrapi/blob/d5b72324b2b00cc0c922b4c7a631d96f42e7b88e/docs/usage-guide/handle_exception.md>
- Types: <https://github.com/subzeroid/instagrapi/blob/d5b72324b2b00cc0c922b4c7a631d96f42e7b88e/docs/usage-guide/types.md>
- Source: [`instagrapi/mixins/auth.py`](https://github.com/subzeroid/instagrapi/blob/d5b72324b2b00cc0c922b4c7a631d96f42e7b88e/instagrapi/mixins/auth.py), [`instagrapi/mixins/comment.py`](https://github.com/subzeroid/instagrapi/blob/d5b72324b2b00cc0c922b4c7a631d96f42e7b88e/instagrapi/mixins/comment.py), [`instagrapi/mixins/media.py`](https://github.com/subzeroid/instagrapi/blob/d5b72324b2b00cc0c922b4c7a631d96f42e7b88e/instagrapi/mixins/media.py), [`instagrapi/types.py`](https://github.com/subzeroid/instagrapi/blob/d5b72324b2b00cc0c922b4c7a631d96f42e7b88e/instagrapi/types.py), [`instagrapi/extractors.py`](https://github.com/subzeroid/instagrapi/blob/d5b72324b2b00cc0c922b4c7a631d96f42e7b88e/instagrapi/extractors.py)
- Example: [`examples/session_login.py`](https://github.com/subzeroid/instagrapi/blob/d5b72324b2b00cc0c922b4c7a631d96f42e7b88e/examples/session_login.py)

## 1. Session persistence

**Yes.** The library is built to reuse one device/session file across process restarts.

### What is saved

`get_settings()` serializes, and `dump_settings(path)` writes as JSON ([`auth.py`](https://github.com/subzeroid/instagrapi/blob/d5b72324b2b00cc0c922b4c7a631d96f42e7b88e/instagrapi/mixins/auth.py)):

- **Device UUIDs** under `uuids`: `phone_id`, `uuid`, `client_session_id`, `advertising_id`, `android_device_id`, `request_id`, `tray_session_id`
- **Cookies** from the private session (`requests.utils.dict_from_cookiejar`)
- **Authorization data** (`authorization_data`: sessionid / ds_user_id / related values)
- **Device settings** (`device_settings`: Android model, dpi, resolution, manufacturer, android version, plus app profile fields)
- **User agent** (`user_agent`)
- Locale / country / timezone, retry/TLS/public-transport knobs, `last_login`, optional `usdid` / `fbns_auth`

The Interactions docs show the same shape (uuids, authorization_data, cookies, device_settings, user_agent) and the same dump/load methods ([Interactions](https://subzeroid.github.io/instagrapi/usage-guide/interactions.html)).

### Can the same UUID, user agent, and cookies be reused?

**Yes, if you load the dumped file before `login()`.**

Documented hourly-run pattern ([README](https://github.com/subzeroid/instagrapi/blob/d5b72324b2b00cc0c922b4c7a631d96f42e7b88e/README.md), [Best Practices](https://subzeroid.github.io/instagrapi/usage-guide/best-practices.html), [`examples/session_login.py`](https://github.com/subzeroid/instagrapi/blob/d5b72324b2b00cc0c922b4c7a631d96f42e7b88e/examples/session_login.py)):

1. First run: `Client()` → `login(username, password)` → `dump_settings("session.json")`
2. Later runs: `Client()` → `load_settings("session.json")` → `login(username, password)` → `dump_settings("session.json")` again (in case the session was refreshed)

`load_settings` reads the JSON and calls `set_settings` → `init()` ([`auth.py`](https://github.com/subzeroid/instagrapi/blob/d5b72324b2b00cc0c922b4c7a631d96f42e7b88e/instagrapi/mixins/auth.py)). `init()` restores cookies, authorization_data, `set_device(device_settings)`, `set_user_agent(user_agent)`, and `set_uuids(uuids)`.

`set_uuids` **reuses** each key present in the loaded dict; it only calls `generate_uuid()` / `generate_android_device_id()` for missing keys. A complete dump therefore keeps the same device UUID set.

`login()` validates a loaded session with `account_info()` when `user_id` is already present. On `LoginRequired` it clears **authorization and cookies only** (`_clear_session_state`) and logs in again with the supplied credentials — it does **not** regenerate device UUIDs ([`auth.py`](https://github.com/subzeroid/instagrapi/blob/d5b72324b2b00cc0c922b4c7a631d96f42e7b88e/instagrapi/mixins/auth.py)). That matches the Session identity constraint: same device identity across hourly runs, even if cookies must be refreshed.

### What rotates the fingerprint (avoid)

- A new `Client()` **without** `load_settings` starts with empty settings; `set_uuids({})` generates new UUIDs.
- `set_device(..., reset=True)` and `set_user_agent(..., reset=True)` call `set_uuids({})` and therefore mint a new device identity ([`auth.py`](https://github.com/subzeroid/instagrapi/blob/d5b72324b2b00cc0c922b4c7a631d96f42e7b88e/instagrapi/mixins/auth.py)).
- Best Practices list “logging in with username/password on every script run” and “switching proxies after every request” as anti-patterns, and say to persist sessions and device identifiers ([Best Practices](https://subzeroid.github.io/instagrapi/usage-guide/best-practices.html)).

Maintainers' own rule for Session identity: “Reuse a stable device profile and one stable IP… Persist sessions and device identifiers; avoid password login from scratch on every run” ([Best Practices](https://subzeroid.github.io/instagrapi/usage-guide/best-practices.html), [Interactions](https://subzeroid.github.io/instagrapi/usage-guide/interactions.html)).

## 2. Login

### Username / password — **Yes**

`Client.login(username, password)` is the documented Account login ([README](https://github.com/subzeroid/instagrapi/blob/d5b72324b2b00cc0c922b4c7a631d96f42e7b88e/README.md), [Interactions](https://subzeroid.github.io/instagrapi/usage-guide/interactions.html)). After a valid saved session is loaded, `login()` reuses it instead of sending a fresh password login; if Instagram returns `login_required`, it clears stale authorization and logs in again with the supplied credentials ([README](https://github.com/subzeroid/instagrapi/blob/d5b72324b2b00cc0c922b4c7a631d96f42e7b88e/README.md), [`auth.py`](https://github.com/subzeroid/instagrapi/blob/d5b72324b2b00cc0c922b4c7a631d96f42e7b88e/instagrapi/mixins/auth.py)).

The documented reuse path still **takes username and password** so a rejected session can be replaced. `relogin()` is `login(..., relogin=True)` and requires `cl.username` and `cl.password` ([Interactions](https://subzeroid.github.io/instagrapi/usage-guide/interactions.html)).

### sessionid — **Partial** (supported, not recommended for long-lived Session identity)

`login_by_sessionid(sessionid)` exists ([Interactions](https://subzeroid.github.io/instagrapi/usage-guide/interactions.html), [`auth.py`](https://github.com/subzeroid/instagrapi/blob/d5b72324b2b00cc0c922b4c7a631d96f42e7b88e/instagrapi/mixins/auth.py)). Maintainers call it a “lightweight compatibility path.” A browser/web `sessionid` can be rejected with `login_required`. For long-lived automation they tell you to do one password `login()`, `dump_settings()`, and reuse that file — not to keep importing browser cookies ([README](https://github.com/subzeroid/instagrapi/blob/d5b72324b2b00cc0c922b4c7a631d96f42e7b88e/README.md), [Interactions](https://subzeroid.github.io/instagrapi/usage-guide/interactions.html)).

### 2FA — **Yes** (describe only; no bypass)

- `login(username, password, verification_code="123456")` — TOTP from an authenticator; “not work with SMS” on this parameter ([Interactions](https://subzeroid.github.io/instagrapi/usage-guide/interactions.html)).
- Same `verification_code` accepts **8-digit backup codes** ([README](https://github.com/subzeroid/instagrapi/blob/d5b72324b2b00cc0c922b4c7a631d96f42e7b88e/README.md), [TOTP](https://subzeroid.github.io/instagrapi/usage-guide/totp.html)).
- Helpers: `totp_generate_seed`, `totp_enable`, `totp_disable`, `totp_generate_code` ([TOTP](https://subzeroid.github.io/instagrapi/usage-guide/totp.html)).
- Newer CAA/Bloks two-factor: `login(..., verification_code=...)` tries the legacy `accounts/two_factor_login/` endpoint first, then retries through Bloks when Instagram returns `two_step_verification_context` ([TOTP](https://subzeroid.github.io/instagrapi/usage-guide/totp.html), [`auth.py`](https://github.com/subzeroid/instagrapi/blob/d5b72324b2b00cc0c922b4c7a631d96f42e7b88e/instagrapi/mixins/auth.py)). If no code is supplied, it raises `TwoFactorRequired`.

### Challenge — **Partial** (handlers exist; some flows are manual)

`challenge_code_handler` (email/SMS code) and `change_password_handler` can be attached; `challenge_resolve(...)` is the hook used by the exception handler ([Challenge Resolver](https://subzeroid.github.io/instagrapi/usage-guide/challenge_resolver.html), [handle_exception.md](https://github.com/subzeroid/instagrapi/blob/d5b72324b2b00cc0c922b4c7a631d96f42e7b88e/docs/usage-guide/handle_exception.md)).

Documented as **not** automatically solved (no bypass described here; this is what they document):

- `/auth_platform/` APC flows — “not yet supported automatically”
- Native `challenge.native_flow=true` checkpoints — no SMS/email/password step
- Bloks redirect checkpoints — “require manual confirmation in the official Instagram app or web flow”
- `ChallengeSelfieCaptcha` / selfie / manual-review — “does not provide a generic bypass”

They tell you to persist settings around challenge handling so the device/session is not rebuilt ([Challenge Resolver](https://subzeroid.github.io/instagrapi/usage-guide/challenge_resolver.html)).

## 3. Read a Post

instagrapi calls a Post **Media**. Docs: “In terms of Instagram, this is called Media, usually users call it publications or posts” ([Media](https://subzeroid.github.io/instagrapi/usage-guide/media.html)).

### Caption — **Yes**

- Field: `Media.caption_text` ([`types.py`](https://github.com/subzeroid/instagrapi/blob/d5b72324b2b00cc0c922b4c7a631d96f42e7b88e/instagrapi/types.py), [Types](https://github.com/subzeroid/instagrapi/blob/d5b72324b2b00cc0c922b4c7a631d96f42e7b88e/docs/usage-guide/types.md)).
- Filled from private API `caption.text` in `extract_media_v1` ([`extractors.py`](https://github.com/subzeroid/instagrapi/blob/d5b72324b2b00cc0c922b4c7a631d96f42e7b88e/instagrapi/extractors.py)).
- Methods that return `Media`: `media_info(media_pk)`, `user_medias(user_id, amount)`, paginated / iterator variants ([Media](https://subzeroid.github.io/instagrapi/usage-guide/media.html)). Docs example shows `caption_text` populated.

### Image URL(s) — **Yes**

On `Media` ([`types.py`](https://github.com/subzeroid/instagrapi/blob/d5b72324b2b00cc0c922b4c7a631d96f42e7b88e/instagrapi/types.py)):

- `thumbnail_url` — largest `image_versions2.candidates` URL (`extract_media_v1` sorts by `height * width` and takes the last) ([`extractors.py`](https://github.com/subzeroid/instagrapi/blob/d5b72324b2b00cc0c922b4c7a631d96f42e7b88e/instagrapi/extractors.py)).
- `image_versions2.candidates[].url` — full candidate list (`SharedMediaImageCandidate.url`).
- Albums (`media_type == 8`): top-level `thumbnail_url` is **removed**; per-slide URLs live on `Media.resources[]` as `Resource.thumbnail_url` / `video_url` ([`extractors.py`](https://github.com/subzeroid/instagrapi/blob/d5b72324b2b00cc0c922b4c7a631d96f42e7b88e/instagrapi/extractors.py), [Media](https://subzeroid.github.io/instagrapi/usage-guide/media.html) example).
- Download helpers: `photo_download(media_pk)`, `album_download(media_pk)` ([Media](https://subzeroid.github.io/instagrapi/usage-guide/media.html)).

These are CDN image URLs, not a Post permalink.

### Recent Comments — **Yes**

Exact method names ([Comment](https://subzeroid.github.io/instagrapi/usage-guide/comment.html), [`comment.py`](https://github.com/subzeroid/instagrapi/blob/d5b72324b2b00cc0c922b4c7a631d96f42e7b88e/instagrapi/mixins/comment.py)):

| Method | Returns | Role |
| --- | --- | --- |
| `media_comments(media_id, amount=20)` | `List[Comment]` | High-level recent Comments; `amount=0` paginates until exhaustion |
| `media_comments_chunk(media_id, max_amount, min_id=None)` | `(List[Comment], str)` | Resume via cursor |
| `media_comments_v1` / `media_comments_v1_chunk` | `List[Comment]` / chunk | Private mobile comments endpoint |
| `media_comments_gql` / `media_comments_gql_chunk` | `List[dict]` | Web GraphQL |
| `media_comments_public_gql` / `_chunk` | `List[dict]` | Public web GraphQL by shortcode |
| `media_comment_replies` / `_chunk` | `List[Comment]` | Threaded replies |

`Comment` fields: `pk`, `text`, `user`, `created_at_utc`, `content_type`, `status`, optional `replied_to_comment_id`, `has_liked`, `like_count` ([`types.py`](https://github.com/subzeroid/instagrapi/blob/d5b72324b2b00cc0c922b4c7a631d96f42e7b88e/instagrapi/types.py)).

`Media` may also carry `comments_preview` (inline parent Comments already in the media payload). Docs say to use the full comments helpers for complete pagination ([Media](https://subzeroid.github.io/instagrapi/usage-guide/media.html)).

## 4. Post a Comment

**Yes.** `media_comment(media_id, text, replied_to_comment_id=None) -> Comment` ([Comment](https://subzeroid.github.io/instagrapi/usage-guide/comment.html), [`comment.py`](https://github.com/subzeroid/instagrapi/blob/d5b72324b2b00cc0c922b4c7a631d96f42e7b88e/instagrapi/mixins/comment.py)).

The implementation posts to the private `media/{media_id}/comment/` endpoint and returns `extract_comment(result["comment"])`. Docs example shows the returned object includes **`pk`** (e.g. `17926777897585108`), `text`, `user`, `created_at_utc`, `status`.

So a Comment **pk/id is returned**. That is enough to *build* a Comment URL if you also have the Post shortcode — the library itself does not do that (see §5).

Related write helpers (not required for the ticket): `media_check_offensive_comment` / `_v2` (optional preflight; `media_comment` does **not** run them automatically), `comment_like` / `comment_unlike`, `comment_bulk_delete`. Docs: “Comment creation is a write action and can still trigger Instagram spam or trust checks” ([Comment](https://subzeroid.github.io/instagrapi/usage-guide/comment.html)).

## 5. Post URL construction

**Partial.**

Documented identifiers ([Media](https://subzeroid.github.io/instagrapi/usage-guide/media.html)):

- `code` — shortcode / slug, e.g. `BjNLpA1AhXM` from `https://www.instagram.com/p/BjNLpA1AhXM/`
- `url` — described as “URL to media publication” with that same `/p/{code}/` example
- Helpers: `media_pk_from_url(url)`, `media_code_from_pk(media_pk)`, `media_pk_from_code(code)` ([`media.py`](https://github.com/subzeroid/instagrapi/blob/d5b72324b2b00cc0c922b4c7a631d96f42e7b88e/instagrapi/mixins/media.py))

`Media` in source has `code` and **no** `url` / permalink field ([`types.py`](https://github.com/subzeroid/instagrapi/blob/d5b72324b2b00cc0c922b4c7a631d96f42e7b88e/instagrapi/types.py)). There is no `media_url(...)` helper. A Post permalink is therefore **constructed by the caller** from the documented pattern `https://www.instagram.com/p/{media.code}/`.

`media_oembed(url)` takes a Post URL and returns short oEmbed-style info (`MediaOembed`), including `thumbnail_url` — it consumes a permalink, it does not produce one ([Media](https://subzeroid.github.io/instagrapi/usage-guide/media.html)).

**Comment URL:** not documented. `Comment` has `pk` only; no permalink field or helper in the Comment docs or `Comment` type.

## 6. Gaps vs our need

Need: persist Session identity → log in as Account → read Post caption + image + recent Comments → post a Comment → return URLs to the Post and the Comment.

| Need | Covered? | Gap |
| --- | --- | --- |
| Stable Session identity across hourly runs | **Yes** | Only if `dump_settings` / `load_settings` is used and `reset=True` is never called. Fresh `Client()` without load rotates UUIDs. Maintainers also want a **stable IP/proxy** per Account; the library does not persist that for you. |
| Log in as Account | **Yes** | Password still needed on the documented reuse path as fallback. `login_by_sessionid` is weaker for long-lived identity. |
| 2FA / checkpoint | **Partial** | TOTP/backup supported; several challenge types are manual. Map fog already lists this. |
| Caption | **Yes** | — |
| Image URL(s) | **Yes** | Album images are on `resources[]`, not top-level `thumbnail_url`. CDN URLs expire independently of the library. |
| Recent Comments | **Yes** | Default `amount=20`. |
| Post a Comment | **Yes** | Write action; maintainers document spam/trust / `FeedbackRequired` risk. |
| Post URL | **Partial** | Build from `Media.code` using the documented `/p/{code}/` pattern. No permalink field. |
| Comment URL | **Partial** | `Comment.pk` only. No documented permalink helper — a Comment record that stores a Comment URL would have to invent the URL scheme outside this library. |

Nothing in the public API blocks the read + comment loop on paper. The Comment URL and unofficial-API operational risk are the main gaps against a Comment record of “text + Post URL + Comment URL.”

## 7. Limitations the maintainers document

Only what they write, not third-party commentary.

**Unofficial / private API**

- “Fast and effective unofficial Instagram API wrapper.” Combines public web and private mobile flows ([README](https://github.com/subzeroid/instagrapi/blob/d5b72324b2b00cc0c922b4c7a631d96f42e7b88e/README.md)).
- “Private API automation is fragile in production because account trust, proxies, device state, challenges, and rate limits can change independently of the library.” Prefer official Instagram APIs for account-owned business workflows. “Best suited for testing, research, and controlled internal automation” ([README](https://github.com/subzeroid/instagrapi/blob/d5b72324b2b00cc0c922b4c7a631d96f42e7b88e/README.md)).
- Public/web paths are “opportunistic rather than guaranteed” ([README](https://github.com/subzeroid/instagrapi/blob/d5b72324b2b00cc0c922b4c7a631d96f42e7b88e/README.md), [Fundamentals](https://subzeroid.github.io/instagrapi/usage-guide/fundamentals.html)).
- Device-bound attestation headers (`x-meta-zca`, `x-meta-usdid`, `x-ig-attest-params`) are **not** generated; fake static values “are more likely to hurt trust than help” ([Interactions](https://subzeroid.github.io/instagrapi/usage-guide/interactions.html)).

**Rate limits and anti-abuse** ([Best Practices](https://subzeroid.github.io/instagrapi/usage-guide/best-practices.html), [handle_exception.md](https://github.com/subzeroid/instagrapi/blob/d5b72324b2b00cc0c922b4c7a631d96f42e7b88e/docs/usage-guide/handle_exception.md))

| Signal | What they say to do |
| --- | --- |
| `ClientThrottledError` / HTTP 429 | Stop the burst, back off, reduce concurrency. Public 429 ≠ broken mobile session. |
| `PleaseWaitFewMinutes` | More serious; stop writes; keep the same device settings; retry later. |
| `FeedbackRequired` | Action blocked / temporary restriction; inspect `feedback_message`; freeze that action. |
| `LoginRequired` | Relogin with the **same** saved device/session state. |
| `ChallengeRequired` | Use `challenge_resolve` only if handlers exist; some flows need the official app. |

They recommend `cl.delay_range = [1, 3]`, one stable proxy/IP per Account, warmup before write-heavy actions (comments included), and not retrying 429 / `PleaseWaitFewMinutes` / `FeedbackRequired` / challenges in a tight loop ([Best Practices](https://subzeroid.github.io/instagrapi/usage-guide/best-practices.html)).

**Bans / trust / comments**

- Best Practices title: “so that you don’t get rate limited or banned.”
- Suspicious-login screens are “trust signals… not reliable to ‘bypass’ generically from the library.”
- “Keep this account separate from write-heavy actions such as follows, likes, comments, uploads, and Direct messages” when doing read-only monitoring ([Best Practices](https://subzeroid.github.io/instagrapi/usage-guide/best-practices.html)).
- Comment creation “can still trigger Instagram spam or trust checks. Reuse saved sessions, keep volume low on new accounts, and stop when Instagram returns feedback/challenge responses” ([Comment](https://subzeroid.github.io/instagrapi/usage-guide/comment.html)).
- Our planned 1–3 Comments/hour is in the same direction as their “keep early write actions low” guidance; they do not publish a numeric comment quota.

**Read-only monitoring example**

For “small jobs that only check whether selected users posted new media,” they tell you to reuse one saved session, poll on a moderate interval (“several minutes rather than seconds”), and store last-seen media ids locally ([Best Practices](https://subzeroid.github.io/instagrapi/usage-guide/best-practices.html)). That is the closest first-party match to an hourly Watch list check — they still treat **commenting** as a separate, riskier write path.
