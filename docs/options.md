# Wikipelago Options

Player settings live in your YAML under the `Wikipelago:` block.

- **Template (source of truth for names/defaults):** [`yaml/Wikipelago.yaml`](../yaml/Wikipelago.yaml)
- Also attached on [Releases](https://github.com/Dreskn/Wikipelago-Continued/releases)

After installing the apworld, you can generate a fresh template from the Archipelago Launcher (**Generate Template Options**).

---

## Length and pacing

| Option | Default | What it does |
| --- | --- | --- |
| `check_count` | `25` | How many Start → Target rounds (checks) are generated for your slot. |
| `required_fragments` | `5` | Knowledge Fragments needed before you can finish the Grand Goal. |
| `start_rounds_unlocked` | `10` | How many rounds are playable immediately at seed start. |
| `rounds_per_unlock` | `5` | How many additional rounds each **Round Access** item unlocks. |
| `progression_balancing` | `50` | Standard Archipelago balancing (0–99). Higher tends to place useful progression a bit earlier. |

Rough pacing tip: if `start_rounds_unlocked` is high relative to `check_count`, the seed feels more open early; if low, you wait more on Round Access.

### Target rerolls (client)

While connected, you can **Reroll** the current round’s target up to **3 times per round** from the web client. Alternatives come from leftover articles in the same seed pool (same enabled categories). The Grand Goal round cannot be rerolled. Requires a seed generated with a current apworld that includes a `reroll_pool` (rebuild/reinstall if the button stays disabled).

Hover the **Target** title to see a plain-text blurb: Wikipedia short description plus the lead paragraph (no images/HTML).

---

## Grand Goal article

| Option | Default | What it does |
| --- | --- | --- |
| `random_goal_article` | `true` | If true, the Grand Goal article is picked randomly from enabled categories. |
| `goal_article_preset` | `dark_souls` | Used only when `random_goal_article` is `false`. Picks a fixed famous article. |

Valid presets include (see the YAML for the full list):  
`minecraft`, `the_legend_of_zelda`, `dark_souls`, `elden_ring`, `super_mario_bros`, `pokemon_red_and_blue`, `chess`, `catan`, `the_dark_knight`, `star_wars_film`, `lord_of_the_rings_fellowship`, `the_matrix`, `avatar_the_last_airbender`, `breaking_bad`, `stranger_things`, `game_of_thrones`, `the_simpsons`, `spongebob_squarepants`, `super_smash_bros_ultimate`, `halo_combat_evolved`.

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

## Article categories

Each `include_*` toggle shapes which articles can appear in rounds and (when random) the Grand Goal pool.

| Option | Default |
| --- | --- |
| `include_video_games` | `true` |
| `include_board_games` | `true` |
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

Turn categories off to shrink or theme the pool (for example movies + TV only). Leave at least one category enabled.

---

## Deaths, DeathLink, and bombs (off by default)

| Option | Default | What it does |
| --- | --- | --- |
| `deaths` | `false` | Forward-revisit a page already visited this round → death (random Wikipedia page). Peaceful when off. |
| `death_link` | `false` | Full Archipelago DeathLink (send and receive). |
| `link_bombs` | `false` | Hidden bomb links on each page (requires `deaths`). Hitting one causes a death. |
| `link_bomb_density` | `few` | `few` (1) / `more` (5) / `insane` (20), capped at half the eligible links. Never bombs Target or Grand Goal links. |

Death effect: jump to a random article. Round visit tracking is cleared as soon as the death fires (and again on the landing page) so deaths cannot chain into a soft-lock while the random page loads. Fragments and unlocks are kept.

---

## Traps

| Option | Default | What it does |
| --- | --- | --- |
| `trap_count` | `0` | How many Foggy Links / Missing Links items to add (before Footnote filler). Counts toward mandatory item budget — generation fails if too many. |
| `trap_type` | `both` | `both` / `only_foggy_links` / `only_missing_links`. |
| `trap_link` | `false` | Share traps with other Trap Link players (independent of `trap_count`). |

| Trap | Effect |
| --- | --- |
| **Foggy Links** | Next non-target page: link labels become `[Link]`. |
| **Missing Links** | Next non-target page: about 30% of links removed (never all). |

---

## Suggested starting points

- **Casual / first multiworld:** defaults (`deaths`/`death_link`/`traps` off).
- **Shorter seed:** lower `check_count` and `required_fragments`.
- **Harder / spice:** enable one sanity or one lens — not everything at once. Add `deaths` or a small `trap_count` for chaos.

For gameplay concepts (rounds, fragments, items), see the [Overview](overview.md).  
For install and connect steps, see the [Setup guide](setup.md).
