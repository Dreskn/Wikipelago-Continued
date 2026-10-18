# Wikipelago Continued

Custom [Archipelago](https://archipelago.gg) world (AP **0.6.7+**) based on wiki racing. Each round has a Start and a Target Wikipedia article; reaching the target via in-article links sends checks, and items unlock tools and progress toward the Grand Goal.

- Continued fork of [Skrumptily69's original Wikipelago](https://github.com/Skrumptily69/Wikipelago), used with permission. Keep the credit (README.md, LICENSE).
- Live client: https://wikipelago.dreskn.fr/ — bug reports come from GitHub Issues and the Wikipelago thread on the Archipelago Discord (links in README).
- 9 Wikipedia languages: en, fr, de, es, it, pt, nl, sv, pl (`UI_LANGS` in `web/i18n.js`, `WikipediaLanguage` in `Options.py`).

## Layout

- `world/APWorldSource/wikipelago/` — the APWorld (Python, loaded by the AP generator).
  - `__init__.py` world logic and item pool; `Items.py`, `Locations.py`, `Regions.py`; `Options.py` (YAML options)
  - `grand_goal.py`, `letter_pairs.py` (bingo), `article_pool.py`
  - `data/pool_{lang}.json` curated multi-tag article pools; `letter_pair_weights_{lang}.json` bingo weights
  - `archipelago.json` version metadata
  - Built to `world/APWorld/wikipelago.apworld` (gitignored).
- `bridge/bridge.py` — single-file aiohttp server: serves `web/`, REST API under `/api/session/{sid}/...`, and acts as the Archipelago websocket client (one state per browser session). Calls the Wikipedia API for title canonicalisation, redirects and Compass page links (only the 9 supported wikis). Requests that come through a reverse proxy can't connect to private or loopback Archipelago addresses. Deps: `aiohttp`, `websockets`.
  - Host announcements: plain text in `announcement.txt` at the repo root (gitignored) shows in a banner on every open page within a few seconds (re-read every 3s, max 500 characters, no restart); delete the file to remove it.
- `web/` — plain JavaScript, no build step, no framework: `app.js` (HUD and game UI), `i18n.js` (all UI strings), `style.css`, `index.html`, PWA manifest and `service-worker.js`. Icons are Lucide SVGs inlined via `lucideIcon()` in `app.js`. Fonts are self-hosted WOFF2 in `web/fonts/` (OFL, licence next to each family); no third-party CDNs. Icon and font notices live in `THIRD_PARTY_NOTICES.md` (`LICENSE` is the MIT text only).
- `docs/` — player docs; `docs/grand-goal/` is the Grand Goal question bank and its build scripts.
- `yaml/Wikipelago.yaml` — player YAML template.
- `world/` — build, test and pool-maintenance scripts. Article pools are rebuilt with the pipeline in `world/README.md` (pageviews → Wikidata annotation → enrichment → export → validation); `world/pageviews/` holds its data.

## Commands (PowerShell, repo root)

```powershell
python bridge/bridge.py --port 5000      # run locally; --debug-menu (or WIKIPELAGO_DEBUG_MENU=1) for the playtest console; PORT env also works
bridge/setup_and_start_bridge.bat        # first run on Windows; bridge/start_bridge.bat afterwards
./world/build_apworld.ps1                # build the apworld
./world/release_check.ps1                # build + smoke test
./world/smoke_test.ps1 [-BuildApworld]   # smoke test only (also runs the two Python unit tests)
./world/fuzz_test.ps1 -Runs 25           # random options: item-math model + the world's own code with AP stand-ins
./world/real_fuzz_test.ps1 -Runs 25 -ArchipelagoRoot "<path>"   # real generation; needs an Archipelago 0.6.7+ checkout or install (installs the built apworld temporarily, restores the old one)
python world/test_letter_pairs.py
python world/test_blocked_namespaces.py
python world/validate_article_pool.py --lang all --strict       # pools vs live Wikipedia
python world/build_letter_pair_weights.py --lang all            # rebuild bingo weights (downloads to world/_cache/)
```

## CI (`.github/workflows/`)

- `ci.yml` (every push and PR): `smoke_test.ps1 -BuildApworld`, then seven seeds generated against Archipelago 0.6.7 via `world/ci_generate.py` (EN, FR, PL, Topic Realms, Realm Master, Realm Master with keys, Homeward).
- `pool-validate.yml` (weekly, and on pool changes to `main`): reports dead titles, never removes them.

## Conventions

- Work on `dev`. `main` is the released branch, updated only by a `dev` → `main` PR on GitHub. Never push to `main` directly.
- Commit messages: one plain imperative sentence ending with a period, e.g. "Fix blank room load from a const displayTitle assignment."
- Releases go on GitHub Releases with `wikipelago.apworld` and `yaml/Wikipelago.yaml` attached.
- Files must be strict UTF-8 (the smoke test checks this).
- New UI text needs entries in `web/i18n.js` for all 9 languages. English strings sent by the bridge (compass hints, trap names, goal text) are mapped by the `localize*` helpers at the end of `i18n.js`.
- When shipping web asset changes, bump `CACHE_NAME` in `web/service-worker.js` and the `?v=` stamps in `web/index.html`.
- Version bumps touch all of these together:
  - `world/APWorldSource/wikipelago/archipelago.json`: `world_version`, `full_version`, `description`
  - `CLIENT_VERSION` in `bridge/bridge.py`
  - `APP_VERSION` in `web/app.js`
  - `requires.game.Wikipelago` in `yaml/Wikipelago.yaml`
  - version pins in `world/smoke_test.ps1`
  - `README.md`, `world/README.md`, the Compatibility table in `docs/setup.md`

  The smoke test checks the YAML, `CLIENT_VERSION`, `APP_VERSION`, `archipelago.json` and CI `AP_REF` pins; the README and docs versions can drift unnoticed.
- Client-only releases (bridge or web fixes, apworld unchanged) add a letter to the version: `1.1.1a`, then `1.1.1b`.
  - Change only `CLIENT_VERSION`, `APP_VERSION`, their two pins in `world/smoke_test.ps1`, and the Compatibility table in `docs/setup.md` (web client `1.1.1a`, apworld `1.1.1`).
  - Never put the letter in `archipelago.json`, the YAML's `requires`, or the smoke test's `archipelago.json` and packaged-apworld pins: Archipelago reads those as numbers.
  - The GitHub Release (tag `1.1.1a`) attaches the same `wikipelago.apworld` and `Wikipelago.yaml` again, so "latest release" always has the downloads, and says no new apworld is needed.
  - The next apworld change goes to `1.1.2` (or `1.2.0`) everywhere and drops the letter.
- Archipelago version: `minimum_ap_version` in `archipelago.json` and `requires.version` in the YAML stay at the oldest supported Archipelago (0.6.7), per AP's guidance; raise them only when the world needs a newer core feature. Player docs say "0.6.7 or newer".

## Working agreements

- Briefly explain the plan before large changes; keep changes focused on the task.
- Don't commit or push unless asked.
