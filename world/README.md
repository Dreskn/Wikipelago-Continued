APWorld source lives in `world/APWorldSource`. Commands below run from the repo root.

World package version: **1.1.0** (`world_version` and `full_version` in `world/APWorldSource/wikipelago/archipelago.json`).

The live runtime article pools are `world/APWorldSource/wikipelago/data/pool_{lang}.json` (multi-tag entries per Wikipedia language). Generation uses those tags (not keyword guessing).

Build APWorld:

```powershell
./world/build_apworld.ps1
```

Output:

`world/APWorld/wikipelago.apworld`

The zip is lowercase (`wikipelago.apworld` → inner folder `wikipelago/` with `archipelago.json` inside), per Archipelago’s apworld spec.

The build injects Archipelago packaging fields (`version` / `compatible_version`) into the packaged `archipelago.json`. Without those, AP 0.6.7+ treats the world as `0.0.0` and YAML `requires.game.Wikipelago` fails.

### Letter-pair bingo weights (per language)

Bingo boards sample pairs using title-frequency weights for the slot’s Wikipedia language. Pair extraction follows each language’s Scrabble alphabet (distinct tiles stay distinct; other diacritics fold; German `ß` → `SS`). Rebuild after dump updates or alphabet rule changes:

```powershell
python world/build_letter_pair_weights.py --lang all
```

This downloads each `{lang}wiki-latest-all-titles-in-ns0.gz` into `world/_cache/` if needed, then writes `world/APWorldSource/wikipelago/letter_pair_weights_{lang}.json` for `en, fr, de, es, it, pt, nl, sv, pl`.

### Rebuilding the article pools

The shipped pools (`world/APWorldSource/wikipelago/data/pool_{lang}.json`) come from this pipeline. Run the steps in order; each script keeps its settings at the top of the file.

1. `python world/pageviews/pageviews_aggregate.py`: Wikipedia page-view tops per language, written to `world/pageviews/pageviews_aggregate_{lang}.json`.
2. `python world/pageviews/annotate_pools.py`: Wikidata tags and the sensitive flag for every title, written to `world/pageviews/annotated/pool_annotated_{lang}.json`. Set `SAMPLE_N` (1000 for a dry run, 0 for the full lists).
3. `python world/enrich_pool_from_popular_pages.py`: adds titles from the English WikiProject "Popular pages" lists (and their other-language versions) to the annotated pools. Writes `world/pool_enrichment_report.json` (not tracked).
4. `python world/pageviews/export_apworld_pools.py`: writes the compact `world/APWorldSource/wikipelago/data/pool_{lang}.json` files the world ships.
5. `python world/validate_article_pool.py --lang all --strict`: checks every title against live Wikipedia. Writes `world/pool_validation_report.json` (not tracked).

Then rebuild the apworld (`./world/build_apworld.ps1`) and run `./world/release_check.ps1`.

Steps 2 and 3 cache Wikidata answers in `world/pageviews/qid_annotation_cache.json`. Delete that file before a full re-annotation, so changes to the tag or sensitive rules apply to every title instead of reusing old answers.

### Testing

Details and troubleshooting are in `world/SIMPLE_TESTING.md`.

```powershell
./world/release_check.ps1               # build the apworld + smoke test
./world/smoke_test.ps1 -BuildApworld    # what CI's Smoke job runs
./world/fuzz_test.ps1 -Runs 25          # random options vs the world's rules; no Archipelago needed
./world/real_fuzz_test.ps1 -Runs 25 -ArchipelagoRoot "PATH_TO_ARCHIPELAGO"   # real generation; needs an Archipelago 0.6.7+ checkout or install
```

CI (`.github/workflows/ci.yml`) runs on every push and pull request: Smoke (`./world/smoke_test.ps1 -BuildApworld`) and Generate, which builds the apworld and generates six fixed seeds against Archipelago **0.6.7** with `world/ci_generate.py` (EN defaults, FR, PL with branches, EN Topic Realms, FR Realm Master with Topic Realms, EN Realm Master with plain branches). Pool validation (`.github/workflows/pool-validate.yml`) runs weekly and on pool-file pushes to `main`; it reports dead titles and never removes them.
