# Wikipelago Options

Player settings live in your YAML under the `Wikipelago:` block.

- **Template (source of truth for names/defaults):** [`yaml/Wikipelago.yaml`](../yaml/Wikipelago.yaml)
- Also attached on [Releases](https://github.com/Dreskn/Wikipelago-Continued/releases)

After installing the apworld, you can generate a fresh template from the Archipelago Launcher (**Generate Template Options**).

---

## Length and pacing

| Option | Default | What it does |
| --- | --- | --- |
| `check_count` | `40` | How many Start → Target rounds (checks) are generated for your slot. |
| `required_fragments` | `7` | Knowledge Fragments needed before the Grand Goal question is revealed. Landing on the answer page finishes the slot. |
| `additional_fragments_in_pool` | `2` | Extra Knowledge Fragments shuffled into the item pool beyond `required_fragments`. Goal still needs only the required count. |
| `start_rounds_unlocked` | `10` | How many rounds are playable immediately at seed start. |
| `rounds_per_unlock` | `5` | How many additional rounds each **Round Access** item unlocks. |
| `progression_balancing` | `50` | Standard Archipelago balancing (0–99). Higher tends to place useful progression a bit earlier. |

Rough pacing tip: if `start_rounds_unlocked` is high relative to `check_count`, the seed feels more open early; if low, you wait more on Round Access.

### Target rerolls

Per-round target rerolls are YAML-tuned (`target_rerolls_start`, default **1**) and increased by **Progressive Reroll** items (`target_reroll_unlocks`, default **2** → max 3/round when fully upgraded). Reroll the current target from the web client (including the final round). Alternatives come from leftover articles in the same seed pool. The Grand Goal article itself cannot be rerolled.

Hover the **Target** title to see a plain-text blurb: Wikipedia short description plus the lead paragraph (no images/HTML).

### Progressive Back

Browser back is limited per round by `back_depth_start` (default **0**) plus **Progressive Back** items (`back_depth_unlocks`, default **3**). When you hit the limit, the Back tool does nothing until the round advances. The Items row shows remaining depth as a badge.

| Option | Default | What it does |
| --- | --- | --- |
| `back_depth_start` | `0` | Back steps available each round before you find Progressive Back. `0` means Back stays locked until the first upgrade. |
| `back_depth_unlocks` | `3` | How many Progressive Back items are in the pool. |
| `target_rerolls_start` | `1` | Target rerolls available each round at the start. |
| `target_reroll_unlocks` | `2` | How many Progressive Reroll items are in the pool. |

### Crossroads and side branches

On by default (`branch_count: 2`). Some main-road rounds become crossroads and **Branch Keys** open extra Start → Target chains. Set `branch_count` to `0` to turn the whole system off.

| Option | Default | What it does |
| --- | --- | --- |
| `branch_count` | `2` | How many main-road rounds are crossroads (`0`–`8`). `0` turns the whole system off. |
| `branch_length` | `5` | How many rounds each unlocked side branch lasts (`1`–`20`). |
| `additional_branch_keys` | `1` | Extra Branch Keys in the pool. They still count as progression for the multiworld; they do not open extra branches. |

On the client: live branch targets list under the main road, a small crossroad cue appears on those rounds, and **Journey** includes the side paths.

### Letter-pair bingo

When `toggle_bingo_letterpairs` is on (default), you get `bingo_cards_start` boards (default **1**) of size `bingo_letterpairs_grid` (3–20, default **5**). Set start to **0** to keep every board locked until **Progressive Bingo Card** items (`bingo_card_unlocks`, default **2**). Bingo on with start **0** and unlocks **0** is rejected (no boards). `bingo_stamp_unlocks` (default **2**) adds **Progressive Bingo Stamp** items that each fill one empty cell.

On the client: unlocked boards stamp in parallel from page titles; click a board for a larger overlay.

---

## Grand Goal article

| Option | Default | What it does |
| --- | --- | --- |
| `random_goal_article` | `true` | Kept for old YAMLs; ignored. The Grand Goal always comes from that wiki language's goal pool (answer page preferred from enabled categories). |
| `goal_article_preset` | `dark_souls` | Deprecated and ignored. Kept so older YAMLs still generate. |

---

## Sanities (off by default)

| Option | Default | What it does |
| --- | --- | --- |
| `searchsanity` | `false` | If true, in-page search (Ctrl+F Lens) is limited to letters you have unlocked via **Search Letter** items. |
| `search_starting_letters` | `none` | Starting letters when searchsanity is on: `none` \| `all_vowels` \| `etaoi` \| `raise`. |
| `scrollsanity` | `false` | If true, scrolling starts slow and improves with **Progressive Scroll Speed** items. |

These add friction; leave them off for a first playtest or casual multiworld.

---

## Display lenses (off by default)

When a lens option is **false**, that part of Wikipedia looks normal.  
When **true**, that part stays hidden until you receive the matching **Lens** item.

| Option | Locks until you find |
| --- | --- |
| `randomize_tables` | Table Lens |
| `randomize_pictures` | Picture Lens |
| `randomize_incipit` | Lead Lens (intro paragraphs) |
| `randomize_infoboxes` | Infobox Lens |
| `randomize_toc` | Contents Lens |
| `randomize_navboxes` | Navbox Lens |
| `randomize_hatnotes` | Hatnote Lens |
| `randomize_references` | Reference Lens |

**Warning:** enabling lenses (even one) can make routing much harder. Stacking several increases difficulty sharply. For larger public tests, defaults (all `false`) are the safest.

---

## Wikipedia language

| Option | Default | Notes |
| --- | --- | --- |
| `wikipedia_language` | `en` | Which Wikipedia you race on: `en`, `fr`, `de`, `es`, `it`, `pt`, `nl`, `sv`, `pl`. Start/Target titles, Grand Goal question, and article fetches all use that edition. |

This is **not** the top-bar language dropdown. That dropdown only translates the client UI (buttons, toasts, panel titles). A French UI can still race on English Wikipedia if the YAML says `en`.

## Article categories

Each `include_*` toggle shapes which articles can appear in rounds and (when random) the Grand Goal pool. Titles are **multi-tag**: kept if **any** tag intersects an enabled category (**OR**).

| Option | Default |
| --- | --- |
| `include_video_games` | `true` |
| `include_movies` | `true` |
| `include_tv_shows` | `true` |
| `include_anime_manga` | `true` |
| `include_sports` | `true` |
| `include_science_space` | `true` |
| `include_technology` | `true` |
| `include_history` | `true` |
| `include_geography` | `true` |
| `include_food_cuisine` | `true` |
| `include_art_literature` | `true` |
| `include_mythology_folklore` | `true` |
| `include_music` | `true` |
| `include_politics` | `true` |
| `include_famous_people` | `true` |
| `include_animals` | `true` |
| `include_biology_medicine` | `true` |
| `include_miscellaneous` | `true` |

`board_games` was removed in 0.6. Leave at least one category enabled.

## Sensitive pages

| Option | Default | Notes |
| --- | --- | --- |
| `include_sensitive_pages` | `false` | Not a category. When off, pages flagged sensitive (porn, terrorism, violent/sexual crime, illicit drugs) are excluded even if they match an enabled category. When on, they may appear if they also match an enabled category. |

---

## Deaths, DeathLink, and bombs (off by default)

| Option | Default | What it does |
| --- | --- | --- |
| `deaths` | `false` | Forward-revisit a page already visited this round → death (random Wikipedia page). Peaceful when off. |
| `death_link` | `false` | Full Archipelago DeathLink (send and receive). |
| `link_bombs` | `false` | Bomb-marked links on each page (requires `deaths`). Hitting one causes a death. |
| `link_bomb_density` | `few` | `few` (1) / `more` (5) / `insane` (20), capped at half the eligible links. Never bombs Target or Grand Goal links. |

Death effect: jump to a random article. Fragments and unlocks are kept.

---

## Traps

| Option | Default | What it does |
| --- | --- | --- |
| `trap_count` | `0` | How many Foggy Links / Missing Links / Wrong Wiki items to add (before Footnote filler). Counts toward mandatory item budget — generation fails if too many. |
| `trap_type` | `all` | `all` / `only_foggy_links` / `only_missing_links` / `only_wrong_wiki`. `both` is deprecated and still selects every trap. |
| `trap_link` | `false` | Share traps with other Trap Link players (independent of `trap_count`). |

| Trap | Effect |
| --- | --- |
| **Foggy Links** | Next ordinary page: link labels become `[Link]`. |
| **Missing Links** | Next ordinary page: about 30% of links removed (never all). |
| **Wrong Wiki** | Next click shows the article on a random other-language Wikipedia. The following page returns to your seed language when that article exists there. |

If several traps land at once, they wait in a queue and apply **one page at a time** (you will see a toast when each is received). Target and Grand Goal pages skip Foggy/Missing.

---

## Suggested starting points

- **Casual / first multiworld:** defaults (`deaths`/`death_link`/`traps` off).
- **Shorter seed:** lower `check_count` and `required_fragments`.
- **More texture:** bingo boards, or raise `branch_count` — not every extra system at once.
- **Harder / spice:** enable one sanity or one lens — not everything at once. Add `deaths` or a small `trap_count` for chaos.

For gameplay concepts (rounds, fragments, items), see the [Overview](overview.md).  
For a numbered map of the browser HUD, see the [web client UI](ui.md).  
For install and connect steps, see the [Setup guide](setup.md).
