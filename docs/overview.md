# Wikipelago Overview

## What is Wikipelago?

Wikipelago is a custom Archipelago world inspired by wiki racing.
You play in a browser: each check is a **round** with a **Start** article and a **Target** article.
Click Wikipedia links to reach the target; when you do, that location is checked in Archipelago.

There is no separate desktop client to install for players — use the [hosted web client](https://wikipelago.dreskn.fr/).

## The web client

The page is split in two: the **article** on the left, and your **HUD** on the right.
A numbered map of every control is in the [web client UI](ui.md) guide. On a narrow screen such as a phone, the client switches to a one-column layout (see [On a phone](#on-a-phone)).

- **Article** — the current Wikipedia page. Only in-article wiki links count as moves. File, Template, Wikipedia-namespace, and similar non-article pages are blocked.
- **Connection** — server, slot, password, **Connect**, and **Practice**.
- **Progression** — round track, current targets, Knowledge Fragments, Grand Goal, the **Realms** checklist (seeds with branches), and Compass. **Journey** opens a map of pages you have visited this seed.
- **Items** — tools you have found (Back, Reroll, Search, Compass, Branch Key or Portals). Locked tools stay grey.
- **Bingo / Lenses / Sanity / Difficulty** — extra cards appear when your seed uses those options.
- **Are you really stuck?** — a link to an external wiki-path solver. It does not send checks for you.

UI language (the dropdown) only changes menus, toasts and the language in Practice mode. The Wikipedia edition you play on in an AP game is set in your YAML (`wikipedia_language`) and does not follow the dropdown.

**Practice** loads random articles from the same language pool with no Archipelago room. Use it to learn the client. It also gives you a 5×5 letter-pair bingo board and one open Realm (5 targets on one topic); when the board is full or the Realm is cleared, a **New board** / **New Realm** button deals another. Nothing is sent to Archipelago.

### Journey

**Journey** (on the Progression card) draws the pages you have visited as one path of points.

- Hover a point to see the page title, what happened there (a finished round, Grand Goal, bingo stamp...) and the same short summary as the Target preview.
- Click a point to open that page on Wikipedia in a new tab. It opens outside the game, so it does not count as a move.
- On a touch screen, the first tap on a point shows its info and a second tap opens the page.
- **Full screen** shows the map on the whole screen. The button is hidden when the browser can't do it (on iPhone, for example).
- **Pop out** opens the Journey in its own browser window. It is not offered in the phone layout.

### On a phone

Below 900 px wide (most phones), the client shows one column instead of two:

- A **bar** stays at the top of the screen while you scroll the article. It shows your current targets: the main road, the Grand Goal question once it is revealed, and up to two branch / Realm targets (**+N more** opens the menu for the rest). Under them are the Compass hint (once you have the Wiki Compass), a search button (needs the Ctrl+F Lens) and **SOS** (teleport to a random page, 60 s cooldown).
- The **menu** button in the bar swaps the article for the menu: the top bar (status, language, theme and display settings), then the cards (Connection, Progression, Items...). Press it again (it shows ✕) to go back to the article where you left it. After you open the menu this way, your phone's Back button closes it instead of turning the article back a page.
- Before a game starts the menu is open so you can connect or start Practice; once the game starts you see the article.
- Touch screens have no hover: tap a target once to see its preview, and tap it again to hide it.

From 900 px wide (a wider window, or some tablets turned sideways), the two columns come back.

## What does randomization do?

Archipelago generates Start → Target rounds for your slot and shuffles items into the multiworld — Round Access, Knowledge Fragments, tools (Progressive Back, Progressive Reroll, Ctrl+F Lens, Wiki Compass), optional letter-pair bingo boards / Progressive Bingo Cards / Progressive Bingo Stamps, optional **Branch Keys** or Realm **Portals**, optional lenses, and optional traps when enabled. Completing rounds and bingo board lines sends checks; receiving items unlocks more rounds and tools until you can finish your goal.

Optional **deaths** / **DeathLink** / **link bombs** and **Foggy Links** / **Missing Links** / **Wrong Wiki** traps are off by default — see the [Options guide](options.md).

## How do rounds work?

1. Navigate by clicking in-article Wikipedia links only.
2. Reach the Target article to send the location check.
3. Receive a new Target, repeat.

Only some rounds are available at the start (`start_rounds_unlocked` in your YAML).
Additional rounds unlock when you receive **Round Access** items (`rounds_per_unlock` controls how many each one opens).

Hover the **Target** title (or tap it on a touch screen) for a short Wikipedia blurb (description plus lead paragraph).

## Crossroads and side branches

If your YAML sets `branch_count` above 0, some main-road rounds become **crossroads**. Finding **Branch Keys** opens a side chain of extra Start → Target rounds.

- Branch 1 needs 1 key, Branch 2 needs 2 keys, and so on, plus the matching finished crossroad.
- Unlocked branches stay live together: one page visit can finish the main target, a branch target, and still stamp bingo.
- Extra keys beyond the number of branches still count as progression items for the multiworld; they do not open more branches.

The Progression card lists each live branch target under the main road. **Journey** shows main-road, branch, and other visited pages on one path.

**Topic Realms** (1.1, `topic_portals: true`) turn every branch into a **Realm** with its own topic (History, Music, Sports, ...). Instead of Branch Keys, each Realm opens with its own **Portal** item (`History Portal`, `Music Portal`, ...), so Realms open in whatever order their Portals arrive.

- A Realm opens once you have its Portal **and** have finished its crossroad round (either order).
- Realm targets come from the Realm's topic, and rerolls stay on topic.
- Each Realm has its own color on the round track, in the target list, in the **Realms** checklist and on the Journey map. The main road stays brass.

Limits and details: [Options — Topic Realms](options.md#topic-realms-11).

## What is the goal?

It depends on `goal` in your YAML.

**Grand Goal** (`goal: grand_goal`, the default): collect enough **Knowledge Fragments** (count set by `required_fragments`). The pool may contain extras (`additional_fragments_in_pool`); only the required count unlocks the goal. The Grand Goal is then revealed as a **closed question** in your wiki language. Reach the answer article to finish your slot.

The question comes from that language’s Grand Goal pool (answer page preferred from your enabled categories). Old YAML presets such as `goal_article_preset` are ignored.

**Realm Master** (`goal: realm_master`, 1.1): clear the last round of every branch / Realm. There are no Knowledge Fragments and no Grand Goal question; the **Realms to master** checklist shows what is left. It needs `branch_count` of at least 1 and is built for Topic Realms (it also works with plain Branch Keys). The main road only has to take you to each crossroad; if you finish it first, the target line reads "Main road cleared — finish your Realms". See [Options — Goal](options.md#goal).

## Useful items

- **Progressive Back** — browser back navigation (limited depth per round)
- **Progressive Reroll** — raises per-round target reroll charges. Each use changes every current target at once (main path + branches), not the Grand Goal.
- **Progressive Bingo Card** — unlocks an extra letter-pair bingo board (when bingo is enabled)
- **Progressive Bingo Stamp** — stamps one empty bingo cell on one unlocked board (once per seed; YAML `bingo_stamp_unlocks`)
- **Ctrl+F Lens** — in-page search
- **Wiki Compass** — warmer/colder hints toward your nearest live target (main road or an open branch / Realm, named once branches are open)
- **Branch Key** — opens a side branch when your seed uses crossroads
- **Portal** (`History Portal`, `Music Portal`, ...) — opens that topic's Realm when your seed uses Topic Realms (replaces Branch Keys)
- **Round Access** — unlocks more rounds
- **Knowledge Fragment** — required toward the Grand Goal (not in Realm Master seeds)
- **Footnote** — filler; does nothing, pads the item pool

Optional toggles can also gate search letters, scroll speed, and Wikipedia page elements (tables, images, infoboxes, etc.) behind Lens items. Those are off by default — see [Options](options.md).

## Letter-pair bingo

When bingo is on, page titles stamp letter pairs on your board(s). Completing a row, column, diagonal, or the full card sends a check. First two letters are used, so "1st" will stamp letters ST, accentuated letters (é, ü...) are counted as distinct or same letters following Scrabble rules (eg French treats é, è, ë and ê as E, while Polish treats ź and z as distinct) 

- Click a board to open a larger overlay with zoom.

## Deaths and traps (when enabled)

- **Deaths** — a forward-revisit of a page you already visited this round jumps you to a random article. Unlocks and fragments are kept.
- **DeathLink** — that death is shared with other DeathLink games, and theirs can hit you.
- **Link bombs** — a few links on each page are marked with a bomb icon; clicking one is a death (never the Target or Grand Goal link).
- **Traps** — Foggy Links hide link text as `[Link]`, Missing Links remove some links, Wrong Wiki shows the next page on another language edition. If several traps arrive at once, they wait in a queue and apply **one per page**.

## What can appear in other players' worlds?

Progression and useful items from Wikipelago can be placed in other games, and vice versa, like any Archipelago world.
When you receive an item, the web client updates your unlocked tools / rounds / fragments.

## Where are the options?

Wikipelago is a custom world, so there is no options page on archipelago.gg.
Use the YAML template from [Releases](https://github.com/Dreskn/Wikipelago-Continued/releases) (also in [`yaml/Wikipelago.yaml`](../yaml/Wikipelago.yaml)), and read the [Options guide](options.md) for explanations.

Generate errors and other play questions: [FAQ](faq.md).
