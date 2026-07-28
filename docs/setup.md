# Wikipelago Setup Guide

## Required software

### Host / organizer (generates the seed)

- [Archipelago](https://github.com/ArchipelagoMW/Archipelago/releases) **0.6.7** or compatible
- `Wikipelago.apworld` from this repo’s [Releases](https://github.com/Dreskn/Wikipelago-Continued/releases)
- Player YAML files (template also on Releases, or [`yaml/Wikipelago.yaml`](../yaml/Wikipelago.yaml))

### Players

- A modern browser
- The live web client: https://wikipelago-contd.onrender.com/
- Room address + port, slot name, and password (if the room uses one)

Players do **not** need to install the apworld unless they also generate or host.

## Install the apworld (host)

1. Download `Wikipelago.apworld` from [Releases](https://github.com/Dreskn/Wikipelago-Continued/releases).
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
   - web client URL: https://wikipelago-contd.onrender.com/

For general Archipelago generation help, see the [official setup tutorial](https://archipelago.gg/tutorial/Archipelago/setup/en).

## Connect and play (player)

1. Open https://wikipelago-contd.onrender.com/
2. Enter server, slot name, and password (if used).
3. Click connect.
4. Play available rounds: Start → Target by clicking Wikipedia links.
5. Collect Knowledge Fragments and clear the Grand Goal when ready.

### Tips

- Only in-article wiki link clicks count toward checks.
- If you disconnect, reconnect with the same slot; the client will try to resume. Prefer finishing a round before closing the tab when possible.
- For how rounds, items, and the goal work, see the [Overview](overview.md).

## Compatibility

| Piece | Version |
| --- | --- |
| Wikipelago world (`apworld`) | **0.5.0-Bingo!** |
| Recommended Archipelago | **0.6.7** |
| Web client | hosted link above (always use the current deploy) |

Hosts and generators should use a matching apworld version for the seed they create.
Players only need a browser and the web client.
