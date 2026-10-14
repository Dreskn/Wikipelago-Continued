# Wikipelago Continued

Wikipelago is a custom [Archipelago](https://archipelago.gg/) world inspired by wiki racing.
Each round gives you a **Start** article and a **Target** article; navigate Wikipedia links to reach the target, send checks, collect progression, and finish your goal.

Play in the browser on nine Wikipedia languages, with Topic Realms, letter-pair bingo, traps and DeathLink, and a Journey map of your path.

This repository is a continued fork of the [original Wikipelago](https://github.com/Skrumptily69/Wikipelago).

## Quick start

- **Just try it:** open https://wikipelago.dreskn.fr/ and press **Practice**. No room and nothing to install: random targets, a bingo board and one open Realm.
- **Play in a multiworld:** the host installs `wikipelago.apworld` from [Releases](https://github.com/Dreskn/Wikipelago-Continued/releases) and generates with your YAML (template: [`yaml/Wikipelago.yaml`](yaml/Wikipelago.yaml)). You open the web client and connect with the room address, your slot name and the password, if any. Step by step: [Setup guide](docs/setup.md).
- **Goals:** collect Knowledge Fragments and find the answer to the **Grand Goal** question, or clear every Topic Realm as **Realm Master**.

## What is this?

- **[Overview](docs/overview.md)** — how the game works (rounds, Realms, items, goals)
- **[Web client UI](docs/ui.md)** — numbered HUD map of the browser client
- **[Setup guide](docs/setup.md)** — install the apworld, generate a seed, connect and play
- **[Options](docs/options.md)** — YAML settings explained (length, Realms and branches, bingo, sanities, lenses, categories, deaths, traps)
- **[Releases](https://github.com/Dreskn/Wikipelago-Continued/releases)** — download `wikipelago.apworld` and the player YAML template
- **[FAQ](docs/faq.md)** — common generate errors and play questions

## Play

Live web client: https://wikipelago.dreskn.fr/

Archipelago version: **0.6.7 or newer**  
World version: **1.1.1**

Looking for more info about Archipelago in general? See the [website](https://archipelago.gg/) or [GitHub](https://github.com/ArchipelagoMW/Archipelago).

## Report a bug

- [GitHub Issues](https://github.com/Dreskn/Wikipelago-Continued/issues) (needs a free GitHub account), or
- the [Wikipelago discussion thread](https://discord.com/channels/731205301247803413/1462007968902938768) on the Archipelago Discord.

Mention the Wikipedia language, what you clicked, and what you expected to happen.

## Credits

Original Wikipelago by [Skrumptily69](https://github.com/Skrumptily69/Wikipelago).

Continued development and hosting by [Dreskn](https://github.com/Dreskn/Wikipelago-Continued).

Articles are loaded live from [Wikipedia](https://www.wikipedia.org/). Their text is written by Wikipedia's contributors and available under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/); images keep their own licences. Wikipelago is not affiliated with the Wikimedia Foundation.

## License

This project is licensed under the [MIT License](LICENSE). The icons are [Lucide](https://lucide.dev) (ISC; some icons derived from Feather, MIT). Fonts are Fraunces, Instrument Sans, JetBrains Mono and Libertinus Serif, self-hosted under the SIL Open Font License. Their notices and the list of icons used are in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

The original author confirmed they had abandoned the project and gave permission to continue public development (including releases and hosting) while keeping attribution for the original idea and earlier versions.
