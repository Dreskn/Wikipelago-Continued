APWorld source lives in `APWorldSource`.

World package version: **0.5.0-Bingo!** (see `APWorldSource/archipelago.json`).

The live runtime article pool is `APWorldSource/Wikipelago/entertainment_articles.py`: a curated list of `(Wikipedia title, category)` tuples. Generation uses those explicit category tags (not keyword guessing).

Build APWorld:

```powershell
.\build_apworld.ps1
```

Output:

`APWorld\Wikipelago.apworld`

### Optional / experimental pool builder

`build_article_pool.ps1` / `build_article_pool.py` can build a broader JSON pool for experiments. They are not required for a normal release; the packaged world ships with `entertainment_articles.py` as the pool.

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
