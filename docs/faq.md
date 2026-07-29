# FAQ

## What does `Wikipelago item math invalid` “required progression items exceed locations” mean?

That’s an intentional failsafe. Your YAML asks for more required items than the seed has locations. Generation stops early so Archipelago doesn’t build a broken pool.

Fix it by either:

- **Adding locations** — raise `check_count`, and/or enable bingo / use a larger grid / more boards
- **Removing item pressure** — turn down sanities (especially searchsanity), lenses, traps, unlock counts, or ease Round Access (`start_rounds_unlocked` / `rounds_per_unlock`)
