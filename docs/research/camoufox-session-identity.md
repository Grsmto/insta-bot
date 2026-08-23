# Can Camoufox persist Session identity and read a Post?

**Ticket:** [Can Camoufox persist Session identity and read a Post?](https://github.com/Grsmto/insta-bot/issues/3)
**Verdict:** **Partial**

Camoufox can reuse a Playwright persistent browser profile (cookies and local storage) across process restarts, and it can drive pages with the Playwright API. A stable Session identity is **not** the default: each launch generates a fresh fingerprint unless we pin and reuse launch options / config. Camoufox is an anti-detect Firefox plus Playwright wrapper. It is not an Instagram API and does not read a Post or post a Comment.

This note reports what Camoufox documents and implements. It does not recommend picking Camoufox. It does not log into Instagram or automate instagram.com.

## Capability answers

| Need | Answer | Why |
| --- | --- | --- |
| Reuse the same browser profile (`user_data_dir` / persistent context) across hourly process restarts | **Yes** | Official Python API exposes `persistent_context` + `user_data_dir`; that path calls Playwright `firefox.launch_persistent_context`. Playwright stores cookies and local storage in that directory. |
| Keep a stable Session identity (cookies **and** fingerprint) across launches | **Partial** | Profile storage can persist cookies. Fingerprint is generated per launch by default. Navigator, WebGL, timezone, locale, and geolocation can be pinned via `config` / saved `launch_options`. JA3/JA4 is not a spoofable Camoufox property. |
| Open a site as an Account, read a Post (caption, image, recent comments), post a Comment, capture Post/Comment URLs | **No** (not a Camoufox feature) | Camoufox provides a browser and Playwright locators. Instagram DOM work would be custom automation on top. |
| Playwright locators / pages (navigate, read DOM, type, click) | **Yes** (Python official) | Drop-in Playwright wrapper. Node is official only via an experimental remote Playwright server; `camoufox-js` is community, not official. |
| Unattended hourly runs (headless, geoip, proxy) | **Partial** | Headless, virtual display, geoip, and Playwright `proxy` are documented. Default launch is headed. Remote `launch_server` does not persist `user_data_dir`. Project warns it may not be production-stable. |

## What Camoufox is

Camoufox is an open-source Firefox fork plus a Python Playwright wrapper, described as an “anti-detect browser built for webscraping & AI agents.” Latest docs live at camoufox.com; the GitHub README points there. The README also says the project is under development and “may not be suitable for stable production use.” The stealth page (2026) says there was a year-long maintenance gap, fingerprint inconsistencies were found, and development is active again.

Camoufox injects fingerprint data at the C++ implementation level (navigator, screen/window, geolocation/timezone/locale, WebRTC, WebGL, fonts). Unset config keys are filled by BrowserForge so each run can look like a plausible device drawn from real-world traffic. The README’s product framing is the opposite of a sticky Session identity: “Every run gets a fresh identity.”

Sources: [daijro/camoufox README](https://github.com/daijro/camoufox/blob/main/README.md), [camoufox.com](https://camoufox.com/), [camoufox.com/stealth](https://camoufox.com/stealth).

## 1. Persistent user profile

**Yes — the same Playwright profile directory can be reused across process restarts.**

Official usage docs:

```python
with Camoufox(
    persistent_context=True,
    user_data_dir='/path/to/profile/dir',
) as context:
    ...
```

`persistent_context` “create[s] a persistent context” and “Requires `user_data_dir`.”

The Python wrapper implements that by calling Playwright, not a Camoufox-specific store. `NewBrowser` in `pythonlib/camoufox/sync_api.py` does:

```python
if persistent_context:
    context = playwright.firefox.launch_persistent_context(**from_options)
    return sync_attach_vd(context, virtual_display)
```

Playwright owns what that directory holds. `BrowserType.launch_persistent_context` “Launches browser that uses persistent storage located at user_data_dir.” The `user_data_dir` argument is “Path to a User Data Directory, which stores browser session data like cookies and local storage.” Playwright also documents that browsers do not allow two instances on the same user data directory at once.

So: hourly stop/start of one process against the same `user_data_dir` can keep cookies and local storage. That is the Account-login cookie half of Session identity. It is not the fingerprint half (next section).

`user_data_dir` is accepted because `launch_options()` forwards leftover kwargs into the Playwright launch dict (`**launch_options`).

**Remote server gap.** Official remote-server docs let other languages connect with Playwright `firefox.connect`. Maintainer triage on [daijro/camoufox#253](https://github.com/daijro/camoufox/issues/253) states `launch_server()` wraps Playwright `firefox.launchServer()`, which has no persistent-context mode, so `persistent_context` / `user_data_dir` are ignored. Persistence is client-side `launch_persistent_context` only. A persistent Playwright server mode is tracked as a feature request ([#161](https://github.com/daijro/camoufox/issues/161), PR [#398](https://github.com/daijro/camoufox/pull/398)).

Sources: [Usage — persistent_context](https://camoufox.com/python/usage/), [`sync_api.py` on daijro/camoufox](https://github.com/daijro/camoufox/blob/main/pythonlib/camoufox/sync_api.py), [Playwright `launch_persistent_context`](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context), [Remote Server](https://camoufox.com/python/remote-server/), [daijro/camoufox#253](https://github.com/daijro/camoufox/issues/253).

## 2. Fingerprint stability

**Default: randomized each launch. Individual properties can be fixed. JA3 cannot.**

### Default is rotation

The README: “Every run gets a fresh identity drawn from the real-world distribution of devices.” BrowserForge generates fingerprints from `os` and `screen` constraints. If `os` is omitted, the wrapper “randomly choose[s] from a list of all three” of windows / macos / linux.

`launch_options()` in `pythonlib/camoufox/utils.py` generates a BrowserForge fingerprint when the caller does not pass `fingerprint` or `fingerprint_preset`, then `merge_into`s it into `config`. After that it assigns **new random seeds every launch** unless those keys are already set:

```python
set_into(config, 'fonts:spacing_seed', randint(1, 4_294_967_295))
set_into(config, 'audio:seed', randint(1, 4_294_967_295))
set_into(config, 'canvas:seed', randint(1, 4_294_967_295))
```

`set_into` only writes when the key is missing, so a reused config can pin those seeds.

`persistent_context=True` does **not** by itself freeze the fingerprint. [daijro/camoufox#38](https://github.com/daijro/camoufox/issues/38) asked how to reuse the same fingerprint across sessions; related [#71](https://github.com/daijro/camoufox/issues/71) reports the fingerprint changing on restart with a persistent context. The issue was closed as achievable today by saving `launch_options()` output and passing it back as `from_options`. `NewBrowser` skips regeneration when `from_options` is set:

```python
if not from_options:
    from_options = launch_options(headless=headless, debug=debug, **kwargs)
```

A first-class single seed parameter is still tracked ([#442](https://github.com/daijro/camoufox/issues/442)).

### What can be fixed (not randomized)

Official fingerprint docs: pass a JSON of properties via `Camoufox(config={"property": "value"})`. “Config data not set by the user will be automatically populated using BrowserForge.” Documented, pin-able properties include:

| Area | How to pin | Official surface |
| --- | --- | --- |
| **Navigator** | `config` keys such as `navigator.userAgent`, `navigator.platform`, `navigator.language`, `navigator.languages`, `navigator.hardwareConcurrency`, … | [Fingerprint — Navigator](https://camoufox.com/fingerprint/navigator/). `navigator.webdriver` is always false. |
| **Timezone** | `config["timezone"]` (IANA TZ id, e.g. `America/Chicago`); also set by `geoip` | [Fingerprint — Geolocation & Intl](https://camoufox.com/fingerprint/geolocation/) |
| **Locale** | `locale=` launch arg, or `locale:language` / `locale:region` / `locale:script` / `locale:all` in `config` | [Usage — locale](https://camoufox.com/python/usage/), same geolocation page |
| **Geolocation** | `geoip=True` or an IP string; or `geolocation:latitude` / `geolocation:longitude` / `geolocation:accuracy` | [Usage — geoip](https://camoufox.com/python/usage/), geolocation page |
| **WebGL** | `webgl_config=(vendor, renderer)` for a supported pair on the target `os`; or `webGl:*` / `webGl2:*` in `config` (renderer, vendor, extensions, parameters, shader precision) | [Usage — webgl_config](https://camoufox.com/python/usage/), [Fingerprint — WebGL](https://camoufox.com/fingerprint/webgl/) |
| **OS / screen constraints** | `os="windows"` (etc.), `screen=Screen(...)` | [Usage — Device Rotation](https://camoufox.com/python/usage/) |
| **Whole generated bundle** | Save `launch_options(...)` and reuse `from_options=...`; or pass a BrowserForge `fingerprint=` (docs say this path will be deprecated) | [BrowserForge integration](https://camoufox.com/python/browserforge/), `utils.py` / `sync_api.py` |
| **Canvas / audio / font noise** | Pin `canvas:seed`, `audio:seed`, `fonts:spacing_seed` in `config` | `utils.py` (`set_into` seeds) |

Passing `os` or `screen` alone does **not** freeze navigator, WebGL, or seeds. Those still regenerate unless `config` / `from_options` / `fingerprint` is reused.

The stealth write-up stresses internal consistency (Windows UA + Apple GPU is a leak). Manual `config` for locale, geolocation, UA, navigator, or viewport triggers leak warnings unless `i_know_what_im_doing=True`.

### JA3 / TLS

**Not a Camoufox spoofing feature.** The official fingerprint index lists navigator, cursor, fonts, screen, window, document, HTTP headers, geolocation/Intl, WebRTC IP, WebGL, media/audio, voices, addons — not JA3, JA4, or ClientHello.

Maintainer close of [daijro/camoufox#358](https://github.com/daijro/camoufox/issues/358): Camoufox does not spoof TLS ClientHello / JA3/JA4; TLS is negotiated in Firefox NSS, below the C++/Juggler spoofing layer; this is closed as out of scope. The stated intent is to keep a genuine Firefox TLS fingerprint rather than a unique-per-profile ClientHello.

So JA3 is “stable” only in the sense that it is real Firefox NSS, not a pin-able Session-identity knob. It cannot be randomized or set per Account via Camoufox config.

Sources: [README — Fingerprint Injection](https://github.com/daijro/camoufox/blob/main/README.md), [camoufox.com/fingerprint](https://camoufox.com/fingerprint/), [Navigator](https://camoufox.com/fingerprint/navigator/), [Geolocation & Intl](https://camoufox.com/fingerprint/geolocation/), [WebGL](https://camoufox.com/fingerprint/webgl/), [BrowserForge](https://camoufox.com/python/browserforge/), [`utils.py` `launch_options`](https://github.com/daijro/camoufox/blob/main/pythonlib/camoufox/utils.py), [daijro/camoufox#38](https://github.com/daijro/camoufox/issues/38), [daijro/camoufox#358](https://github.com/daijro/camoufox/issues/358).

## 3. Playwright API compatibility

**Yes for Python. Node is official only through an experimental remote server.**

Usage docs: “Camoufox is fully compatible with your existing Playwright code. You only have to change your browser initialization.” Sync: `from camoufox.sync_api import Camoufox`. Async: `from camoufox.async_api import AsyncCamoufox`. Examples use `browser.new_page()` and `page.goto(...)`. “All Playwright Firefox launch options are accepted.” The README lists “Drop-in Playwright compatibility via Python interface” and a “Custom implementation of Playwright for the latest Firefox.”

That is the normal Playwright page/locator surface: navigate, query the DOM, type, click. Cursor humanization (`humanize=True` or a max duration) is an extra Camoufox option, not a replacement for locators.

**Python** is the first-party interface ([PyPI `camoufox`](https://pypi.org/project/camoufox/), [pythonlib README](https://github.com/daijro/camoufox/blob/main/pythonlib/README.md)).

**Node / other languages:** official path is the experimental remote Playwright server (`python -m camoufox server` or `camoufox.server.launch_server`), then `playwright.firefox.connect(ws://...)`. Docs warn this “uses a hacky workaround to gain access to undocumented Playwright methods.” Fingerprints do not rotate while one server instance is up. As above, that server path does not persist `user_data_dir`.

[apify/camoufox-js](https://camoufox.com/community/) is listed under Community Projects as “independently maintained and … not official Camoufox releases.”

Sources: [Usage](https://camoufox.com/python/usage/), [Python interface](https://camoufox.com/python/), [README — Python Usage / Playwright support](https://github.com/daijro/camoufox/blob/main/README.md), [Remote Server](https://camoufox.com/python/remote-server/), [Community](https://camoufox.com/community/).

## 4. What Camoufox does not provide

Camoufox is an anti-detect browser and Playwright launcher. It is **not** an Instagram API and does not mention Instagram Account, Post, or Comment as product features.

It does not:

- Log into an Account or refresh Instagram session cookies
- Parse a Post caption, image, or recent comments
- Post a Comment
- Return canonical Post or Comment URLs

Anything on instagram.com would be **custom Playwright automation** (selectors, waits, navigation) on top of Camoufox. That work is outside Camoufox and was not exercised here.

`block_images=True` would block image requests (“save your proxy usage”). That is a Camoufox toggle, not a Post-image reader; turning it on would prevent loading a Post image in the page.

Sources: [README features / capabilities](https://github.com/daijro/camoufox/blob/main/README.md), [Usage — block_images](https://camoufox.com/python/usage/). No Instagram API or Instagram DOM helpers appear in those first-party docs.

## 5. Constraints for hourly unattended runs

**Headless vs headed.** `headless` is `Optional[Union[bool, Literal['virtual']]]` and **defaults to False** (headed). `headless=True` is supported. On Linux, `headless="virtual"` uses Xvfb. Virtual-display docs say headless patches may still leak later and recommend a virtual display for “headless” runs. The wrapper turns `headless="virtual"` into a real headed window on Xvfb (`headless=False` plus a `DISPLAY`).

**GeoIP.** `geoip=True` or an IP string fills longitude, latitude, timezone, country, locale, and WebRTC IP. Language can be sampled from speakers in the target region. Needs `pip install -U "camoufox[geoip]"`. Official geoip docs pass `geoip=True` together with Playwright’s `proxy` dict and warn that residential proxies matter for “best results.” Using a non-localhost proxy without geolocation triggers a leak warning that cannot be silenced with `i_know_what_im_doing`.

**Proxy.** Playwright-shaped `proxy={'server', 'username', 'password'}`. Accepted as a Firefox launch option. README marketing copy says Camoufox is “intended to be used with rotating proxies”; that is a usage recommendation, not an API that rotates for us. For a stable Session identity, a sticky egress IP is the consistent pairing with a pinned fingerprint (not documented as a Camoufox feature — inferred from geoip matching the proxy IP).

**Cache.** `enable_cache` is off by default; without it, `page.go_back()` / `page.go_forward()` are documented as unavailable.

**Stability / ops.** README: under development, may not be suitable for stable production. Stealth 2026: maintenance gap and fingerprint inconsistencies. One process per `user_data_dir` (Playwright). `launch_server` cannot host that persistent profile.

Sources: [Usage — headless, geoip, proxy, enable_cache](https://camoufox.com/python/usage/), [Virtual Display](https://camoufox.com/python/virtual-display/), [GeoIP & Proxy](https://camoufox.com/python/geoip/), [`utils.py` headless default and proxy-without-geoip warning](https://github.com/daijro/camoufox/blob/main/pythonlib/camoufox/utils.py), [README warning](https://github.com/daijro/camoufox/blob/main/README.md), [Playwright user-data-dir single-instance note](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context).

## 6. Gaps vs our need

Need: persist one Session identity, open instagram.com as an Account, read a Post’s caption / image / recent comments, post a Comment, capture Post and Comment URLs.

| Piece | Camoufox | Gap |
| --- | --- | --- |
| Cookies / local storage across hourly restarts | Yes, `persistent_context` + `user_data_dir` | None at the browser-profile layer. Instagram session lifetime and checkpoints are out of scope here. |
| Fingerprint half of Session identity | Pin-able if we persist `from_options` / `config` (navigator, WebGL, timezone, locale, geo, canvas/audio/font seeds) | **Default is a new identity every launch.** `os`/`screen` alone is not enough. No first-class “seed” yet (#442). |
| JA3 | Genuine Firefox NSS; not configurable | Cannot set a unique-per-Account TLS fingerprint. Usually matches Firefox, which the project treats as desirable. |
| Open as an Account | Generic browser only | Login, 2FA, and cookie refresh are not Camoufox features. |
| Read Post caption / image / recent comments | Playwright can read whatever DOM we write selectors for | **Custom Instagram automation, not provided.** |
| Post a Comment | Playwright can type/click | **Custom Instagram automation, not provided.** |
| Capture Post and Comment URLs | Playwright can read `page.url` or DOM `href`s if the site exposes them | **Custom, not provided.** |
| Node worker | Experimental remote server, no persistent profile | Official persistent profile is the Python `Camoufox(...)` client path. |

**Bottom line:** Camoufox can carry cookies in a persistent profile and can keep a fingerprint stable if we save and reuse launch options. It does not implement Session identity as a single product feature, and it does not read a Post or post a Comment.

## Sources

Primary, in the order they were used:

1. [https://github.com/daijro/camoufox/blob/main/README.md](https://github.com/daijro/camoufox/blob/main/README.md) — project definition, fingerprint rotation, Playwright/Python, production warning.
2. [https://camoufox.com/](https://camoufox.com/) — current docs home (linked from the README).
3. [https://camoufox.com/python/usage/](https://camoufox.com/python/usage/) — Playwright compatibility, `persistent_context`, `user_data_dir`, `os`, `config`, `webgl_config`, `headless`, `geoip`, `locale`, `proxy`, `block_images`.
4. [https://github.com/daijro/camoufox/blob/main/pythonlib/camoufox/sync_api.py](https://github.com/daijro/camoufox/blob/main/pythonlib/camoufox/sync_api.py) — `from_options`, `launch_persistent_context`.
5. [https://github.com/daijro/camoufox/blob/main/pythonlib/camoufox/utils.py](https://github.com/daijro/camoufox/blob/main/pythonlib/camoufox/utils.py) — default fingerprint generation, per-launch seeds, headless default, geoip/proxy.
6. [https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context) — what `user_data_dir` persists.
7. [https://camoufox.com/fingerprint/](https://camoufox.com/fingerprint/) and child pages for navigator, geolocation/Intl, WebGL.
8. [https://camoufox.com/python/browserforge/](https://camoufox.com/python/browserforge/) — random-by-default BrowserForge fingerprints.
9. [https://camoufox.com/python/geoip/](https://camoufox.com/python/geoip/), [https://camoufox.com/python/virtual-display/](https://camoufox.com/python/virtual-display/), [https://camoufox.com/python/remote-server/](https://camoufox.com/python/remote-server/).
10. [https://camoufox.com/stealth](https://camoufox.com/stealth) — 2026 maintenance status.
11. [https://camoufox.com/community/](https://camoufox.com/community/) — unofficial Node ports.
12. First-party issue closes on daijro/camoufox: [#38](https://github.com/daijro/camoufox/issues/38) (persist fingerprint via `from_options`), [#358](https://github.com/daijro/camoufox/issues/358) (JA3 out of scope), [#253](https://github.com/daijro/camoufox/issues/253) (`launch_server` has no persistent context).
