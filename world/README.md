APWorld source lives in `APWorldSource`.

World package version: **1.0-beta1** (`world_version` **1.0.0** in `APWorldSource/wikipelago/archipelago.json` for Archipelago; marketing tag in `full_version`).

The live runtime article pools are `APWorldSource/wikipelago/data/pool_{lang}.json` (multi-tag entries per Wikipedia language). Generation uses those tags (not keyword guessing).

Build APWorld:

```powershell
.\build_apworld.ps1
```

Output:

`APWorld\wikipelago.apworld`

The zip is lowercase (`wikipelago.apworld` → inner folder `wikipelago/` with `archipelago.json` inside), per Archipelago’s apworld spec.

The build injects Archipelago packaging fields (`version` / `compatible_version`) into the packaged `archipelago.json`. Without those, AP 0.6.7+ treats the world as `0.0.0` and YAML `requires.game.Wikipelago` fails.

### Letter-pair bingo weights (per language)

Bingo boards sample pairs using title-frequency weights for the slot’s Wikipedia language. Pair extraction follows each language’s Scrabble alphabet (distinct tiles stay distinct; other diacritics fold; German `ß` → `SS`). Rebuild after dump updates or alphabet rule changes:

```powershell
python .\build_letter_pair_weights.py --lang all
```

This downloads each `{lang}wiki-latest-all-titles-in-ns0.gz` into `world/_cache/` if needed, then writes `APWorldSource/wikipelago/letter_pair_weights_{lang}.json` for `en, fr, de, es, it, pt, nl, sv, pl`.

### Optional / experimental pool builder

`build_article_pool.ps1` / `build_article_pool.py` and the pageviews export tools refresh `data/pool_*.json`. CI validates every language pool with `python world/validate_article_pool.py --lang all --strict`, then generates EN / FR / PL seeds against Archipelago **0.6.7** (`world/ci_generate.py`).

```powershell
# Build to 5,000 titles (keeps existing and expands)
.\build_article_pool.ps1 -TargetCount 5000

# Rebuild from scratch to 20,000 titles
.\build_article_pool.ps1 -TargetCount 20000 -Replace
```

Optional tuning:

```powershell
# Increase random sampling share (0.0 to 1.0)
.\build_article_pool.ps1 -TargetCount 10000 -RandomShare 0.5

# Deterministic shuffle source
.\build_article_pool.ps1 -TargetCount 10000 -Seed 4242
```

Notes:
- The experimental builder mixes many topic categories plus random pages and filters low-value pages.
- If you adopt a generated pool into the runtime world, update the AP package source accordingly, then run `build_apworld.ps1` again.
