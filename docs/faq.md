# FAQ

## What does `Wikipelago item math invalid` “required progression items exceed locations” mean?

That’s an intentional failsafe. Your YAML asks for more required items than the seed has locations. Generation stops early so Archipelago doesn’t build a broken pool.

Fix it by either:

- **Adding locations** — raise `check_count`, and/or enable bingo / use a larger grid / more boards, and/or enable branches
- **Removing item pressure** — turn down sanities (especially searchsanity), lenses, traps, unlock counts, or ease Round Access (`start_rounds_unlocked` / `rounds_per_unlock`)

## The top badge says Offline.

Reconnect with the same server, slot, and password. The client tries to put you back on the last page. Checks you already sent are still in Archipelago; you just need the connection again.

## Why is the Wikipedia language different from the dropdown in the corner?

The dropdown only translates buttons, labels, and toasts. Which Wikipedia you race on is `wikipedia_language` in your YAML (and Practice follows the UI language).

## Why did the next page open on another Wikipedia?

That’s the **Wrong Wiki** trap. The following click tries to bring you back to your seed language when that article exists there. Traps apply one page at a time if several arrive together.

## A link did nothing and I got a warning about the page type.

Non-article namespaces (File, Template, Wikipedia:, Portail, Plik, and the same idea in other languages) are blocked so you stay in the client. Pick a normal article link.

## What happened to `goal_article_preset` / `random_goal_article`?

They are ignored. The Grand Goal is always a closed question from that wiki language’s goal pool. Old YAMLs still generate; they just no longer pick a preset series.

## `trap_type: both` still in my YAML — is that broken?

No. `both` still means every trap kind. The current name is `all`. Prefer `all` on new YAMLs.
