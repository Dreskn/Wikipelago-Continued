
import argparse
import asyncio
import json
import logging
import os
import time
import urllib.parse
import urllib.request
import uuid
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import websockets
from aiohttp import web

logging.basicConfig(level=logging.INFO, format="%(message)s")
LOG = logging.getLogger("wikipelago-cloud")

# Client/release label for the hosted UI (independent of apworld tag until a release cut).
CLIENT_VERSION = "0.3.0-Continued"


def build_info() -> dict[str, Any]:
    """Deploy identity for the UI. Render injects RENDER_GIT_* on hosted services."""
    branch = (os.environ.get("RENDER_GIT_BRANCH") or "").strip() or "local"
    commit_full = (os.environ.get("RENDER_GIT_COMMIT") or "").strip()
    commit = commit_full[:7] if commit_full else ""
    service = (os.environ.get("RENDER_SERVICE_NAME") or "").strip()
    staging = branch not in ("main", "master")
    return {
        "ok": True,
        "version": CLIENT_VERSION,
        "branch": branch,
        "commit": commit,
        "commit_full": commit_full,
        "service": service,
        "staging": staging,
    }

DEFAULT_ITEMS = {
    "Knowledge Fragment": 1_870_001,
    "Back Button": 1_870_002,
    "Wiki Compass": 1_870_003,
    "Ctrl+F Lens": 1_870_004,
    "Progressive Scroll Speed": 1_870_008,
    "Round Access": 1_870_007,
    "Table Lens": 1_870_009,
    "Picture Lens": 1_870_010,
    "Lead Lens": 1_870_011,
    "Infobox Lens": 1_870_012,
    "Contents Lens": 1_870_013,
    "Navbox Lens": 1_870_014,
    "Hatnote Lens": 1_870_015,
    "Reference Lens": 1_870_016,
    "Foggy Links": 1_870_046,
    "Missing Links": 1_870_047,
}

TRAP_ITEM_NAMES = frozenset({"Foggy Links", "Missing Links"})
LINK_BOMB_DENSITY_COUNTS = {0: 1, 1: 5, 2: 20}

SESSION_TTL_SECONDS = 60 * 60 * 6
# Transient AP drops: retry a few times, then stop and surface last_error.
# ConnectionRefused (bad password/slot) never retries.
MAX_AP_CONNECT_ATTEMPTS = 3


def normalize_title(title: str) -> str:
    spaced = " ".join(title.replace("_", " ").strip().split())
    deaccented = "".join(ch for ch in unicodedata.normalize("NFKD", spaced) if not unicodedata.combining(ch))
    return deaccented.casefold()


TITLE_CANONICALS: dict[str, str] = {
    normalize_title("Pokemon"): "Pok\u00e9mon",
    normalize_title("Pokemon Red and Blue"): "Pok\u00e9mon Red and Blue",
    normalize_title("Pokemon Gold and Silver"): "Pok\u00e9mon Gold and Silver",
    normalize_title("Pokemon Scarlet and Violet"): "Pok\u00e9mon Scarlet and Violet",
    normalize_title("Pokemon Yellow"): "Pok\u00e9mon Yellow",
    normalize_title("Pokemon Ruby and Sapphire"): "Pok\u00e9mon Ruby and Sapphire",
    normalize_title("Pokemon Diamond and Pearl"): "Pok\u00e9mon Diamond and Pearl",
    normalize_title("Pokemon Black and White"): "Pok\u00e9mon Black and White",
    normalize_title("Pokemon Sun and Moon"): "Pok\u00e9mon Sun and Moon",
    normalize_title("Pokemon Legends: Arceus"): "Pok\u00e9mon Legends: Arceus",
    normalize_title("Pokemon Go"): "Pok\u00e9mon Go",
    normalize_title("Pokemon Trading Card Game"): "Pok\u00e9mon Trading Card Game",
    normalize_title("La La Land (film)"): "La La Land",
    normalize_title("Her (film)"): "Her (2013 film)",
    normalize_title("Clue (board game)"): "Cluedo",
}


TITLE_ALIASES: dict[str, set[str]] = {
    normalize_title("La La Land (film)"): {normalize_title("La La Land")},
    normalize_title("Her (film)"): {normalize_title("Her (2013 film)"), normalize_title("Her")},
    normalize_title("Clue (board game)"): {normalize_title("Cluedo")},
}

@dataclass
class SessionState:
    connected_to_ap: bool = False
    ap_server: str = ""
    slot_name: str = ""
    check_count: int = 10
    required_fragments: int = 8
    start_rounds_unlocked: int = 5
    rounds_per_unlock: int = 5
    searchsanity: bool = False
    scrollsanity: bool = False
    scroll_speed_upgrades: int = 5
    search_starting_letters: list[str] = field(default_factory=list)
    randomize_tables: bool = False
    randomize_pictures: bool = False
    randomize_incipit: bool = False
    randomize_infoboxes: bool = False
    randomize_toc: bool = False
    randomize_navboxes: bool = False
    randomize_hatnotes: bool = False
    randomize_references: bool = False
    deaths: bool = False
    death_link: bool = False
    link_bombs: bool = False
    link_bomb_density: int = 0
    trap_type: int = 0
    trap_link: bool = False
    pending_events: list[dict[str, Any]] = field(default_factory=list)
    round_pairs: list[dict[str, str]] = field(default_factory=lambda: [{"start": "Wikipedia", "target": "Philosophy"}])
    location_round_ids: list[int] = field(default_factory=list)
    location_grand_goal: int | None = None
    item_ids: dict[str, int] = field(default_factory=lambda: DEFAULT_ITEMS.copy())
    received_items: list[int] = field(default_factory=list)
    checked_locations: set[int] = field(default_factory=set)
    round_index: int = 0
    clicks_used: int = 0
    last_page: str = ""
    warmer_colder: str | None = None
    last_distance_estimate: int | None = None
    boss_completed: bool = False
    goal_status_sent: bool = False
    last_error: str = ""
    last_seen: float = field(default_factory=lambda: time.time())
    slot: int = 0
    player_names: dict[int, str] = field(default_factory=dict)
    slot_games: dict[int, str] = field(default_factory=dict)
    item_id_to_name: dict[str, dict[int, str]] = field(default_factory=dict)

    def current_target(self) -> str:
        if self.round_index >= len(self.round_pairs):
            return self.round_pairs[-1]["target"] if self.round_pairs else ""
        return self.round_pairs[self.round_index]["target"]

    def current_start(self) -> str:
        if self.round_index >= len(self.round_pairs):
            return self.round_pairs[-1]["start"] if self.round_pairs else "Wikipedia"
        return self.round_pairs[self.round_index]["start"]

    def goal_article(self) -> str:
        return self.round_pairs[-1]["target"] if self.round_pairs else ""

    def fragments(self) -> int:
        fragment_id = self.item_ids.get("Knowledge Fragment", DEFAULT_ITEMS["Knowledge Fragment"])
        return sum(1 for item in self.received_items if item == fragment_id)

    def round_access_count(self) -> int:
        round_access_id = self.item_ids.get("Round Access", DEFAULT_ITEMS["Round Access"])
        return sum(1 for item in self.received_items if item == round_access_id)

    def has_item(self, name: str) -> bool:
        item_id = self.item_ids.get(name, DEFAULT_ITEMS.get(name, -1))
        return item_id in self.received_items

    def item_count(self, name: str) -> int:
        item_id = self.item_ids.get(name, DEFAULT_ITEMS.get(name, -1))
        return sum(1 for item in self.received_items if item == item_id)

    def owned_search_letters(self) -> list[str]:
        letters = set(self.search_starting_letters)
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            if self.has_item(f"Search Letter {letter}"):
                letters.add(letter)
        return sorted(letters)

    def boss_ready(self) -> bool:
        return self.fragments() >= self.required_fragments

    def unlocked_rounds(self) -> int:
        step = max(1, self.rounds_per_unlock)
        unlock_items = self.round_access_count()
        return min(self.check_count, self.start_rounds_unlocked + (unlock_items * step))

    def to_status(self) -> dict[str, Any]:
        return {
            "connected_to_ap": self.connected_to_ap,
            "ap_server": self.ap_server,
            "slot_name": self.slot_name,
            "current_start": self.current_start(),
            "current_target": self.current_target(),
            "goal_article": self.goal_article(),
            "round": min(self.round_index + 1, self.check_count),
            "check_count": self.check_count,
            "clicks_used": self.clicks_used,
            "fragments": self.fragments(),
            "required_fragments": self.required_fragments,
            "start_rounds_unlocked": self.start_rounds_unlocked,
            "rounds_per_unlock": self.rounds_per_unlock,
            "round_access_count": self.round_access_count(),
            "unlocked_rounds": self.unlocked_rounds(),
            "searchsanity": self.searchsanity,
            "scrollsanity": self.scrollsanity,
            "scroll_speed_upgrades": self.scroll_speed_upgrades,
            "scroll_speed_level": self.item_count("Progressive Scroll Speed"),
            "back_button_unlocked": self.has_item("Back Button"),
            "ctrl_f_unlocked": self.has_item("Ctrl+F Lens"),
            "search_letters": self.owned_search_letters(),
            "compass_unlocked": self.has_item("Wiki Compass"),
            "randomize_tables": self.randomize_tables,
            "randomize_pictures": self.randomize_pictures,
            "randomize_incipit": self.randomize_incipit,
            "randomize_infoboxes": self.randomize_infoboxes,
            "randomize_toc": self.randomize_toc,
            "randomize_navboxes": self.randomize_navboxes,
            "randomize_hatnotes": self.randomize_hatnotes,
            "randomize_references": self.randomize_references,
            "deaths": self.deaths,
            "death_link": self.death_link,
            "link_bombs": self.link_bombs,
            "link_bomb_density": self.link_bomb_density,
            "link_bomb_count": LINK_BOMB_DENSITY_COUNTS.get(self.link_bomb_density, 1),
            "trap_type": self.trap_type,
            "trap_link": self.trap_link,
            "pending_events": list(self.pending_events),
            "tables_unlocked": (not self.randomize_tables) or self.has_item("Table Lens"),
            "pictures_unlocked": (not self.randomize_pictures) or self.has_item("Picture Lens"),
            "incipit_unlocked": (not self.randomize_incipit) or self.has_item("Lead Lens"),
            "infoboxes_unlocked": (not self.randomize_infoboxes) or self.has_item("Infobox Lens"),
            "toc_unlocked": (not self.randomize_toc) or self.has_item("Contents Lens"),
            "navboxes_unlocked": (not self.randomize_navboxes) or self.has_item("Navbox Lens"),
            "hatnotes_unlocked": (not self.randomize_hatnotes) or self.has_item("Hatnote Lens"),
            "references_unlocked": (not self.randomize_references) or self.has_item("Reference Lens"),
            "warmer_colder": self.warmer_colder,
            "boss_ready": self.boss_ready(),
            "boss_completed": self.boss_completed,
            "last_page": self.last_page,
            "last_error": self.last_error,
        }


class APConnection:
    def __init__(self, state: SessionState):
        self.state = state
        self.ws: Any = None
        self.reader_task: asyncio.Task | None = None
        self.send_lock = asyncio.Lock()
        self.server = ""
        self.slot_name = ""
        self.password = ""
        self.items_seen = 0
        self.link_cache: dict[str, set[str]] = {}
        self.resolved_title_cache: dict[str, str] = {}
        self._scout_waiters: dict[int, asyncio.Future] = {}
        self._datapackage_requested = False

    async def connect(self, server: str, slot_name: str, password: str = "") -> None:
        self.server = server
        self.slot_name = slot_name
        self.password = password

        self.state.ap_server = server
        self.state.slot_name = slot_name
        self.state.connected_to_ap = False
        self.state.last_error = ""
        self.state.round_index = 0
        self.state.checked_locations.clear()
        self.state.received_items.clear()
        self.state.boss_completed = False
        self.state.goal_status_sent = False
        self.state.warmer_colder = None
        self.state.last_distance_estimate = None
        self.state.pending_events.clear()
        self.state.slot = 0
        self.state.player_names.clear()
        self.state.slot_games.clear()
        self.state.item_id_to_name.clear()
        self.items_seen = 0
        self.link_cache.clear()
        self.resolved_title_cache.clear()
        self._datapackage_requested = False
        for fut in self._scout_waiters.values():
            if not fut.done():
                fut.cancel()
        self._scout_waiters.clear()

        if self.reader_task and not self.reader_task.done():
            self.reader_task.cancel()
            try:
                await self.reader_task
            except Exception:
                pass

        self.reader_task = asyncio.create_task(self._connection_loop())

    async def _connection_loop(self) -> None:
        fail_streak = 0
        while True:
            try:
                ws_url = self._to_ws_url(self.server)
                async with websockets.connect(ws_url, ping_interval=20, ping_timeout=20, max_size=2**22) as ws:
                    self.ws = ws
                    await self._handshake(ws)
                    fail_streak = 0
                    self.state.last_error = ""
                    async for raw in ws:
                        await self._handle_message(raw)
                self.state.connected_to_ap = False
                raise RuntimeError("Disconnected from Archipelago server")
            except asyncio.CancelledError:
                return
            except Exception as exc:
                self.state.connected_to_ap = False
                self.ws = None
                msg = str(exc)
                if "ConnectionRefused" in msg:
                    self.state.last_error = self._friendly_connection_error(msg)
                    LOG.info("AP connection refused; not retrying: %s", self.state.last_error)
                    return

                fail_streak += 1
                if fail_streak >= MAX_AP_CONNECT_ATTEMPTS:
                    self.state.last_error = (
                        f"Unable to connect after {MAX_AP_CONNECT_ATTEMPTS} attempts. {self._friendly_connection_error(msg)}"
                    )
                    LOG.info("AP connect gave up after %s attempts: %s", fail_streak, msg)
                    return

                # Keep last_error empty while retrying so the client does not spam toasts.
                self.state.last_error = ""
                LOG.info("AP connect retry %s/%s after: %s", fail_streak, MAX_AP_CONNECT_ATTEMPTS, msg)
                await asyncio.sleep(2)

    @staticmethod
    def _friendly_connection_error(message: str) -> str:
        lowered = message.lower()
        compact = lowered.replace(" ", "")
        if "connectionrefused" in compact:
            if "invalidpassword" in compact or "incorrect password" in lowered:
                return "Connection refused: invalid password."
            if "invalidslot" in compact:
                return "Connection refused: invalid slot name."
            if "invalidgame" in compact:
                return "Connection refused: wrong game for this slot."
            return "Connection refused. Check server, slot name, and password."
        if "getaddrinfo" in lowered or "name or service not known" in lowered:
            return "Unable to reach server. Check the address."
        if "timed out" in lowered or "timeout" in lowered:
            return "Connection timed out."
        return message

    async def _handshake(self, ws: Any) -> None:
        room_info_raw = await asyncio.wait_for(ws.recv(), timeout=30)
        await self._handle_message(room_info_raw)

        connect_packet = {
            "cmd": "Connect",
            "password": self.password,
            "name": self.slot_name,
            "game": "Wikipelago",
            "uuid": f"wikipelago-cloud-{uuid.uuid4()}",
            "version": {"major": 0, "minor": 6, "build": 7, "class": "Version"},
            "items_handling": 7,
            "tags": ["AP", "SlotData"],
            "slot_data": True,
        }
        await ws.send(json.dumps([connect_packet]))

        # Wait here for Connected or ConnectionRefused (raised) before the read loop.
        deadline = time.time() + 30
        while not self.state.connected_to_ap:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise RuntimeError("Timed out waiting for Archipelago Connected")
            raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
            await self._handle_message(raw)

    async def _handle_message(self, raw: str) -> None:
        try:
            packets = json.loads(raw)
        except json.JSONDecodeError:
            return
        if not isinstance(packets, list):
            return

        for packet in packets:
            cmd = packet.get("cmd")
            if cmd == "Connected":
                self.state.connected_to_ap = True
                self.state.last_error = ""
                self._apply_connected(packet)
                await self._update_link_tags()
                await self._canonicalize_active_targets()
                await self._request_data_package()
            elif cmd == "ConnectionRefused":
                self.state.last_error = f"ConnectionRefused: {packet.get('errors', [])}"
                raise RuntimeError(self.state.last_error)
            elif cmd == "ReceivedItems":
                items = packet.get("items", [])
                index = int(packet.get("index", 0))
                start = max(self.items_seen - index, 0)
                new_item_ids: list[int] = []
                for item in items[start:]:
                    item_id = int(item.get("item"))
                    self.state.received_items.append(item_id)
                    new_item_ids.append(item_id)
                self.items_seen = max(self.items_seen, index + len(items))
                # index 0 is a full inventory sync (connect/reconnect) — do not re-fire traps.
                if index != 0 and new_item_ids:
                    await self._handle_new_items(new_item_ids)
                await self.try_finish_boss()
            elif cmd == "Bounced":
                await self._handle_bounced(packet)
            elif cmd == "DataPackage":
                self._apply_data_package(packet)
            elif cmd == "LocationInfo":
                self._resolve_location_info(packet)

    def _apply_connected(self, packet: dict[str, Any]) -> None:
        slot_data = packet.get("slot_data") or {}
        try:
            self.state.slot = int(packet.get("slot") or 0)
        except Exception:
            self.state.slot = 0

        self.state.player_names.clear()
        self.state.slot_games.clear()
        for player in packet.get("players") or []:
            if not isinstance(player, dict):
                continue
            try:
                slot = int(player.get("slot"))
            except Exception:
                continue
            name = str(player.get("alias") or player.get("name") or f"P{slot}").strip()
            self.state.player_names[slot] = name or f"P{slot}"

        slot_info = packet.get("slot_info") or {}
        if isinstance(slot_info, dict):
            for slot_key, info in slot_info.items():
                if not isinstance(info, dict):
                    continue
                try:
                    slot = int(slot_key)
                except Exception:
                    continue
                game = str(info.get("game") or "").strip()
                if game:
                    self.state.slot_games[slot] = game
                name = str(info.get("name") or "").strip()
                if name:
                    self.state.player_names[slot] = name

        pairs = slot_data.get("round_pairs")
        if isinstance(pairs, list) and pairs:
            normalized_pairs: list[dict[str, str]] = []
            for pair in pairs:
                if not isinstance(pair, dict):
                    continue
                start = self._canonicalize_known_title(str(pair.get("start", "")).strip())
                target = self._canonicalize_known_title(str(pair.get("target", "")).strip())
                normalized_pairs.append({"start": start, "target": target})
            if normalized_pairs:
                self.state.round_pairs = normalized_pairs

        self.state.check_count = int(slot_data.get("check_count", len(self.state.round_pairs)))
        self.state.required_fragments = int(slot_data.get("required_fragments", self.state.required_fragments))
        self.state.start_rounds_unlocked = int(slot_data.get("start_rounds_unlocked", self.state.start_rounds_unlocked))
        self.state.rounds_per_unlock = int(slot_data.get("rounds_per_unlock", self.state.rounds_per_unlock))
        self.state.searchsanity = bool(slot_data.get("searchsanity", False))
        self.state.scrollsanity = bool(slot_data.get("scrollsanity", False))
        self.state.scroll_speed_upgrades = int(slot_data.get("scroll_speed_upgrades", self.state.scroll_speed_upgrades))
        starting_letters = slot_data.get("search_starting_letters", [])
        if isinstance(starting_letters, list):
            self.state.search_starting_letters = [str(letter).upper() for letter in starting_letters if str(letter)]
        self.state.randomize_tables = bool(slot_data.get("randomize_tables", False))
        self.state.randomize_pictures = bool(slot_data.get("randomize_pictures", False))
        self.state.randomize_incipit = bool(slot_data.get("randomize_incipit", False))
        self.state.randomize_infoboxes = bool(slot_data.get("randomize_infoboxes", False))
        self.state.randomize_toc = bool(slot_data.get("randomize_toc", False))
        self.state.randomize_navboxes = bool(slot_data.get("randomize_navboxes", False))
        self.state.randomize_hatnotes = bool(slot_data.get("randomize_hatnotes", False))
        self.state.randomize_references = bool(slot_data.get("randomize_references", False))
        self.state.deaths = bool(slot_data.get("deaths", False))
        self.state.death_link = bool(slot_data.get("death_link", False))
        self.state.link_bombs = bool(slot_data.get("link_bombs", False))
        self.state.link_bomb_density = int(slot_data.get("link_bomb_density", 0))
        self.state.trap_type = int(slot_data.get("trap_type", 0))
        self.state.trap_link = bool(slot_data.get("trap_link", False))

        location_ids = slot_data.get("location_ids", {})
        self.state.location_round_ids = [int(v) for v in location_ids.get("rounds", [])]
        grand_goal = location_ids.get("grand_goal")
        self.state.location_grand_goal = int(grand_goal) if grand_goal is not None else None

        item_ids = slot_data.get("item_ids")
        if isinstance(item_ids, dict):
            parsed: dict[str, int] = {}
            for k, v in item_ids.items():
                try:
                    parsed[str(k)] = int(v)
                except Exception:
                    pass
            if parsed:
                self.state.item_ids = parsed

        # Seed local item names so Wikipelago sends resolve even before DataPackage arrives.
        local_names = {int(v): str(k) for k, v in self.state.item_ids.items()}
        self.state.item_id_to_name["Wikipelago"] = {
            **self.state.item_id_to_name.get("Wikipelago", {}),
            **local_names,
        }

        checked_locations = packet.get("checked_locations", [])
        if isinstance(checked_locations, list):
            restored_checked: set[int] = set()
            for loc in checked_locations:
                try:
                    restored_checked.add(int(loc))
                except Exception:
                    pass
            self.state.checked_locations = restored_checked

            restored_round_index = 0
            for round_loc in self.state.location_round_ids:
                if round_loc in restored_checked:
                    restored_round_index += 1
                else:
                    break
            self.state.round_index = min(restored_round_index, self.state.check_count)

            if self.state.location_grand_goal and self.state.location_grand_goal in restored_checked:
                self.state.boss_completed = True
                self.state.goal_status_sent = True

        if not self.state.last_page:
            self.state.last_page = self.state.current_start()

    async def _request_data_package(self) -> None:
        if self.ws is None or self._datapackage_requested:
            return
        games = sorted({game for game in self.state.slot_games.values() if game})
        if not games:
            games = ["Wikipelago"]
        self._datapackage_requested = True
        payload = [{"cmd": "GetDataPackage", "games": games}]
        async with self.send_lock:
            await self.ws.send(json.dumps(payload))

    def _apply_data_package(self, packet: dict[str, Any]) -> None:
        games = ((packet.get("data") or {}).get("games") or {})
        if not isinstance(games, dict):
            return
        for game, data in games.items():
            if not isinstance(data, dict):
                continue
            mapping = data.get("item_name_to_id") or {}
            if not isinstance(mapping, dict):
                continue
            inverted: dict[int, str] = {}
            for name, item_id in mapping.items():
                try:
                    inverted[int(item_id)] = str(name)
                except Exception:
                    pass
            if inverted:
                merged = dict(self.state.item_id_to_name.get(str(game), {}))
                merged.update(inverted)
                self.state.item_id_to_name[str(game)] = merged

    def _resolve_location_info(self, packet: dict[str, Any]) -> None:
        for entry in packet.get("locations") or []:
            if not isinstance(entry, dict):
                continue
            try:
                location_id = int(entry.get("location"))
            except Exception:
                continue
            fut = self._scout_waiters.pop(location_id, None)
            if fut and not fut.done():
                fut.set_result(entry)

    def _lookup_item_name(self, item_id: int, receiving_slot: int) -> str:
        game = self.state.slot_games.get(receiving_slot, "Wikipelago")
        name = self.state.item_id_to_name.get(game, {}).get(item_id)
        if name:
            return name
        for mapping in self.state.item_id_to_name.values():
            if item_id in mapping:
                return mapping[item_id]
        return f"Item {item_id}"

    def _format_send_text(self, network_item: dict[str, Any]) -> str:
        try:
            item_id = int(network_item.get("item"))
            receiving = int(network_item.get("player"))
        except Exception:
            return ""
        item_name = self._lookup_item_name(item_id, receiving)
        if receiving == self.state.slot:
            return f"Found your {item_name}"
        receiver_name = self.state.player_names.get(receiving, f"P{receiving}")
        return f"Sent {receiver_name}'s {item_name}"

    async def scout_locations(self, location_ids: list[int]) -> dict[int, dict[str, Any]]:
        if not location_ids or self.ws is None:
            return {}
        loop = asyncio.get_running_loop()
        waiters: dict[int, asyncio.Future] = {}
        for location_id in location_ids:
            fut = loop.create_future()
            self._scout_waiters[location_id] = fut
            waiters[location_id] = fut
        payload = [{
            "cmd": "LocationScouts",
            "locations": location_ids,
            "create_as_hint": 0,
        }]
        try:
            async with self.send_lock:
                await self.ws.send(json.dumps(payload))
        except Exception:
            for location_id, fut in waiters.items():
                self._scout_waiters.pop(location_id, None)
                if not fut.done():
                    fut.cancel()
            return {}

        results: dict[int, dict[str, Any]] = {}
        for location_id, fut in waiters.items():
            try:
                results[location_id] = await asyncio.wait_for(fut, timeout=2.5)
            except Exception:
                self._scout_waiters.pop(location_id, None)
                if not fut.done():
                    fut.cancel()
        return results

    @staticmethod
    def _to_ws_url(server: str) -> str:
        cleaned = server.replace("ws://", "").replace("wss://", "").replace("http://", "").replace("https://", "").strip("/")
        scheme = "wss" if cleaned.startswith("archipelago.gg") else "ws"
        return f"{scheme}://{cleaned}"

    def _item_id_to_name(self, item_id: int) -> str | None:
        for name, code in self.state.item_ids.items():
            if int(code) == int(item_id):
                return name
        return None

    def _trap_allowed(self, trap_name: str) -> bool:
        if trap_name not in TRAP_ITEM_NAMES:
            return False
        if self.state.trap_type == 1:
            return trap_name == "Foggy Links"
        if self.state.trap_type == 2:
            return trap_name == "Missing Links"
        return True

    def _queue_event(self, event: dict[str, Any]) -> None:
        self.state.pending_events.append(event)

    def take_pending_events(self) -> list[dict[str, Any]]:
        events = list(self.state.pending_events)
        self.state.pending_events.clear()
        return events

    async def _update_link_tags(self) -> None:
        if self.ws is None:
            return
        tags = ["AP", "SlotData"]
        if self.state.death_link:
            tags.append("DeathLink")
        if self.state.trap_link:
            tags.append("TrapLink")
        payload = [{"cmd": "ConnectUpdate", "tags": tags}]
        async with self.send_lock:
            await self.ws.send(json.dumps(payload))

    async def _handle_new_items(self, item_ids: list[int]) -> None:
        for item_id in item_ids:
            name = self._item_id_to_name(item_id)
            if not name or name not in TRAP_ITEM_NAMES:
                continue
            if not self._trap_allowed(name):
                continue
            self._queue_event({"type": "trap", "trap": name, "source": "item"})
            if self.state.trap_link:
                await self.send_trap_link(name)

    async def _handle_bounced(self, packet: dict[str, Any]) -> None:
        tags = packet.get("tags") or []
        data = packet.get("data") or {}
        if not isinstance(data, dict):
            return
        source = str(data.get("source") or "").strip()
        our_name = self.state.player_names.get(self.state.slot, self.slot_name)

        if "DeathLink" in tags and self.state.death_link:
            if source and our_name and source == our_name:
                return
            cause = str(data.get("cause") or "").strip()
            self._queue_event({"type": "death", "source": source or "DeathLink", "cause": cause})
            return

        if "TrapLink" in tags and self.state.trap_link:
            if source and our_name and source == our_name:
                return
            trap_name = str(data.get("trap_name") or "").strip()
            if not self._trap_allowed(trap_name):
                return
            self._queue_event({"type": "trap", "trap": trap_name, "source": source or "TrapLink"})

    async def send_death_link(self, cause: str = "") -> None:
        if not self.state.death_link or self.ws is None:
            return
        source = self.state.player_names.get(self.state.slot, self.slot_name) or self.slot_name
        payload = [{
            "cmd": "Bounce",
            "tags": ["DeathLink"],
            "data": {
                "time": time.time(),
                "source": source,
                "cause": cause or f"{source} died on Wikipedia",
            },
        }]
        async with self.send_lock:
            await self.ws.send(json.dumps(payload))

    async def send_trap_link(self, trap_name: str) -> None:
        if not self.state.trap_link or self.ws is None:
            return
        if not self._trap_allowed(trap_name):
            return
        source = self.state.player_names.get(self.state.slot, self.slot_name) or self.slot_name
        payload = [{
            "cmd": "Bounce",
            "tags": ["TrapLink"],
            "data": {
                "time": time.time(),
                "source": source,
                "trap_name": trap_name,
            },
        }]
        async with self.send_lock:
            await self.ws.send(json.dumps(payload))

    async def send_location_checks(self, location_ids: list[int]) -> None:
        if not location_ids or self.ws is None:
            return
        payload = [{"cmd": "LocationChecks", "locations": location_ids}]
        async with self.send_lock:
            await self.ws.send(json.dumps(payload))
        self.state.checked_locations.update(location_ids)

    @staticmethod
    def _canonicalize_known_title(title: str) -> str:
        return TITLE_CANONICALS.get(normalize_title(title), title)

    def _canonicalize_title_sync(self, title: str) -> str:
        norm = normalize_title(title)
        cached = self.resolved_title_cache.get(norm)
        if cached:
            return cached

        canonical = self._canonicalize_known_title(title)
        try:
            resolved = self._fetch_resolved_title(canonical)
        except Exception:
            resolved = canonical

        self.resolved_title_cache[norm] = resolved
        self.resolved_title_cache[normalize_title(resolved)] = resolved
        return resolved

    async def _canonicalize_title(self, title: str) -> str:
        return await asyncio.to_thread(self._canonicalize_title_sync, title)

    async def _canonicalize_active_targets(self) -> None:
        """Resolve active round titles without blocking the event loop."""
        if not self.state.round_pairs:
            return

        active_index = min(self.state.round_index, max(len(self.state.round_pairs) - 1, 0))
        indices = {active_index, len(self.state.round_pairs) - 1}
        for idx in indices:
            pair = self.state.round_pairs[idx]
            pair["start"] = self._canonicalize_known_title(pair.get("start", ""))
            pair["target"] = await self._canonicalize_title(pair.get("target", ""))

    def _fetch_page_links(self, title: str) -> set[str]:
        norm = normalize_title(title)
        cached = self.link_cache.get(norm)
        if cached is not None:
            return cached

        links: set[str] = set()
        plcontinue: str | None = None
        pages_fetched = 0

        while pages_fetched < 2:
            params: dict[str, str] = {
                "action": "query",
                "prop": "links",
                "titles": title,
                "redirects": "1",
                "plnamespace": "0",
                "pllimit": "max",
                "format": "json",
            }
            if plcontinue:
                params["plcontinue"] = plcontinue

            url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(params)
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "WikipelagoBridge/1.0 (local bridge)",
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=8) as response:
                payload = json.loads(response.read().decode("utf-8"))

            pages = payload.get("query", {}).get("pages", {})
            for page_data in pages.values():
                for link in page_data.get("links", []):
                    link_title = str(link.get("title", "")).strip()
                    if link_title:
                        links.add(normalize_title(link_title))

            plcontinue = payload.get("continue", {}).get("plcontinue")
            pages_fetched += 1
            if not plcontinue:
                break

        self.link_cache[norm] = links
        return links

    async def _estimate_click_distance(self, page_title: str, target_title: str) -> int | None:
        page_norm = normalize_title(page_title)
        target_norm = normalize_title(target_title)
        if page_norm == target_norm:
            return 0

        try:
            page_links = await asyncio.to_thread(self._fetch_page_links, page_title)
            if target_norm in page_links:
                return 1

            target_links = await asyncio.to_thread(self._fetch_page_links, target_title)
            if page_links.intersection(target_links):
                return 2
            return 3
        except Exception:
            return None


    def _fetch_resolved_title(self, title: str) -> str:
        params = {
            "action": "query",
            "titles": title,
            "redirects": "1",
            "format": "json",
        }
        url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "WikipelagoBridge/1.0 (local bridge)",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))

        pages = payload.get("query", {}).get("pages", {})
        for page_data in pages.values():
            resolved = str(page_data.get("title", "")).strip()
            if resolved:
                return resolved
        return title

    async def _titles_match(self, page_title: str, target_title: str) -> bool:
        page_norm = normalize_title(page_title)
        target_norm = normalize_title(target_title)
        if page_norm == target_norm:
            return True

        target_aliases = TITLE_ALIASES.get(target_norm, set())
        if page_norm in target_aliases:
            return True

        page_aliases = TITLE_ALIASES.get(page_norm, set())
        if target_norm in page_aliases:
            return True

        try:
            resolved_page = await asyncio.to_thread(self._fetch_resolved_title, page_title)
            resolved_target = await asyncio.to_thread(self._fetch_resolved_title, target_title)
            return normalize_title(resolved_page) == normalize_title(resolved_target)
        except Exception:
            return False

    async def _update_compass_hint(self, page_title: str, target_title: str) -> None:
        if not self.state.has_item("Wiki Compass"):
            self.state.warmer_colder = None
            self.state.last_distance_estimate = None
            return

        estimate = await self._estimate_click_distance(page_title, target_title)
        if estimate is None:
            self.state.warmer_colder = "No signal"
            return
        if estimate == 0:
            self.state.warmer_colder = "On target"
            self.state.last_distance_estimate = 0
            return

        previous = self.state.last_distance_estimate
        if previous is None:
            self.state.warmer_colder = "Calibrating"
        elif estimate < previous:
            self.state.warmer_colder = "Warmer"
        elif estimate > previous:
            self.state.warmer_colder = "Colder"
        else:
            self.state.warmer_colder = "Same"
        self.state.last_distance_estimate = estimate

    async def send_goal_status(self) -> None:
        if self.ws is None:
            return
        # Archipelago ClientStatus.CLIENT_GOAL
        payload = [{"cmd": "StatusUpdate", "status": 30}]
        async with self.send_lock:
            await self.ws.send(json.dumps(payload))
        self.state.goal_status_sent = True
        LOG.info("Sent AP goal status update")

    async def ensure_goal_status_if_complete(self) -> None:
        if self.state.goal_status_sent:
            return
        if self.state.location_grand_goal and self.state.location_grand_goal in self.state.checked_locations:
            await self.send_goal_status()
            return
        if self.state.location_round_ids and all(loc in self.state.checked_locations for loc in self.state.location_round_ids):
            await self.send_goal_status()

    async def on_page_check(self, page_title: str, clicks_used: int) -> dict[str, Any]:
        self.state.last_seen = time.time()

        # Refuse gameplay checks while offline so rounds cannot advance without AP.
        if not self.state.connected_to_ap:
            return {
                "matched": False,
                "target": self.state.current_target(),
                "advanced": False,
                "locked": False,
                "not_connected": True,
                "boss_completed": self.state.boss_completed,
                "status": self.state.to_status(),
                "next_target": self.state.current_target(),
            }

        self.state.last_page = page_title
        self.state.clicks_used = clicks_used

        target = await self._canonicalize_title(self.state.current_target())
        if self.state.round_index < len(self.state.round_pairs):
            self.state.round_pairs[self.state.round_index]["target"] = target
        await self._update_compass_hint(page_title, target)
        matched = await self._titles_match(page_title, target)

        result: dict[str, Any] = {
            "matched": matched,
            "target": target,
            "advanced": False,
            "locked": False,
            "boss_completed": self.state.boss_completed,
        }

        if matched and self.state.round_index < self.state.check_count and self.state.location_round_ids:
            round_number = self.state.round_index + 1
            if round_number > self.state.unlocked_rounds():
                result["locked"] = True
            else:
                round_id = self.state.location_round_ids[self.state.round_index]
                scouted = await self.scout_locations([round_id])
                await self.send_location_checks([round_id])
                self.state.round_index += 1
                result["advanced"] = True
                network_item = scouted.get(round_id)
                if network_item:
                    sent_text = self._format_send_text(network_item)
                    if sent_text:
                        result["sent_text"] = sent_text

        await self.try_finish_boss()
        await self.ensure_goal_status_if_complete()
        result["status"] = self.state.to_status()
        result["next_target"] = self.state.current_target()
        return result

    async def try_finish_boss(self) -> None:
        if self.state.boss_completed:
            return
        if not self.state.boss_ready():
            return
        goal_title = await self._canonicalize_title(self.state.goal_article())
        if self.state.round_pairs:
            self.state.round_pairs[-1]["target"] = goal_title
        if not await self._titles_match(self.state.last_page, goal_title):
            return

        if self.state.location_grand_goal:
            await self.send_location_checks([self.state.location_grand_goal])

        remaining = [loc for loc in self.state.location_round_ids if loc not in self.state.checked_locations]
        if remaining:
            await self.send_location_checks(remaining)

        self.state.boss_completed = True
        await self.send_goal_status()


@dataclass
class Session:
    id: str
    state: SessionState
    conn: APConnection


class SessionManager:
    def __init__(self):
        self.sessions: dict[str, Session] = {}

    def create(self) -> Session:
        sid = uuid.uuid4().hex
        state = SessionState()
        session = Session(id=sid, state=state, conn=APConnection(state))
        self.sessions[sid] = session
        return session

    def get(self, sid: str) -> Session | None:
        session = self.sessions.get(sid)
        if session:
            session.state.last_seen = time.time()
        return session

    async def gc(self) -> None:
        while True:
            now = time.time()
            stale = [sid for sid, session in self.sessions.items() if now - session.state.last_seen > SESSION_TTL_SECONDS]
            for sid in stale:
                session = self.sessions.pop(sid)
                if session.conn.reader_task and not session.conn.reader_task.done():
                    session.conn.reader_task.cancel()
            await asyncio.sleep(120)

class App:
    def __init__(self, web_root: Path):
        self.web_root = web_root
        self.sessions = SessionManager()

    async def index(self, request: web.Request) -> web.StreamResponse:
        return web.FileResponse(self.web_root / "index.html")

    async def manifest(self, request: web.Request) -> web.StreamResponse:
        response = web.FileResponse(self.web_root / "manifest.webmanifest")
        response.content_type = "application/manifest+json"
        return response

    async def service_worker(self, request: web.Request) -> web.StreamResponse:
        response = web.FileResponse(self.web_root / "service-worker.js")
        response.headers["Cache-Control"] = "no-cache"
        response.headers["Service-Worker-Allowed"] = "/"
        return response

    async def health(self, request: web.Request) -> web.StreamResponse:
        info = build_info()
        info["sessions"] = len(self.sessions.sessions)
        return web.json_response(info)

    async def create_session(self, request: web.Request) -> web.StreamResponse:
        session = self.sessions.create()
        return web.json_response({"ok": True, "session_id": session.id})

    async def connect_session(self, request: web.Request) -> web.StreamResponse:
        sid = request.match_info["sid"]
        session = self.sessions.get(sid)
        if not session:
            return web.json_response({"ok": False, "error": "invalid session"}, status=404)

        data = await request.json()
        server = str(data.get("server", "")).strip()
        slot_name = str(data.get("slot_name", "")).strip()
        password = str(data.get("password", "")).strip()

        if not server or not slot_name:
            return web.json_response({"ok": False, "error": "server and slot_name are required"}, status=400)

        await session.conn.connect(server, slot_name, password)
        return web.json_response({"ok": True})

    async def session_status(self, request: web.Request) -> web.StreamResponse:
        sid = request.match_info["sid"]
        session = self.sessions.get(sid)
        if not session:
            return web.json_response({"ok": False, "error": "invalid session"}, status=404)
        status = session.state.to_status()
        events = session.conn.take_pending_events()
        status["pending_events"] = events
        return web.json_response({"ok": True, "status": status})

    async def session_death(self, request: web.Request) -> web.StreamResponse:
        sid = request.match_info["sid"]
        session = self.sessions.get(sid)
        if not session:
            return web.json_response({"ok": False, "error": "invalid session"}, status=404)
        if not session.state.connected_to_ap:
            return web.json_response({"ok": False, "error": "not connected"}, status=400)
        data = await request.json()
        cause = str(data.get("cause") or "").strip()
        await session.conn.send_death_link(cause)
        return web.json_response({"ok": True})

    async def session_check(self, request: web.Request) -> web.StreamResponse:
        sid = request.match_info["sid"]
        session = self.sessions.get(sid)
        if not session:
            return web.json_response({"ok": False, "error": "invalid session"}, status=404)

        data = await request.json()
        page_title = str(data.get("page_title", "")).strip()
        clicks_used = int(data.get("clicks_used", 0))
        # Strict mode: display/restore callers must not score. Only intentional
        # in-article clicks should send submit_check=true (client default).
        submit_check = bool(data.get("submit_check", True))

        if not page_title:
            return web.json_response({"ok": False, "error": "page_title is required"}, status=400)

        if not submit_check:
            session.conn.state.last_seen = time.time()
            session.conn.state.last_page = page_title
            session.conn.state.clicks_used = clicks_used
            return web.json_response({
                "ok": True,
                "matched": False,
                "advanced": False,
                "locked": False,
                "display_only": True,
                "target": session.conn.state.current_target(),
                "next_target": session.conn.state.current_target(),
                "boss_completed": session.conn.state.boss_completed,
                "status": session.conn.state.to_status(),
            })

        result = await session.conn.on_page_check(page_title, clicks_used)
        return web.json_response({"ok": True, **result})

    def build(self) -> web.Application:
        app = web.Application()
        app.router.add_get("/", self.index)
        app.router.add_get("/manifest.webmanifest", self.manifest)
        app.router.add_get("/service-worker.js", self.service_worker)
        app.router.add_get("/health", self.health)
        app.router.add_post("/api/session", self.create_session)
        app.router.add_post("/api/session/{sid}/connect", self.connect_session)
        app.router.add_get("/api/session/{sid}/status", self.session_status)
        app.router.add_post("/api/session/{sid}/death", self.session_death)
        app.router.add_post("/api/session/{sid}/check", self.session_check)
        app.router.add_static("/icons/", str(self.web_root / "icons"), show_index=False, append_version=True)
        app.router.add_static("/static/", str(self.web_root), show_index=False, append_version=True)

        async def startup(_: web.Application) -> None:
            app["gc_task"] = asyncio.create_task(self.sessions.gc())

        async def cleanup(_: web.Application) -> None:
            task = app.get("gc_task")
            if task:
                task.cancel()
                try:
                    await task
                except Exception:
                    pass

        app.on_startup.append(startup)
        app.on_cleanup.append(cleanup)
        return app


async def main_async(args: argparse.Namespace) -> None:
    web_root = Path(__file__).resolve().parent.parent / "web"
    application = App(web_root).build()

    runner = web.AppRunner(application)
    await runner.setup()
    site = web.TCPSite(runner, args.host, args.port)
    await site.start()

    LOG.info(f"Wikipelago cloud app running on http://{args.host}:{args.port}")
    while True:
        await asyncio.sleep(3600)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Wikipelago cloud app")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "5000")))
    return parser.parse_args()


def launch() -> None:
    args = parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    launch()


















