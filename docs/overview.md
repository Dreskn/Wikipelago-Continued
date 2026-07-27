# Wikipelago Overview

## What is Wikipelago?

Wikipelago is a custom Archipelago world inspired by wiki racing.
You play in a browser: each check is a **round** with a **Start** article and a **Target** article.
Click Wikipedia links to reach the target; when you do, that location is checked in Archipelago.

There is no separate desktop client to install for players — use the [hosted web client](https://wikipelago-contd.onrender.com/).

## What does randomization do?

Archipelago generates Start → Target rounds for your slot and shuffles items into the multiworld — Round Access, Knowledge Fragments, useful tools (Back Button, Ctrl+F Lens, Wiki Compass), optional lenses, and optional traps when enabled. Completing rounds sends checks; receiving items unlocks more rounds and tools until you can finish the Grand Goal.

Optional **deaths** / **DeathLink** / **link bombs** and **Foggy Links** / **Missing Links** traps are off by default — see the [Options guide](options.md).

## How do rounds work?

1. Navigate by clicking in-article Wikipedia links only (typed URLs / free navigation do not count as checks).
2. Reach the Target article to send the location check.
3. Optional: **Reroll** the current target up to 3 times per round if it’s obscure (including the final round; Grand Goal itself cannot be rerolled).

Only some rounds are available at the start (`start_rounds_unlocked` in your YAML).
Additional rounds unlock when you receive **Round Access** items (`rounds_per_unlock` controls how many each one opens).

## What is the goal?

Collect enough **Knowledge Fragments** (count set by `required_fragments`), then complete the **Grand Goal**: reach the final goal article with enough fragments.

The goal article can be random from your enabled categories, or a fixed preset — see the [Options guide](options.md).

## Useful items

- **Back Button** — browser back navigation
- **Ctrl+F Lens** — in-page search
- **Wiki Compass** — warmer/colder hints toward the target
- **Round Access** — unlocks more rounds
- **Knowledge Fragment** — required toward the Grand Goal
- **Footnote** — filler; does nothing, pads the item pool

Optional toggles can also gate search letters, scroll speed, and Wikipedia page elements (tables, images, infoboxes, etc.) behind Lens items. Those are off by default — see [Options](options.md).

## What can appear in other players' worlds?

Progression and useful items from Wikipelago can be placed in other games, and vice versa, like any Archipelago world.
When you receive an item, the web client updates your unlocked tools / rounds / fragments.

## Where are the options?

Wikipelago is a custom world, so there is no options page on archipelago.gg.
Use the YAML template from [Releases](https://github.com/Dreskn/Wikipelago-Continued/releases) (also in [`yaml/Wikipelago.yaml`](../yaml/Wikipelago.yaml)), and read the [Options guide](options.md) for explanations.
