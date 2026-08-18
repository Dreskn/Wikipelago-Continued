# Wikipelago Overview

## What is Wikipelago?

Wikipelago is a custom Archipelago world inspired by wiki racing.
You play in a browser: each check is a **round** with a **Start** article and a **Target** article.
Click Wikipedia links to reach the target; when you do, that location is checked in Archipelago.

There is no separate desktop client to install for players — use the [hosted web client](https://wikipelago.dreskn.fr/).

## The web client

The page is split in two: the **article** on the left, and your **HUD** on the right.

- **Top bar** — game title, a small build tag, the **UI language** dropdown, and a **Connected / Offline / Practice** badge.
- **Article** — the current Wikipedia page. Only in-article wiki links count as moves. File, Template, Wikipedia-namespace, and similar non-article pages are blocked (you stay in the client with a warning).
- **Connection** — server, slot, password, **Connect**, and **Practice**. After you connect, this card shrinks to the room and slot, with **Disconnect**.
- **Progression** — round track, current targets, Knowledge Fragments, Grand Goal, and Compass. **Journey** opens a map of pages you have marked. The whole card can be hidden to its header.
- **Items** — tools you have found (Back, Reroll, Search, Compass, Branch Key). Locked tools stay grey.
- **Bingo / Lenses / Sanity / Difficulty** — extra cards appear when your seed uses those options. Each can be collapsed the same way.
- **Are you really stuck?** — a link to an external wiki-path solver. It does not send checks for you.

UI language (the dropdown) only changes menus and toasts. The Wikipedia edition you race on is set in your YAML (`wikipedia_language`) and does not follow the dropdown.

**Practice** loads random articles from the same language pool with no Archipelago room. Use it to learn the client; it does not count as a seed.

## What does randomization do?

Archipelago generates Start → Target rounds for your slot and shuffles items into the multiworld — Round Access, Knowledge Fragments, tools (Progressive Back, Progressive Reroll, Ctrl+F Lens, Wiki Compass), optional letter-pair bingo boards / Progressive Bingo Cards / Progressive Bingo Stamps, optional **Branch Keys**, optional lenses, and optional traps when enabled. Completing rounds sends checks; receiving items unlocks more rounds and tools until you can finish the Grand Goal.

Optional **deaths** / **DeathLink** / **link bombs** and **Foggy Links** / **Missing Links** / **Wrong Wiki** traps are off by default — see the [Options guide](options.md).

## How do rounds work?

1. Navigate by clicking in-article Wikipedia links only (typed URLs / free navigation do not count as checks).
2. Reach the Target article to send the location check.
3. Optional: **Reroll** the current target (charges per round from YAML start + Progressive Reroll items; including the final round; Grand Goal itself cannot be rerolled).

Only some rounds are available at the start (`start_rounds_unlocked` in your YAML).
Additional rounds unlock when you receive **Round Access** items (`rounds_per_unlock` controls how many each one opens).

Hover the **Target** title for a short Wikipedia blurb (description plus lead paragraph).

## Crossroads and side branches

If your YAML sets `branch_count` above 0, some main-road rounds become **crossroads**. Finding **Branch Keys** opens a side chain of extra Start → Target rounds.

- Branch 1 needs 1 key, Branch 2 needs 2 keys, and so on, plus the matching finished crossroad.
- Unlocked branches stay live together: one page visit can finish the main target, a branch target, and still stamp bingo.
- Extra keys beyond the number of branches still count as progression items for the multiworld; they do not open more branches.

The Progression card lists each live branch target under the main road. **Journey** shows main-road, branch, and other marked pages on one path.

## What is the goal?

Collect enough **Knowledge Fragments** (count set by `required_fragments`). The pool may contain extras (`additional_fragments_in_pool`); only the required count unlocks the goal. The Grand Goal is then revealed as a **closed question** in your wiki language. Reach the answer article to finish your slot.

The answer title stays hidden until you land on that page. A victory overlay then shows the question and answer; you can close it and keep browsing, or open **Journey** to review the path. Reloading a finished seed may show the overlay once more — close it the same way.

The question comes from that language’s Grand Goal pool (answer page preferred from your enabled categories). Old YAML presets such as `goal_article_preset` are ignored.

## Useful items

- **Progressive Back** — browser back navigation (limited depth per round)
- **Progressive Reroll** — raises per-round target reroll charges
- **Progressive Bingo Card** — unlocks an extra letter-pair bingo board (when bingo is enabled)
- **Progressive Bingo Stamp** — stamps one empty bingo cell on one unlocked board (once per seed; YAML `bingo_stamp_unlocks`)
- **Ctrl+F Lens** — in-page search
- **Wiki Compass** — warmer/colder hints toward the target
- **Branch Key** — opens a side branch when your seed uses crossroads
- **Round Access** — unlocks more rounds
- **Knowledge Fragment** — required toward the Grand Goal
- **Footnote** — filler; does nothing, pads the item pool

Optional toggles can also gate search letters, scroll speed, and Wikipedia page elements (tables, images, infoboxes, etc.) behind Lens items. Those are off by default — see [Options](options.md).

## Letter-pair bingo

When bingo is on, page titles stamp letter pairs on your board(s). Completing a row, column, diagonal, or the full card sends a check.

- Each board has its own **Hide** control next to the **Board N** label.
- Click a board to open a larger overlay with zoom.
- Stamps are shared across devices on the same slot once you are connected.

## Deaths and traps (when enabled)

- **Deaths** — clicking back onto a page you already visited this round jumps you to a random article. Unlocks and fragments are kept.
- **DeathLink** — that death is shared with other DeathLink games, and theirs can hit you.
- **Link bombs** — a few ordinary-looking links explode into a death (never the Target or Grand Goal link).
- **Traps** — Foggy Links hide link text as `[Link]`, Missing Links remove some links, Wrong Wiki shows the next page on another language edition. If several traps arrive at once, they wait in a queue and apply **one per page**.

## What can appear in other players' worlds?

Progression and useful items from Wikipelago can be placed in other games, and vice versa, like any Archipelago world.
When you receive an item, the web client updates your unlocked tools / rounds / fragments.

## Where are the options?

Wikipelago is a custom world, so there is no options page on archipelago.gg.
Use the YAML template from [Releases](https://github.com/Dreskn/Wikipelago-Continued/releases) (also in [`yaml/Wikipelago.yaml`](../yaml/Wikipelago.yaml)), and read the [Options guide](options.md) for explanations.
