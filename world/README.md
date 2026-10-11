APWorld source lives in `APWorldSource`.

World package version: **1.1.0** (`world_version` and `full_version` in `APWorldSource/wikipelago/archipelago.json`).

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

### Rebuilding the article pools

The shipped pools (`APWorldSource/wikipelago/data/pool_{lang}.json`) come from this pipeline. Run the steps in order from the repo root; each script keeps its settings at the top of the file.

1. `python world/pageviews/pageviews_aggregate.py`: Wikipedia page-view tops per language, written to `world/pageviews/pageviews_aggregate_{lang}.json`.
2. `python world/pageviews/annotate_pools.py`: Wikidata tags and the sensitive flag for every title, written to `world/pageviews/annotated/pool_annotated_{lang}.json`. Set `SAMPLE_N` (1000 for a dry run, 0 for the full lists).
3. `python world/enrich_pool_from_popular_pages.py`: adds titles from the English WikiProject "Popular pages" lists (and their other-language versions) to the annotated pools. Writes `world/pool_enrichment_report.json` (not tracked).
4. `python world/pageviews/export_apworld_pools.py`: writes the compact `data/pool_{lang}.json` files the world ships.
5. `python world/validate_article_pool.py --lang all --strict`: checks every title against live Wikipedia. Writes `world/pool_validation_report.json` (not tracked).

Then rebuild the apworld (`build_apworld.ps1`) and run `release_check.ps1`.

Steps 2 and 3 cache Wikidata answers in `world/pageviews/qid_annotation_cache.json`. Delete that file before a full re-annotation, so changes to the tag or sensitive rules apply to every title instead of reusing old answers.

Every commit runs Smoke and Generate (EN / FR / PL seeds against Archipelago **0.6.7**, `world/ci_generate.py`). Pool validation runs weekly and on pool-file pushes to `main`; it reports dead titles and never removes them.
