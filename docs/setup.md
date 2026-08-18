# Wikipelago Setup Guide

## Required software

### Host / organizer (generates the seed)

- [Archipelago](https://github.com/ArchipelagoMW/Archipelago/releases) **0.6.7** or compatible
- `wikipelago.apworld` from this repo’s [Releases](https://github.com/Dreskn/Wikipelago-Continued/releases)
- Player YAML files (template also on Releases, or [`yaml/Wikipelago.yaml`](../yaml/Wikipelago.yaml))

### Players

- A modern browser
- The live web client: https://wikipelago.dreskn.fr/
- Room address + port, slot name, and password (if the room uses one)

Players do **not** need to install the apworld unless they also generate or host.

## Install the apworld (host)

1. Download `wikipelago.apworld` from [Releases](https://github.com/Dreskn/Wikipelago-Continued/releases).
2. Install it either way:
   - Double-click the `.apworld` so the Archipelago Launcher installs it, **or**
   - Place it in your Archipelago `custom_worlds` folder.
3. Restart the Archipelago Launcher if it was already open.

## Create your YAML

1. Copy the player template (`Wikipelago.yaml`) into your Archipelago `Players` folder.  
   After installing the apworld you can also use **Generate Template Options** in the Launcher.
2. Edit `name` (slot name) and any options you want.  
   See the [Options guide](options.md) for what each setting does.
3. Put one YAML per player/slot in `Players` (remove YAMLs for people not in this seed).

## Generate and host

1. In the Archipelago Launcher, click **Generate**.
2. Find the output zip under your Archipelago `output` folder.
3. Host either:
   - locally via **Host** in the Launcher, or
   - on the website by uploading the zip to https://archipelago.gg/uploads
4. Share with players:
   - server address + port (example: `archipelago.gg:PORT`)
   - slot name
   - password (if any)
   - web client URL: https://wikipelago.dreskn.fr/

For general Archipelago generation help, see the [official setup tutorial](https://archipelago.gg/tutorial/Archipelago/setup/en).

## Connect and play (player)

1. Open https://wikipelago.dreskn.fr/
2. Optional: pick a **UI language** in the top-right dropdown (menus and toasts only — your YAML still chooses which Wikipedia you race on). The [UI map](ui.md) labels each control.
3. Enter server, slot name, and password (if used).
4. Click **Connect**. The top badge turns **Connected**.
5. Play available rounds: Start → Target by clicking Wikipedia links.
6. Collect Knowledge Fragments to unlock the Grand Goal question, then find the answer page.

**Practice** (no room needed) uses the same client and a random article pool in the UI language. It does not connect to Archipelago and does not send checks.

### Tips

- Only in-article wiki link clicks count toward checks.
- Hover the Target title for a short description of that page.
- **Journey** (on the Progression card, once you are in a game) shows the path of pages you have marked.
- Side cards have a small hide control on the header if you want more room for the article.
- If the badge says **Offline**, you are no longer attached to the room — reconnect with the same slot; the client will try to resume. Prefer finishing a round before closing the tab when possible.
- File / Template / Wikipedia-namespace pages are blocked on purpose; pick another link.
- For how rounds, items, branches, bingo, and the goal work, see the [Overview](overview.md).

## Compatibility

| Piece | Version |
| --- | --- |
| Wikipelago world (`apworld`) | **1.0-beta1** (`world_version` **1.0.0**) |
| Recommended Archipelago | **0.6.7** |
| Web client | hosted link above (always use the current deploy) |

The player YAML template pins these via top-level `requires` (`version` + `game.Wikipelago`) so generation fails if the host apworld is too old.
Hosts and generators should still use a matching apworld for the seed they create.
Players only need a browser and the web client.
