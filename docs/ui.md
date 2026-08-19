# Web client UI

Play at https://wikipelago.dreskn.fr/. The page is the Wikipedia article on the left and the HUD cards on the right.

![Wikipelago web client with numbered HUD callouts](ui-annotated.png)

Numbered callouts match the list below. Optional cards (Sanity, Bingo, Lenses, Difficulty) only appear when your seed uses those options.

## Legend

1. **current build** — title, branch/commit tag, and client version.
2. **UI language** — menus and toasts only; the Wikipedia edition comes from your YAML.
3. **Connected / Offline / Practice** — room status. Offline means reconnect; Practice is not a seed.
4. **current page** — article title you are on.
5. **Wikipedia content** — in-article wiki links are the only moves that count.
6. **room login** — server, slot, and password. After connect this card shrinks to the room name plus Disconnect.
7. **join room** — Connect to the Archipelago slot.
8. **no Archipelago** — Practice with random articles and no room.
9. **path map** — Journey: pages you have marked this seed.
10. **collapse card** — shrink a HUD card to its header.
11. **seed progress** — rounds unlocked and cleared.
12. **pages to reach** — live Start → Target (main road and any open branch).
13. **new target** — Reroll the current target (charges per round; not the Grand Goal).
14. **goal items** — Knowledge Fragments toward revealing the Grand Goal.
15. **warmer/colder** — Compass hint when you have Wiki Compass.
16. **unlocked tools** — Back, Reroll, Search, Compass, and similar; locked tools stay grey.
17. **searchsanity option** — search-letter unlocks when that sanity is on.
18. **title stamps** — letter-pair bingo boards (click a board to zoom).
19. **fill cell** — spend a Progressive Bingo Stamp on one empty cell.
20. **collapse board** — Hide next to **Board N**.
21. **hidden page parts** — lens toggles (tables, images, infobox, and so on).
22. **deaths traps bombs** — Deaths, DeathLink, traps, and link bombs when enabled.
23. **path solver** — external wiki-path helper; it does not send checks.
24. **donate links** — Support Wikipelago and Support Wikipedia.

For how rounds, items, and the Grand Goal work, see the [Overview](overview.md). For YAML flags that show or hide these cards, see [Options](options.md).
