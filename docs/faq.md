# FAQ

## How do I report a bug?

On the Archipelago Discord, in the [Wikipelago discussion thread](https://discord.com/channels/731205301247803413/1462007968902938768).

## What does `Wikipelago item math invalid` “required progression items exceed locations” mean?

That’s an intentional failsafe. Your YAML asks for more required items than the seed has locations. Generation stops early so Archipelago doesn’t build a broken pool.

Fix it by either:

- **Adding locations** — raise `check_count`, and/or enable bingo / use a larger grid / more boards, and/or enable branches
- **Removing item pressure** — turn down sanities (especially searchsanity), lenses, traps, unlock counts, or ease Round Access (`start_rounds_unlocked` / `rounds_per_unlock`)

## I don't understand how bingo works. How do I stamp a letter pair like FC?

Bingo only looks at the **start of the page title**. It skips spaces, digits, hyphens, and other punctuation, then takes the **first two letters**. Those two letters are the pair that gets stamped.

- **FC Barcelona** → **FC** (that cell stamps)
- **Paris FC** → **PA** (does not stamp FC)
- **1st** → **ST** (the `1` is ignored)

The Wikipedia language of the seed (`wikipedia_language`) decides which accented letters count as their own letter. That is not the UI dropdown in the corner.

### Accents (Scrabble rules)

If a letter is **its own tile** for that language, it stays that letter on the board (`Ñ` stays `Ñ`). If it is **not** a tile, it is treated as the unaccented A–Z letter (`é` → `E`).

| Wiki | Own letters (besides A–Z) | Everything else |
| --- | --- | --- |
| English, French, Italian, Dutch | none | all accents fold (`é è ê ë` → E, `à â` → A... `Électricité` → **EL**) |
| Spanish | **Ñ** | `á é í ó ú ü` fold (`Ñandú` → **ÑA**) |
| Portuguese | **Ç** | `á â ã é ê í ó ô õ ú` fold (`Ação` → **AÇ**) |
| German | **Ä Ö Ü** | `ß` / `ẞ` counts as **SS** (`Äpfel` → **ÄP**, a title starting with ß → **SS**) |
| Swedish | **Å Ä Ö** | other accents fold (`Öl` → **ÖL**) |
| Polish | **Ą Ć Ę Ł Ń Ó Ś Ź Ż** | those stay distinct from the unaccented letter (`Łódź` → **ŁÓ**) |

French `é` is just E. Polish `Ź` is not Z. Same idea for the other extras in the table.

## The top badge says Offline.

You might get disconnected if the AP room goes to sleep, or if the server deploys a new update. Refresh your page and reconnect with the same server, slot, and password. Checks you already sent are still in Archipelago; you just need the connection again.

## Why is the Wikipedia language different from the dropdown in the corner?

The dropdown only translates buttons, labels, and toasts. Which Wikipedia you race on is `wikipedia_language` in your YAML (and Practice follows the UI language).

## A link did nothing and I got a warning about the page type.

Non-article namespaces (File, Template, Wikipedia:, Portail, Plik, and the same idea in other languages) are blocked so you stay in the client. Pick a normal article link.

## What happened to `goal_article_preset` / `random_goal_article`?

They are ignored. The Grand Goal is always a closed question from that wiki language’s goal pool. Old YAMLs still generate; they just no longer pick a preset series.
