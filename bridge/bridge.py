
import argparse
import asyncio
import json
import logging
import os
import random
import subprocess
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
CLIENT_VERSION = "0.6.0-ZaWarudo!"

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _env_first(*names: str) -> str:
    for name in names:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return ""


def _git_output(*args: str) -> str:
    """Best-effort git identity for self-hosted/VPS deploys (Render sets env instead)."""
    try:
        out = subprocess.check_output(
            ["git", *args],
            cwd=_REPO_ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        )
        return (out or "").strip()
    except Exception:
        return ""


def build_info() -> dict[str, Any]:
    """Deploy identity for the UI.

    Prefer Render-injected RENDER_GIT_* / RENDER_SERVICE_NAME. On a VPS or local
    checkout, fall back to WIKIPELAGO_* overrides, then `git` in the repo root.
    """
    branch = _env_first("RENDER_GIT_BRANCH", "WIKIPELAGO_GIT_BRANCH")
    commit_full = _env_first("RENDER_GIT_COMMIT", "WIKIPELAGO_GIT_COMMIT")
    service = _env_first("RENDER_SERVICE_NAME", "WIKIPELAGO_SERVICE_NAME")

    if not branch:
        branch = _git_output("rev-parse", "--abbrev-ref", "HEAD")
        if branch == "HEAD":
            # Detached checkout — keep a usable label if possible.
            branch = _git_output("name-rev", "--name-only", "--no-undefined", "HEAD") or "HEAD"
    if not branch:
        branch = "local"
    if not commit_full:
        commit_full = _git_output("rev-parse", "HEAD")

    commit = commit_full[:7] if commit_full else ""
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
    "Progressive Back": 1_870_002,
    "Wiki Compass": 1_870_003,
    "Ctrl+F Lens": 1_870_004,
    "Footnote": 1_870_006,
    "Round Access": 1_870_007,
    "Progressive Scroll Speed": 1_870_008,
    "Table Lens": 1_870_009,
    "Picture Lens": 1_870_010,
    "Lead Lens": 1_870_011,
    "Infobox Lens": 1_870_012,
    "Contents Lens": 1_870_013,
    "Navbox Lens": 1_870_014,
    "Hatnote Lens": 1_870_015,
    "Reference Lens": 1_870_016,
    "Progressive Reroll": 1_870_017,
    "Progressive Bingo Card": 1_870_018,
    "Progressive Bingo Stamp": 1_870_019,
    "Foggy Links": 1_870_046,
    "Missing Links": 1_870_047,
}

TRAP_ITEM_NAMES = frozenset({"Foggy Links", "Missing Links"})
LINK_BOMB_DENSITY_COUNTS = {0: 1, 1: 5, 2: 20}
# Fallback max for legacy seeds that omit target_rerolls_start.
TARGET_REROLLS_PER_ROUND = 3
PROGRESSIVE_STACK_ITEMS = frozenset({
    "Knowledge Fragment",
    "Round Access",
    "Progressive Scroll Speed",
    "Progressive Back",
    "Progressive Reroll",
    "Progressive Bingo Card",
    "Progressive Bingo Stamp",
    *TRAP_ITEM_NAMES,
})

DEBUG_TOOL_ITEMS = (
    "Progressive Back",
    "Progressive Reroll",
    "Progressive Bingo Card",
    "Progressive Bingo Stamp",
    "Wiki Compass",
    "Ctrl+F Lens",
)
DEBUG_LENS_ITEMS = (
    "Table Lens",
    "Picture Lens",
    "Lead Lens",
    "Infobox Lens",
    "Contents Lens",
    "Navbox Lens",
    "Hatnote Lens",
    "Reference Lens",
)
DEBUG_OPTION_BOOLS = (
    "deaths",
    "death_link",
    "link_bombs",
    "trap_link",
    "searchsanity",
    "scrollsanity",
)

SESSION_TTL_SECONDS = 60 * 60 * 6
# Transient AP drops: retry a few times, then stop and surface last_error.
# ConnectionRefused (bad password/slot) never retries.
MAX_AP_CONNECT_ATTEMPTS = 3


def normalize_title(title: str) -> str:
    spaced = " ".join(title.replace("_", " ").strip().split())
    deaccented = "".join(ch for ch in unicodedata.normalize("NFKD", spaced) if not unicodedata.combining(ch))
    return deaccented.casefold()


# Must match world/APWorldSource/Wikipelago/letter_pairs.py (Scrabble alphabets).
_SCRABBLE_LETTERS: dict[str, str] = {
    "en": "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "fr": "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "it": "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "nl": "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "es": "ABCDEFGHIJKLMNOPQRSTUVWXYZÑ",
    "pt": "ABCDEFGHIJKLMNOPQRSTUVWXYZÇ",
    "de": "ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÜ",
    "sv": "ABCDEFGHIJKLMNOPQRSTUVWXYZÅÄÖ",
    "pl": "ABCDEFGHIJKLMNOPQRSTUVWXYZĄĆĘŁŃÓŚŹŻ",
}


def _bingo_alphabet(lang: str) -> str:
    code = (lang or "en").strip().lower()
    return _SCRABBLE_LETTERS.get(code, _SCRABBLE_LETTERS["en"])


def _fold_bingo_base_latin(ch: str) -> str:
    if ch in ("ß", "ẞ"):
        return "SS"
    decomposed = unicodedata.normalize("NFKD", ch)
    out: list[str] = []
    for part in decomposed:
        if unicodedata.combining(part):
            continue
        if "A" <= part <= "Z" or "a" <= part <= "z":
            out.append(part.upper())
    return "".join(out)


def letter_pair_from_title(title: str, lang: str = "en") -> str | None:
    """First two Scrabble-aware bingo letters (must match world letter_pairs.py)."""
    alphabet = set(_bingo_alphabet(lang))
    letters: list[str] = []
    for ch in title:
        if not ch or ch.isspace():
            continue
        upper = ch.upper()
        if upper in alphabet:
            letters.append(upper)
        elif ch in ("ß", "ẞ") or upper == "ẞ":
            letters.extend(("S", "S"))
        else:
            for letter in _fold_bingo_base_latin(ch):
                if letter in alphabet:
                    letters.append(letter)
        if len(letters) >= 2:
            return letters[0] + letters[1]
    return None


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

PRACTICE_POOL_DIR = (
    Path(__file__).resolve().parent.parent / "world" / "APWorldSource" / "Wikipelago" / "data"
)
PRACTICE_SUPPORTED_LANGS = ("en", "fr", "de", "es", "it", "pt", "nl", "sv", "pl")
_PRACTICE_POOL_CACHE: dict[str, list[str]] = {}


def load_practice_titles(lang: str = "en", *, include_sensitive: bool = False) -> list[str]:
    """Titles from repo pool_*.json (same pools as the apworld)."""
    code = (lang or "en").strip().lower()
    if code not in PRACTICE_SUPPORTED_LANGS:
        raise ValueError(
            f"Unsupported wikipedia_language '{lang}'. "
            f"Supported: {', '.join(PRACTICE_SUPPORTED_LANGS)}"
        )
    cache_key = f"{code}:{'all' if include_sensitive else 'safe'}"
    cached = _PRACTICE_POOL_CACHE.get(cache_key)
    if cached is not None:
        return list(cached)

    path = PRACTICE_POOL_DIR / f"pool_{code}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Missing practice article pool: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    titles: list[str] = []
    for entry in payload.get("entries") or []:
        title = str(entry.get("title") or "").strip()
        if not title:
            continue
        if not include_sensitive and bool(entry.get("sensitive")):
            continue
        titles.append(title)
    # Preserve order, drop dupes.
    titles = list(dict.fromkeys(titles))
    if len(titles) < 3:
        raise RuntimeError(f"Practice pool for '{code}' is too small ({len(titles)} titles).")
    _PRACTICE_POOL_CACHE[cache_key] = titles
    return list(titles)


@dataclass
class SessionState:
    connected_to_ap: bool = False
    practice: bool = False
    practice_pool_titles: list[str] = field(default_factory=list)
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
    trap_count: int = 0
    trap_type: int = 0
    trap_link: bool = False
    bingo_letterpairs: bool = False
    bingo_letterpairs_grid: int = 0
    bingo_letterpairs_boards: list[list[list[str]]] = field(default_factory=list)
    bingo_cards_start: int = 0
    bingo_card_unlocks: int = 0
    bingo_stamp_unlocks: int = 0
    bingo_letterpairs_location_ids: dict[str, dict[str, int]] = field(default_factory=dict)
    bingo_stamped_pairs: dict[str, set[str]] = field(default_factory=dict)
    bingo_stamps_used: int = 0
    bingo_storage_ready: bool = False
    pending_events: list[dict[str, Any]] = field(default_factory=list)
    round_pairs: list[dict[str, str]] = field(default_factory=list)
    goal_article_title: str = ""
    wikipedia_language: str = "en"
    reroll_pool: list[str] = field(default_factory=list)
    target_rerolls_start: int = TARGET_REROLLS_PER_ROUND
    target_rerolls_used: int = 0
    target_rerolls_round: int = -1
    back_depth_start: int = 0
    backs_used: int = 0
    backs_round: int = -1
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
    team: int = 0
    player_names: dict[int, str] = field(default_factory=dict)
    slot_games: dict[int, str] = field(default_factory=dict)
    item_id_to_name: dict[str, dict[int, str]] = field(default_factory=dict)

    def current_target(self) -> str:
        if self.round_index >= len(self.round_pairs):
            return self.goal_article()
        return self.round_pairs[self.round_index]["target"]

    def current_start(self) -> str:
        if not self.round_pairs:
            return ""
        if self.round_index >= len(self.round_pairs):
            # Boss hunt begins from the final round's completed target page.
            return self.round_pairs[-1]["target"]
        return self.round_pairs[self.round_index]["start"]

    def goal_article(self) -> str:
        if self.goal_article_title:
            return self.goal_article_title
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

    def is_playable(self) -> bool:
        """Archipelago connected, or local Practice mode."""
        return self.connected_to_ap or self.practice

    def owned_search_letters(self) -> list[str]:
        letters = set(self.search_starting_letters)
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            if self.has_item(f"Search Letter {letter}"):
                letters.add(letter)
        return sorted(letters)

    def boss_ready(self) -> bool:
        if self.practice:
            return False
        return self.fragments() >= self.required_fragments

    def unlocked_rounds(self) -> int:
        step = max(1, self.rounds_per_unlock)
        unlock_items = self.round_access_count()
        return min(self.check_count, self.start_rounds_unlocked + (unlock_items * step))

    def unlocked_bingo_boards(self) -> int:
        if not self.bingo_letterpairs or not self.bingo_letterpairs_boards:
            return 0
        return min(
            len(self.bingo_letterpairs_boards),
            max(0, self.bingo_cards_start) + self.item_count("Progressive Bingo Card"),
        )

    def unlocked_bingo_board_keys(self) -> list[str]:
        return [str(index) for index in range(1, self.unlocked_bingo_boards() + 1)]

    def bingo_stamps_max(self) -> int:
        if not self.bingo_letterpairs:
            return 0
        return self.item_count("Progressive Bingo Stamp")

    def bingo_stamps_remaining(self) -> int:
        return max(0, self.bingo_stamps_max() - max(0, self.bingo_stamps_used))

    def back_depth_max(self) -> int:
        return max(0, self.back_depth_start) + self.item_count("Progressive Back")

    def sync_back_counter(self) -> None:
        if self.backs_round != self.round_index:
            self.backs_round = self.round_index
            self.backs_used = 0

    def backs_remaining(self) -> int:
        self.sync_back_counter()
        return max(0, self.back_depth_max() - self.backs_used)

    def can_go_back(self) -> bool:
        self.sync_back_counter()
        if not self.is_playable():
            return False
        return self.backs_remaining() > 0

    def target_rerolls_max(self) -> int:
        return max(0, self.target_rerolls_start) + self.item_count("Progressive Reroll")

    def sync_target_reroll_counter(self) -> None:
        if self.target_rerolls_round != self.round_index:
            self.target_rerolls_round = self.round_index
            self.target_rerolls_used = 0

    def target_rerolls_remaining(self) -> int:
        self.sync_target_reroll_counter()
        return max(0, self.target_rerolls_max() - self.target_rerolls_used)

    def can_reroll_target(self) -> bool:
        self.sync_target_reroll_counter()
        if not self.is_playable() or self.boss_completed:
            return False
        # Reroll is available for every normal round, including the final one.
        # Boss hunt (past all rounds) cannot reroll the Grand Goal.
        if not self.practice and self.round_index >= self.check_count:
            return False
        if self.target_rerolls_remaining() <= 0:
            return False
        return bool(self.reroll_pool)

    def bingo_board_for_key(self, board_key: str) -> list[list[str]]:
        try:
            index = int(board_key) - 1
        except Exception:
            return []
        if index < 0 or index >= len(self.bingo_letterpairs_boards):
            return []
        return self.bingo_letterpairs_boards[index]

    def bingo_stamped_cells(self) -> dict[str, list[list[int]]]:
        cells_by_board: dict[str, list[list[int]]] = {}
        if not self.bingo_letterpairs:
            return cells_by_board
        for board_key in self.unlocked_bingo_board_keys():
            board = self.bingo_board_for_key(board_key)
            stamped = self.bingo_stamped_pairs.get(board_key, set())
            cells: list[list[int]] = []
            for row_index, row in enumerate(board):
                for col_index, pair in enumerate(row):
                    if pair in stamped:
                        cells.append([row_index, col_index])
            cells_by_board[board_key] = cells
        return cells_by_board

    def bingo_completed_line_keys_for_board(self, board_key: str) -> list[str]:
        board = self.bingo_board_for_key(board_key)
        n = len(board)
        if not self.bingo_letterpairs or n == 0:
            return []
        stamped = self.bingo_stamped_pairs.get(board_key, set())
        completed: list[str] = []
        for row_index, row in enumerate(board):
            if row and all(pair in stamped for pair in row):
                completed.append(f"row_{row_index + 1}")
        for col_index in range(n):
            if all(board[row_index][col_index] in stamped for row_index in range(n)):
                completed.append(f"col_{col_index + 1}")
        if all(board[i][i] in stamped for i in range(n)):
            completed.append("diag")
        if all(board[i][n - 1 - i] in stamped for i in range(n)):
            completed.append("anti")
        if all(pair in stamped for row in board for pair in row):
            completed.append("full")
        return completed

    def bingo_lines_checked(self) -> dict[str, dict[str, bool]]:
        result: dict[str, dict[str, bool]] = {}
        for board_key, id_map in self.bingo_letterpairs_location_ids.items():
            if not isinstance(id_map, dict):
                continue
            result[board_key] = {
                key: (loc_id in self.checked_locations)
                for key, loc_id in id_map.items()
            }
        return result

    def to_status(self) -> dict[str, Any]:
        self.sync_target_reroll_counter()
        self.sync_back_counter()
        stamped_pairs = {
            board_key: sorted(pairs)
            for board_key, pairs in self.bingo_stamped_pairs.items()
        }
        return {
            "connected_to_ap": self.connected_to_ap,
            "practice": self.practice,
            "ap_server": self.ap_server,
            "slot_name": self.slot_name,
            "current_start": self.current_start(),
            "current_target": self.current_target(),
            "goal_article": self.goal_article(),
            "wikipedia_language": self.wikipedia_language or "en",
            "round": min(self.round_index + 1, self.check_count),
            "rounds_completed": min(self.round_index, self.check_count),
            "check_count": self.check_count,
            "target_rerolls_max": self.target_rerolls_max(),
            "target_rerolls_used": self.target_rerolls_used,
            "target_rerolls_remaining": self.target_rerolls_remaining(),
            "can_reroll_target": self.can_reroll_target(),
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
            "back_depth_max": self.back_depth_max(),
            "backs_used": self.backs_used,
            "backs_remaining": self.backs_remaining(),
            "can_go_back": self.can_go_back(),
            "back_button_unlocked": self.back_depth_max() > 0,
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
            "trap_count": self.trap_count,
            "trap_type": self.trap_type,
            "trap_link": self.trap_link,
            "bingo_letterpairs": self.bingo_letterpairs,
            "bingo_letterpairs_grid": self.bingo_letterpairs_grid,
            "bingo_letterpairs_boards": self.bingo_letterpairs_boards,
            "bingo_cards_start": self.bingo_cards_start,
            "bingo_unlocked_boards": self.unlocked_bingo_boards(),
            "bingo_stamp_unlocks": self.bingo_stamp_unlocks,
            "bingo_stamps_max": self.bingo_stamps_max(),
            "bingo_stamps_used": max(0, self.bingo_stamps_used),
            "bingo_stamps_remaining": self.bingo_stamps_remaining(),
            "bingo_stamped_pairs": stamped_pairs,
            "bingo_stamped_cells": self.bingo_stamped_cells(),
            "bingo_lines_checked": self.bingo_lines_checked(),
            "bingo_storage_ready": self.bingo_storage_ready,
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

    def _clear_practice_state(self) -> None:
        self.state.practice = False
        self.state.practice_pool_titles = []

    def _roll_practice_race(self, *, continue_from: str | None = None) -> None:
        """Pick a practice start/target. If continue_from is set, chain like AP rounds
        (stay on that page; only the target changes)."""
        titles = list(self.state.practice_pool_titles)
        if len(titles) < 3:
            raise RuntimeError("Practice pool is too small to start a race.")

        def _norm(title: str) -> str:
            return str(title or "").replace("_", " ").strip().casefold()

        if continue_from and _norm(continue_from):
            start = continue_from
            candidates = [title for title in titles if _norm(title) != _norm(start)]
            if not candidates:
                raise RuntimeError("Practice pool has no alternate targets.")
            target = random.choice(candidates)
        else:
            start, target = random.sample(titles, 2)

        blocked = {_norm(start), _norm(target)}
        rest = [title for title in titles if _norm(title) not in blocked]
        random.shuffle(rest)
        self.state.round_pairs = [{"start": start, "target": target}]
        self.state.round_index = 0
        self.state.check_count = 1
        self.state.reroll_pool = rest
        self.state.goal_article_title = ""
        self.state.clicks_used = 0
        self.state.backs_used = 0
        self.state.backs_round = 0
        self.state.target_rerolls_used = 0
        self.state.target_rerolls_round = 0
        self.state.last_page = start
        self.state.warmer_colder = None
        self.state.last_distance_estimate = None
        self.state.boss_completed = False
        self.state.goal_status_sent = False

    async def start_practice(self, wikipedia_language: str = "en") -> dict[str, Any]:
        """Begin unlimited local Practice (no Archipelago). Exits any AP connection."""
        # Drop AP without treating this as "exit practice" (we are entering it).
        await self.disconnect(leave_practice=False)
        lang = (wikipedia_language or "en").strip().lower() or "en"
        titles = load_practice_titles(lang, include_sensitive=False)

        self.state.practice = True
        self.state.practice_pool_titles = titles
        self.state.connected_to_ap = False
        self.state.ap_server = ""
        self.state.slot_name = ""
        self.state.last_error = ""
        self.state.wikipedia_language = lang
        self.state.required_fragments = 999
        self.state.start_rounds_unlocked = 1
        self.state.rounds_per_unlock = 1
        self.state.searchsanity = False
        self.state.scrollsanity = False
        self.state.search_starting_letters = []
        self.state.randomize_tables = False
        self.state.randomize_pictures = False
        self.state.randomize_incipit = False
        self.state.randomize_infoboxes = False
        self.state.randomize_toc = False
        self.state.randomize_navboxes = False
        self.state.randomize_hatnotes = False
        self.state.randomize_references = False
        self.state.deaths = False
        self.state.death_link = False
        self.state.link_bombs = False
        self.state.link_bomb_density = 0
        self.state.trap_count = 0
        self.state.trap_link = False
        self.state.bingo_letterpairs = False
        self.state.bingo_letterpairs_grid = 0
        self.state.bingo_letterpairs_boards = []
        self.state.bingo_cards_start = 0
        self.state.bingo_card_unlocks = 0
        self.state.bingo_stamp_unlocks = 0
        self.state.bingo_letterpairs_location_ids = {}
        self.state.bingo_stamped_pairs.clear()
        self.state.bingo_stamps_used = 0
        self.state.bingo_storage_ready = False
        self.state.location_round_ids = []
        self.state.location_grand_goal = None
        self.state.checked_locations.clear()
        self.state.pending_events.clear()
        self.state.back_depth_start = 3
        self.state.target_rerolls_start = 3
        self.state.received_items = [
            DEFAULT_ITEMS["Wiki Compass"],
            DEFAULT_ITEMS["Ctrl+F Lens"],
        ]
        self._roll_practice_race()
        LOG.info(
            "Practice started lang=%s pool=%s start=%s target=%s",
            lang,
            len(titles),
            self.state.current_start(),
            self.state.current_target(),
        )
        return {"ok": True, "status": self.state.to_status()}

    async def connect(self, server: str, slot_name: str, password: str = "") -> None:
        prev_server = (self.server or "").strip().lower()
        prev_slot = (self.slot_name or "").strip().lower()
        next_server = (server or "").strip().lower()
        next_slot = (slot_name or "").strip().lower()
        slot_changed = prev_server != next_server or prev_slot != next_slot

        # Connect always leaves Practice.
        self._clear_practice_state()

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
        self.state.bingo_letterpairs = False
        self.state.bingo_letterpairs_grid = 0
        self.state.bingo_letterpairs_boards = []
        self.state.bingo_cards_start = 0
        self.state.bingo_card_unlocks = 0
        self.state.bingo_stamp_unlocks = 0
        self.state.bingo_letterpairs_location_ids = {}
        self.state.bingo_stamped_pairs.clear()
        self.state.bingo_stamps_used = 0
        self.state.bingo_storage_ready = False
        self.state.target_rerolls_start = TARGET_REROLLS_PER_ROUND
        self.state.target_rerolls_used = 0
        self.state.target_rerolls_round = -1
        self.state.back_depth_start = 0
        self.state.backs_used = 0
        self.state.backs_round = -1
        self.state.slot = 0
        self.state.team = 0
        self.state.player_names.clear()
        self.state.slot_games.clear()
        self.state.item_id_to_name.clear()
        # Switching slots/languages must not resume the previous wiki page.
        if slot_changed:
            self.state.last_page = ""
            self.state.clicks_used = 0
            self.state.wikipedia_language = "en"
            self.state.round_pairs = []
            self.state.goal_article_title = ""
            self.state.reroll_pool = []
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

    async def disconnect(self, *, leave_practice: bool = True) -> None:
        """Leave Archipelago and optionally Practice so the player can reconnect or idle."""
        was_practice = self.state.practice if leave_practice else False
        if leave_practice:
            self._clear_practice_state()
        self.state.connected_to_ap = False
        self.state.last_error = ""
        if was_practice:
            self.state.round_pairs = []
            self.state.reroll_pool = []
            self.state.goal_article_title = ""
            self.state.received_items.clear()
            self.state.back_depth_start = 0
            self.state.target_rerolls_start = TARGET_REROLLS_PER_ROUND
            self.state.clicks_used = 0
            self.state.last_page = ""
            self.state.warmer_colder = None
            self.state.last_distance_estimate = None
        if self.reader_task and not self.reader_task.done():
            self.reader_task.cancel()
            try:
                await self.reader_task
            except Exception:
                pass
        self.reader_task = None
        self.ws = None

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
                await self._request_bingo_stamps_from_storage()
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
            elif cmd == "Retrieved":
                self._resolve_retrieved(packet)
            elif cmd == "SetReply":
                self._resolve_set_reply(packet)

    def _apply_connected(self, packet: dict[str, Any]) -> None:
        slot_data = packet.get("slot_data") or {}
        try:
            self.state.slot = int(packet.get("slot") or 0)
        except Exception:
            self.state.slot = 0
        try:
            self.state.team = int(packet.get("team") or 0)
        except Exception:
            self.state.team = 0

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

        goal_from_slot = slot_data.get("goal_article")
        if isinstance(goal_from_slot, str) and goal_from_slot.strip():
            self.state.goal_article_title = self._canonicalize_known_title(goal_from_slot.strip())
        elif self.state.round_pairs:
            # Legacy seeds: last round target was the Grand Goal.
            self.state.goal_article_title = self.state.round_pairs[-1]["target"]

        wiki_lang = slot_data.get("wikipedia_language", "en")
        if isinstance(wiki_lang, str) and wiki_lang.strip():
            self.state.wikipedia_language = wiki_lang.strip().lower()
        else:
            self.state.wikipedia_language = "en"

        reroll_pool = slot_data.get("reroll_pool")
        if isinstance(reroll_pool, list):
            self.state.reroll_pool = [
                self._canonicalize_known_title(str(title).strip())
                for title in reroll_pool
                if str(title).strip()
            ]

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
        self.state.trap_count = int(slot_data.get("trap_count", 0))
        self.state.trap_type = int(slot_data.get("trap_type", 0))
        self.state.trap_link = bool(slot_data.get("trap_link", False))

        self.state.bingo_letterpairs = bool(slot_data.get("bingo_letterpairs", False))
        self.state.bingo_letterpairs_grid = int(slot_data.get("bingo_letterpairs_grid", 0) or 0)
        self.state.bingo_cards_start = int(slot_data.get("bingo_cards_start", 0) or 0)
        self.state.bingo_card_unlocks = int(slot_data.get("bingo_card_unlocks", 0) or 0)
        self.state.bingo_stamp_unlocks = int(slot_data.get("bingo_stamp_unlocks", 0) or 0)
        self.state.bingo_stamps_used = 0
        self.state.back_depth_start = int(slot_data.get("back_depth_start", 0) or 0)
        if "target_rerolls_start" in slot_data:
            self.state.target_rerolls_start = max(0, int(slot_data.get("target_rerolls_start") or 0))
        else:
            self.state.target_rerolls_start = TARGET_REROLLS_PER_ROUND
        self.state.backs_used = 0
        self.state.backs_round = -1
        self.state.target_rerolls_used = 0
        self.state.target_rerolls_round = -1

        boards: list[list[list[str]]] = []
        boards_raw = slot_data.get("bingo_letterpairs_boards")
        if isinstance(boards_raw, list):
            for board_raw in boards_raw:
                if not isinstance(board_raw, list):
                    continue
                board: list[list[str]] = []
                for row in board_raw:
                    if not isinstance(row, list):
                        continue
                    board.append([str(cell).upper() for cell in row if str(cell).strip()])
                if board:
                    boards.append(board)
        if not boards:
            # Legacy seeds: migrate single bingo_letterpairs_board → boards=[old].
            board_raw = slot_data.get("bingo_letterpairs_board")
            if isinstance(board_raw, list):
                board = []
                for row in board_raw:
                    if not isinstance(row, list):
                        continue
                    board.append([str(cell).upper() for cell in row if str(cell).strip()])
                if board:
                    boards.append(board)
                    if self.state.bingo_cards_start <= 0:
                        self.state.bingo_cards_start = 1
        self.state.bingo_letterpairs_boards = boards if self.state.bingo_letterpairs else []
        if self.state.bingo_letterpairs and self.state.bingo_letterpairs_grid <= 0 and boards:
            self.state.bingo_letterpairs_grid = len(boards[0])

        location_ids = slot_data.get("location_ids", {})
        self.state.location_round_ids = [int(v) for v in location_ids.get("rounds", [])]
        grand_goal = location_ids.get("grand_goal")
        self.state.location_grand_goal = int(grand_goal) if grand_goal is not None else None
        bingo_ids_raw = location_ids.get("bingo_letterpairs") if isinstance(location_ids, dict) else None
        bingo_ids: dict[str, dict[str, int]] = {}
        if isinstance(bingo_ids_raw, dict):
            # New shape: {"1": {"row_1": id, ...}, ...}
            # Legacy flat: {"row_1": id, ...} → board "1"
            # Also accept pre-homogenized row1/col1 keys from older apworlds.
            looks_nested = any(isinstance(value, dict) for value in bingo_ids_raw.values())
            if looks_nested:
                for board_key, id_map in bingo_ids_raw.items():
                    if not isinstance(id_map, dict):
                        continue
                    parsed: dict[str, int] = {}
                    for key, value in id_map.items():
                        try:
                            parsed[self._normalize_bingo_line_key(key)] = int(value)
                        except Exception:
                            pass
                    if parsed:
                        bingo_ids[str(board_key)] = parsed
            else:
                parsed = {}
                for key, value in bingo_ids_raw.items():
                    try:
                        parsed[self._normalize_bingo_line_key(key)] = int(value)
                    except Exception:
                        pass
                if parsed:
                    bingo_ids["1"] = parsed
        self.state.bingo_letterpairs_location_ids = bingo_ids if self.state.bingo_letterpairs else {}
        self.state.bingo_stamped_pairs.clear()
        self.state.bingo_stamps_used = 0

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

        self._rebuild_bingo_stamps_from_checked()

        # Fresh connect to this slot: resume only within-slot last_page, else round start.
        if not self.state.last_page:
            self.state.last_page = self.state.current_start()

    def _rebuild_bingo_stamps_from_checked(self) -> None:
        """Infer stamped cells from already-checked bingo lines (HUD after reconnect)."""
        if not self.state.bingo_letterpairs or not self.state.bingo_letterpairs_boards:
            return
        for board_key, id_map in self.state.bingo_letterpairs_location_ids.items():
            if not isinstance(id_map, dict):
                continue
            board = self.state.bingo_board_for_key(board_key)
            n = len(board)
            if n == 0:
                continue
            stamped = self.state.bingo_stamped_pairs.setdefault(board_key, set())
            for raw_key, loc_id in id_map.items():
                if loc_id not in self.state.checked_locations:
                    continue
                key = self._normalize_bingo_line_key(raw_key)
                if key.startswith("row_"):
                    try:
                        row_index = int(key.split("_", 1)[1]) - 1
                    except Exception:
                        continue
                    if 0 <= row_index < n:
                        stamped.update(board[row_index])
                elif key.startswith("col_"):
                    try:
                        col_index = int(key.split("_", 1)[1]) - 1
                    except Exception:
                        continue
                    if 0 <= col_index < n:
                        for row_index in range(n):
                            stamped.add(board[row_index][col_index])
                elif key == "diag":
                    stamped.update(board[i][i] for i in range(n))
                elif key == "anti":
                    stamped.update(board[i][n - 1 - i] for i in range(n))
                elif key == "full":
                    stamped.update(pair for row in board for pair in row)

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
        host = cleaned.split("/", 1)[0].split(":", 1)[0].lower()
        # Plain ws only for local/dev hosts; public rooms need wss from an HTTPS web client.
        local_hosts = {"localhost", "127.0.0.1", "::1"}
        scheme = "ws" if host in local_hosts else "wss"
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

    def _bingo_stamps_snapshot(self) -> frozenset[tuple[str, str]]:
        return frozenset(
            (board_key, pair)
            for board_key, pairs in self.state.bingo_stamped_pairs.items()
            for pair in pairs
        )

    def _stamp_pair_on_unlocked_boards(self, pair: str) -> bool:
        """Stamp pair on every unlocked board that contains it. Returns True if any board changed."""
        if not pair:
            return False
        changed = False
        for board_key in self.state.unlocked_bingo_board_keys():
            board = self.state.bingo_board_for_key(board_key)
            if any(pair in row for row in board):
                stamped = self.state.bingo_stamped_pairs.setdefault(board_key, set())
                if pair not in stamped:
                    stamped.add(pair)
                    changed = True
        return changed

    @staticmethod
    def _normalize_bingo_line_key(key: Any) -> str:
        """Homogenize line keys to row_N / col_N (accepts legacy rowN / colN)."""
        text = str(key or "").strip()
        if text.startswith("row_") or text.startswith("col_"):
            return text
        if text.startswith("row") and text[3:].isdigit():
            return f"row_{text[3:]}"
        if text.startswith("col") and text[3:].isdigit():
            return f"col_{text[3:]}"
        return text

    @staticmethod
    def _parse_bingo_storage_payload(raw: Any) -> tuple[dict[str, list[Any]], int]:
        """Return (boards_payload, stamps_used). Supports legacy flat board maps."""
        stamps_used = 0
        boards_payload: dict[str, list[Any]] = {}
        if isinstance(raw, dict):
            boards_raw = raw.get("boards")
            if isinstance(boards_raw, dict):
                for board_key, pairs in boards_raw.items():
                    if isinstance(pairs, list):
                        boards_payload[str(board_key)] = pairs
                try:
                    stamps_used = max(0, int(raw.get("stamps_used") or 0))
                except Exception:
                    stamps_used = 0
            else:
                for board_key, pairs in raw.items():
                    if board_key == "stamps_used":
                        try:
                            stamps_used = max(0, int(pairs or 0))
                        except Exception:
                            pass
                        continue
                    if isinstance(pairs, list):
                        boards_payload[str(board_key)] = pairs
        elif isinstance(raw, list):
            boards_payload = {"1": raw}
        return boards_payload, stamps_used

    async def apply_bingo_visit(self, page_title: str) -> list[dict[str, Any]]:
        """Stamp letter-pair cells for this page; send newly completed bingo line checks."""
        if not self.state.bingo_letterpairs or not self.state.bingo_letterpairs_boards:
            return []
        if not self.state.connected_to_ap or self.ws is None:
            return []

        before = self._bingo_stamps_snapshot()
        wiki_lang = (self.state.wikipedia_language or "en").strip().lower() or "en"
        pair = letter_pair_from_title(page_title, wiki_lang)
        if pair:
            self._stamp_pair_on_unlocked_boards(pair)

        events = await self._flush_bingo_line_checks()
        if self._bingo_stamps_snapshot() != before:
            await self._persist_bingo_stamps()
        return events

    async def merge_bingo_stamps(self, stamped_pairs: Any) -> list[dict[str, Any]]:
        """Merge persisted stamps (client cache / AP storage); may complete lines."""
        if not self.state.bingo_letterpairs or not self.state.bingo_letterpairs_boards:
            return []
        if not self.state.connected_to_ap:
            return []

        before = self._bingo_stamps_snapshot()
        if isinstance(stamped_pairs, dict):
            # Per-board payload: {"1": ["AB", ...], ...}
            for board_key, pairs in stamped_pairs.items():
                key = str(board_key)
                if key not in self.state.unlocked_bingo_board_keys():
                    continue
                board = self.state.bingo_board_for_key(key)
                on_board = {pair for row in board for pair in row}
                stamped = self.state.bingo_stamped_pairs.setdefault(key, set())
                for raw in pairs or []:
                    pair = str(raw or "").strip().upper()
                    if pair in on_board:
                        stamped.add(pair)
        else:
            for raw in stamped_pairs or []:
                pair = str(raw or "").strip().upper()
                self._stamp_pair_on_unlocked_boards(pair)

        events = await self._flush_bingo_line_checks()
        if self._bingo_stamps_snapshot() != before:
            # Never write DataStorage until Retrieved applied — early replace wipes room stamps.
            await self._persist_bingo_stamps()
        return events

    def _bingo_storage_key(self) -> str:
        return f"wikipelago_bingo_letterpairs_{self.state.team}_{self.state.slot}"

    def _resolve_retrieved(self, packet: dict[str, Any]) -> None:
        keys = packet.get("keys")
        if not isinstance(keys, dict):
            return
        storage_key = self._bingo_storage_key()
        # Only handle our bingo Get. Key may be present with null when empty.
        if storage_key not in keys:
            return
        raw = keys.get(storage_key)
        asyncio.create_task(self._apply_bingo_storage_payload(raw, source="Retrieved"))

    def _resolve_set_reply(self, packet: dict[str, Any]) -> None:
        storage_key = self._bingo_storage_key()
        if packet.get("key") != storage_key:
            return
        # SetNotify / want_reply: value is the post-operation DataStorage payload.
        raw = packet.get("value")
        asyncio.create_task(self._apply_bingo_storage_payload(raw, source="SetReply"))

    async def _request_bingo_stamps_from_storage(self) -> None:
        """Subscribe + Get stamped pairs from Archipelago DataStorage."""
        if not self.state.bingo_letterpairs or not self.state.bingo_letterpairs_boards:
            return
        if self.ws is None or not self.state.connected_to_ap:
            return
        self.state.bingo_storage_ready = False
        key = self._bingo_storage_key()
        payload = [
            {"cmd": "SetNotify", "keys": [key]},
            {"cmd": "Get", "keys": [key]},
        ]
        try:
            async with self.send_lock:
                await self.ws.send(json.dumps(payload))
        except Exception as exc:
            LOG.info("Bingo DataStorage Get/SetNotify request failed: %s", exc)

    async def _apply_bingo_storage_payload(self, raw: Any, *, source: str = "") -> None:
        if not self.state.bingo_letterpairs or not self.state.bingo_letterpairs_boards:
            self.state.bingo_storage_ready = True
            return
        before = self._bingo_stamps_snapshot()
        before_used = max(0, self.state.bingo_stamps_used)
        boards_payload, stamps_used = self._parse_bingo_storage_payload(raw)
        for board_key, pairs in boards_payload.items():
            key = str(board_key)
            board = self.state.bingo_board_for_key(key)
            if not board:
                continue
            on_board = {pair for row in board for pair in row}
            stamped = self.state.bingo_stamped_pairs.setdefault(key, set())
            for item in pairs or []:
                pair = str(item or "").strip().upper()
                if pair in on_board:
                    stamped.add(pair)
        # Never lose a locally higher used count on a racing SetReply.
        self.state.bingo_stamps_used = max(before_used, stamps_used)
        await self._flush_bingo_line_checks()
        after = self._bingo_stamps_snapshot()
        changed = after != before or self.state.bingo_stamps_used != before_used
        was_ready = self.state.bingo_storage_ready
        # Mark ready before any persist so gated writers can flush the unioned state.
        self.state.bingo_storage_ready = True
        # Keep storage in sync with line-inferred / in-memory stamps after reconnect.
        # Never echo-persist unchanged SetReply (would loop with want_reply).
        if source == "SetReply":
            if changed:
                await self._persist_bingo_stamps(force=True)
        elif changed or any(self.state.bingo_stamped_pairs.values()) or self.state.bingo_stamps_used > 0:
            await self._persist_bingo_stamps(force=True)
        if changed or not was_ready:
            self._queue_event({"type": "bingo_stamps_updated", "source": source or "storage"})

    async def _persist_bingo_stamps(self, *, force: bool = False) -> None:
        if not self.state.bingo_letterpairs or self.ws is None or not self.state.connected_to_ap:
            return
        # Replacing DataStorage before the initial Get returns drops stamps written by
        # other clients while this device was offline.
        if not force and not self.state.bingo_storage_ready:
            return
        key = self._bingo_storage_key()
        value = {
            "boards": {
                board_key: sorted(pairs)
                for board_key, pairs in self.state.bingo_stamped_pairs.items()
                if pairs
            },
            "stamps_used": max(0, int(self.state.bingo_stamps_used)),
        }
        payload = [{
            "cmd": "Set",
            "key": key,
            "default": {"boards": {}, "stamps_used": 0},
            "want_reply": True,
            "operations": [{
                "operation": "replace",
                "value": value,
            }],
        }]
        try:
            async with self.send_lock:
                await self.ws.send(json.dumps(payload))
        except Exception as exc:
            LOG.info("Bingo DataStorage Set failed for %s: %s", key, exc)

    async def use_bingo_stamp(self, board: Any, row: Any, col: Any) -> dict[str, Any]:
        """Spend one Progressive Bingo Stamp to stamp a single unlocked empty cell."""
        if not self.state.bingo_letterpairs or not self.state.bingo_letterpairs_boards:
            return {"ok": False, "error": "bingo disabled", "status": self.state.to_status()}
        if not self.state.connected_to_ap or self.ws is None:
            return {"ok": False, "error": "not connected", "status": self.state.to_status()}
        if not self.state.bingo_storage_ready:
            return {"ok": False, "error": "bingo storage not ready", "status": self.state.to_status()}
        if self.state.bingo_stamps_remaining() <= 0:
            return {"ok": False, "error": "no stamp charges", "status": self.state.to_status()}

        board_key = str(board).strip()
        if board_key not in self.state.unlocked_bingo_board_keys():
            return {"ok": False, "error": "board locked", "status": self.state.to_status()}
        board_grid = self.state.bingo_board_for_key(board_key)
        n = len(board_grid)
        try:
            row_index = int(row)
            col_index = int(col)
        except Exception:
            return {"ok": False, "error": "invalid cell", "status": self.state.to_status()}
        if row_index < 0 or col_index < 0 or row_index >= n or col_index >= n:
            return {"ok": False, "error": "cell out of range", "status": self.state.to_status()}

        pair = str(board_grid[row_index][col_index] or "").strip().upper()
        if not pair:
            return {"ok": False, "error": "empty cell", "status": self.state.to_status()}
        stamped = self.state.bingo_stamped_pairs.setdefault(board_key, set())
        if pair in stamped:
            return {"ok": False, "error": "already stamped", "status": self.state.to_status()}

        stamped.add(pair)
        self.state.bingo_stamps_used = max(0, self.state.bingo_stamps_used) + 1
        bingo_completed = await self._flush_bingo_line_checks()
        await self._persist_bingo_stamps(force=True)
        LOG.info(
            "Bingo stamp used board=%s cell=%s,%s pair=%s used=%s/%s",
            board_key,
            row_index,
            col_index,
            pair,
            self.state.bingo_stamps_used,
            self.state.bingo_stamps_max(),
        )
        return {
            "ok": True,
            "stamped": True,
            "board": board_key,
            "row": row_index,
            "col": col_index,
            "pair": pair,
            "bingo_completed": bingo_completed,
            "status": self.state.to_status(),
        }

    async def _flush_bingo_line_checks(self) -> list[dict[str, Any]]:
        pending: list[tuple[str, str, int]] = []
        for board_key in self.state.unlocked_bingo_board_keys():
            id_map = self.state.bingo_letterpairs_location_ids.get(board_key) or {}
            if not isinstance(id_map, dict):
                continue
            for key in self.state.bingo_completed_line_keys_for_board(board_key):
                loc_id = id_map.get(key)
                if loc_id is None or loc_id in self.state.checked_locations:
                    continue
                pending.append((board_key, key, loc_id))

        if not pending:
            return []

        location_ids = [loc_id for _, _, loc_id in pending]
        scouted = await self.scout_locations(location_ids)
        await self.send_location_checks(location_ids)
        LOG.info("Bingo lines checked: %s", [f"{board}:{key}" for board, key, _ in pending])

        events: list[dict[str, Any]] = []
        for board_key, key, loc_id in pending:
            network_item = scouted.get(loc_id)
            sent_text = self._format_send_text(network_item) if network_item else ""
            events.append({
                "board": board_key,
                "key": key,
                "label": self._bingo_line_label(key, board_key),
                "sent_text": sent_text,
            })
        return events

    @staticmethod
    def _bingo_line_label(key: str, board_key: str = "1") -> str:
        board_label = f"Bingo Board {board_key}"
        if key.startswith("row_"):
            return f"{board_label} Row {key.split('_', 1)[1]}"
        if key.startswith("col_"):
            return f"{board_label} Column {key.split('_', 1)[1]}"
        if key == "diag":
            return f"{board_label} Diagonal"
        if key == "anti":
            return f"{board_label} Anti-Diagonal"
        if key == "full":
            return f"{board_label} Full Card"
        return f"{board_label} {key}"

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
        if self.state.goal_article_title:
            self.state.goal_article_title = await self._canonicalize_title(self.state.goal_article_title)

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

            url = f"{self._wikipedia_api_root()}/w/api.php?" + urllib.parse.urlencode(params)
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

    def _wikipedia_api_root(self) -> str:
        lang = (self.state.wikipedia_language or "en").strip().lower() or "en"
        return f"https://{lang}.wikipedia.org"

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
        url = f"{self._wikipedia_api_root()}/w/api.php?" + urllib.parse.urlencode(params)
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
        if self.state.boss_completed:
            await self.send_goal_status()
            return
        if self.state.location_grand_goal and self.state.location_grand_goal in self.state.checked_locations:
            await self.send_goal_status()

    async def on_page_check(self, page_title: str, clicks_used: int) -> dict[str, Any]:
        self.state.last_seen = time.time()

        # Refuse gameplay checks while offline so rounds cannot advance without AP/Practice.
        if not self.state.is_playable():
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

        if self.state.practice:
            if matched:
                # Chain like AP: keep the player on the cleared target; only roll a new target.
                self._roll_practice_race(continue_from=page_title)
                result["advanced"] = True
                result["practice_rolled"] = True
            result["status"] = self.state.to_status()
            result["next_target"] = self.state.current_target()
            return result

        if matched and self.state.round_index < self.state.check_count and self.state.location_round_ids:
            round_number = self.state.round_index + 1
            if round_number > self.state.unlocked_rounds():
                result["locked"] = True
            else:
                round_id = self.state.location_round_ids[self.state.round_index]
                scouted = await self.scout_locations([round_id])
                await self.send_location_checks([round_id])
                self.state.round_index += 1
                self.state.sync_target_reroll_counter()
                self.state.sync_back_counter()
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

    async def reroll_target(self) -> dict[str, Any]:
        self.state.last_seen = time.time()
        self.state.sync_target_reroll_counter()

        if not self.state.is_playable():
            return {"ok": False, "error": "not connected", "status": self.state.to_status()}
        if self.state.boss_completed:
            return {"ok": False, "error": "seed already complete", "status": self.state.to_status()}
        if not self.state.practice and self.state.round_index >= self.state.check_count:
            return {
                "ok": False,
                "error": "cannot reroll the Grand Goal",
                "status": self.state.to_status(),
            }
        if self.state.target_rerolls_remaining() <= 0:
            return {
                "ok": False,
                "error": f"no rerolls left this round ({self.state.target_rerolls_max()} max)",
                "status": self.state.to_status(),
            }

        def _norm(title: str) -> str:
            return str(title or "").replace("_", " ").strip().casefold()

        start = self.state.current_start()
        old_target = self.state.current_target()
        blocked = {_norm(start), _norm(old_target), _norm(self.state.goal_article())}
        for pair in self.state.round_pairs:
            blocked.add(_norm(pair.get("target", "")))

        candidates = [title for title in self.state.reroll_pool if _norm(title) not in blocked]
        if not candidates:
            return {
                "ok": False,
                "error": "no alternate targets left in the seed pool",
                "status": self.state.to_status(),
            }

        picked = random.choice(candidates)
        new_target = await self._canonicalize_title(picked)
        if _norm(new_target) in blocked or not new_target:
            # Canonicalization collided with a blocked title; try a few more.
            random.shuffle(candidates)
            new_target = ""
            for candidate in candidates[:12]:
                resolved = await self._canonicalize_title(candidate)
                if resolved and _norm(resolved) not in blocked:
                    new_target = resolved
                    picked = candidate
                    break
            if not new_target:
                return {
                    "ok": False,
                    "error": "no usable alternate targets after title resolution",
                    "status": self.state.to_status(),
                }

        self.state.round_pairs[self.state.round_index]["target"] = new_target
        self.state.reroll_pool = [title for title in self.state.reroll_pool if _norm(title) != _norm(picked)]
        # Return the discarded target to the pool for later rounds / rerolls.
        if old_target and _norm(old_target) != _norm(self.state.goal_article()):
            still_used = any(
                _norm(pair.get("target", "")) == _norm(old_target)
                for idx, pair in enumerate(self.state.round_pairs)
                if idx != self.state.round_index
            )
            if not still_used and all(_norm(title) != _norm(old_target) for title in self.state.reroll_pool):
                self.state.reroll_pool.append(old_target)

        self.state.target_rerolls_used += 1
        self.state.warmer_colder = None
        self.state.last_distance_estimate = None

        return {
            "ok": True,
            "rerolled": True,
            "old_target": old_target,
            "new_target": new_target,
            "rerolls_used": self.state.target_rerolls_used,
            "rerolls_remaining": self.state.target_rerolls_remaining(),
            "status": self.state.to_status(),
        }

    async def use_back(self) -> dict[str, Any]:
        """Consume one Progressive Back charge for the current round (client owns history)."""
        self.state.last_seen = time.time()
        self.state.sync_back_counter()

        if not self.state.is_playable():
            return {"ok": False, "error": "not connected", "status": self.state.to_status()}
        if not self.state.can_go_back():
            return {
                "ok": False,
                "error": f"no backs left this round ({self.state.back_depth_max()} max)",
                "status": self.state.to_status(),
            }

        self.state.backs_used += 1
        return {
            "ok": True,
            "used_back": True,
            "backs_used": self.state.backs_used,
            "backs_remaining": self.state.backs_remaining(),
            "back_depth_max": self.state.back_depth_max(),
            "status": self.state.to_status(),
        }

    async def try_finish_boss(self) -> None:
        if self.state.boss_completed:
            return
        if not self.state.boss_ready():
            return
        goal_title = await self._canonicalize_title(self.state.goal_article())
        self.state.goal_article_title = goal_title
        if not await self._titles_match(self.state.last_page, goal_title):
            return

        if self.state.location_grand_goal:
            await self.send_location_checks([self.state.location_grand_goal])

        remaining = [loc for loc in self.state.location_round_ids if loc not in self.state.checked_locations]
        if remaining:
            await self.send_location_checks(remaining)

        self.state.boss_completed = True
        await self.send_goal_status()

    def _debug_item_id(self, name: str) -> int | None:
        if name in self.state.item_ids:
            return int(self.state.item_ids[name])
        item_id: int | None = None
        if name in DEFAULT_ITEMS:
            item_id = int(DEFAULT_ITEMS[name])
        elif name.startswith("Search Letter ") and len(name) == len("Search Letter A"):
            letter = name[-1].upper()
            if "A" <= letter <= "Z":
                item_id = 1_870_000 + 20 + (ord(letter) - ord("A"))
        if item_id is None:
            return None
        # Keep has_item / counts consistent when slot_data omitted an id.
        self.state.item_ids[name] = item_id
        return item_id

    async def _debug_grant_named(self, name: str, *, unique: bool = False, fire_trap: bool = True) -> bool:
        item_id = self._debug_item_id(name)
        if item_id is None:
            return False
        if unique and self.state.has_item(name):
            return False
        self.state.received_items.append(item_id)
        if fire_trap and name in TRAP_ITEM_NAMES:
            await self._handle_new_items([item_id])
        return True

    def _debug_set_item_count(self, name: str, count: int) -> None:
        item_id = self._debug_item_id(name)
        if item_id is None:
            return
        count = max(0, int(count))
        self.state.received_items = [i for i in self.state.received_items if i != item_id]
        self.state.received_items.extend([item_id] * count)

    async def _debug_complete_round_at(self, round_index: int) -> dict[str, Any]:
        if round_index < 0 or round_index >= len(self.state.location_round_ids):
            return {"advanced": False, "error": "no round location for index"}
        if self.state.boss_completed:
            return {"advanced": False, "error": "seed already complete"}
        round_id = self.state.location_round_ids[round_index]
        if round_id in self.state.checked_locations:
            if self.state.round_index <= round_index:
                self.state.round_index = min(round_index + 1, self.state.check_count)
                self.state.sync_target_reroll_counter()
                self.state.sync_back_counter()
            return {"advanced": False, "already_checked": True}
        scouted = await self.scout_locations([round_id])
        await self.send_location_checks([round_id])
        self.state.round_index = max(self.state.round_index, min(round_index + 1, self.state.check_count))
        self.state.sync_target_reroll_counter()
        self.state.sync_back_counter()
        result: dict[str, Any] = {"advanced": True, "round_completed": round_index + 1}
        network_item = scouted.get(round_id)
        if network_item:
            sent_text = self._format_send_text(network_item)
            if sent_text:
                result["sent_text"] = sent_text
        return result

    async def debug_action(self, action: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Full AP/session debug mutators for playtesting. Unauthenticated for 0.4."""
        data = data or {}
        self.state.last_seen = time.time()
        action = str(action or "").strip()

        if not self.state.connected_to_ap:
            return {"ok": False, "error": "not connected", "status": self.state.to_status()}

        try:
            if action == "complete_round":
                idx = self.state.round_index
                if idx >= self.state.check_count:
                    return {"ok": False, "error": "no active round left", "status": self.state.to_status()}
                result = await self._debug_complete_round_at(idx)
                await self.try_finish_boss()
                await self.ensure_goal_status_if_complete()
                return {"ok": True, "action": action, **result, "status": self.state.to_status()}

            if action == "set_round":
                # 1-based round number to jump to (incomplete). Completes earlier rounds via AP.
                target_round = max(1, min(int(data.get("round", 1)), self.state.check_count))
                target_index = target_round - 1
                sent_bits: list[str] = []
                for idx in range(target_index):
                    result = await self._debug_complete_round_at(idx)
                    if result.get("sent_text"):
                        sent_bits.append(str(result["sent_text"]))
                self.state.round_index = min(target_index, self.state.check_count)
                self.state.sync_target_reroll_counter()
                self.state.sync_back_counter()
                self.state.warmer_colder = None
                self.state.last_distance_estimate = None
                await self.try_finish_boss()
                out: dict[str, Any] = {
                    "ok": True,
                    "action": action,
                    "round": self.state.round_index + 1,
                    "status": self.state.to_status(),
                }
                if sent_bits:
                    out["sent_text"] = sent_bits[-1]
                return out

            if action == "unlock_all_rounds":
                step = max(1, self.state.rounds_per_unlock)
                need = max(0, self.state.check_count - self.state.start_rounds_unlocked)
                need_items = (need + step - 1) // step
                while self.state.round_access_count() < need_items:
                    await self._debug_grant_named("Round Access", unique=False, fire_trap=False)
                return {
                    "ok": True,
                    "action": action,
                    "round_access_count": self.state.round_access_count(),
                    "unlocked_rounds": self.state.unlocked_rounds(),
                    "status": self.state.to_status(),
                }

            if action == "grant_item":
                name = str(data.get("item") or "").strip()
                if not name:
                    return {"ok": False, "error": "item is required", "status": self.state.to_status()}
                unique = name not in PROGRESSIVE_STACK_ITEMS
                granted = await self._debug_grant_named(name, unique=unique, fire_trap=True)
                await self.try_finish_boss()
                return {
                    "ok": True,
                    "action": action,
                    "item": name,
                    "granted": granted,
                    "status": self.state.to_status(),
                }

            if action == "grant_tools":
                granted = []
                for name in DEBUG_TOOL_ITEMS:
                    unique = name not in PROGRESSIVE_STACK_ITEMS
                    if await self._debug_grant_named(name, unique=unique, fire_trap=False):
                        granted.append(name)
                return {"ok": True, "action": action, "granted": granted, "status": self.state.to_status()}

            if action == "grant_lenses":
                granted = [n for n in DEBUG_LENS_ITEMS if await self._debug_grant_named(n, unique=True, fire_trap=False)]
                return {"ok": True, "action": action, "granted": granted, "status": self.state.to_status()}

            if action == "grant_letters":
                granted = []
                for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                    name = f"Search Letter {letter}"
                    if await self._debug_grant_named(name, unique=True, fire_trap=False):
                        granted.append(letter)
                return {"ok": True, "action": action, "granted": granted, "status": self.state.to_status()}

            if action == "grant_scroll":
                # Fill to configured upgrade cap.
                target = max(1, int(self.state.scroll_speed_upgrades))
                while self.state.item_count("Progressive Scroll Speed") < target:
                    await self._debug_grant_named("Progressive Scroll Speed", unique=False, fire_trap=False)
                return {
                    "ok": True,
                    "action": action,
                    "scroll_speed_level": self.state.item_count("Progressive Scroll Speed"),
                    "status": self.state.to_status(),
                }

            if action == "set_fragments":
                count = max(0, int(data.get("count", 0)))
                self._debug_set_item_count("Knowledge Fragment", count)
                await self.try_finish_boss()
                return {
                    "ok": True,
                    "action": action,
                    "fragments": self.state.fragments(),
                    "status": self.state.to_status(),
                }

            if action == "fill_fragments":
                self._debug_set_item_count("Knowledge Fragment", self.state.required_fragments)
                await self.try_finish_boss()
                return {
                    "ok": True,
                    "action": action,
                    "fragments": self.state.fragments(),
                    "status": self.state.to_status(),
                }

            if action == "set_target":
                title = str(data.get("title") or "").strip()
                if not title:
                    return {"ok": False, "error": "title is required", "status": self.state.to_status()}
                if self.state.round_index >= len(self.state.round_pairs):
                    return {"ok": False, "error": "no active round", "status": self.state.to_status()}
                new_target = await self._canonicalize_title(title)
                self.state.round_pairs[self.state.round_index]["target"] = new_target
                self.state.warmer_colder = None
                self.state.last_distance_estimate = None
                return {
                    "ok": True,
                    "action": action,
                    "new_target": new_target,
                    "status": self.state.to_status(),
                }

            if action == "reset_rerolls":
                self.state.target_rerolls_used = 0
                self.state.target_rerolls_round = self.state.round_index
                return {"ok": True, "action": action, "status": self.state.to_status()}

            if action == "reset_backs":
                self.state.backs_used = 0
                self.state.backs_round = self.state.round_index
                return {"ok": True, "action": action, "status": self.state.to_status()}

            if action == "set_options":
                changed: list[str] = []
                for key in DEBUG_OPTION_BOOLS:
                    if key in data:
                        setattr(self.state, key, bool(data[key]))
                        changed.append(key)
                if "link_bomb_density" in data:
                    self.state.link_bomb_density = max(0, min(2, int(data["link_bomb_density"])))
                    changed.append("link_bomb_density")
                if "death_link" in data or "trap_link" in data:
                    await self._update_link_tags()
                return {"ok": True, "action": action, "changed": changed, "status": self.state.to_status()}

            if action == "queue_trap":
                trap = str(data.get("trap") or "").strip()
                if trap not in TRAP_ITEM_NAMES:
                    return {"ok": False, "error": "trap must be Foggy Links or Missing Links", "status": self.state.to_status()}
                # Inject as a received trap item so inventory + TrapLink stay consistent.
                await self._debug_grant_named(trap, unique=False, fire_trap=True)
                return {"ok": True, "action": action, "trap": trap, "status": self.state.to_status()}

            if action == "send_death_link":
                if not self.state.death_link:
                    self.state.death_link = True
                    await self._update_link_tags()
                cause = str(data.get("cause") or "Debug DeathLink").strip()
                await self.send_death_link(cause)
                return {"ok": True, "action": action, "status": self.state.to_status()}

            if action == "receive_death":
                cause = str(data.get("cause") or "Debug death").strip()
                self._queue_event({"type": "death", "source": "Debug", "cause": cause})
                return {"ok": True, "action": action, "status": self.state.to_status()}

            if action == "finish_boss":
                self._debug_set_item_count("Knowledge Fragment", max(self.state.required_fragments, self.state.fragments()))
                # Complete any remaining round locations, then grand goal.
                remaining = [loc for loc in self.state.location_round_ids if loc not in self.state.checked_locations]
                if remaining:
                    await self.send_location_checks(remaining)
                self.state.round_index = self.state.check_count
                if self.state.location_grand_goal:
                    await self.send_location_checks([self.state.location_grand_goal])
                self.state.boss_completed = True
                await self.send_goal_status()
                return {"ok": True, "action": action, "status": self.state.to_status()}

            return {"ok": False, "error": f"unknown action: {action}", "status": self.state.to_status()}
        except Exception as exc:
            LOG.exception("debug_action failed: %s", action)
            return {"ok": False, "error": str(exc), "status": self.state.to_status()}


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
        # Embed deploy identity in HTML so the badge does not depend on a separate
        # /health fetch (Render free-tier cold starts often 404 that first request).
        html = (self.web_root / "index.html").read_text(encoding="utf-8")
        payload = json.dumps(build_info(), separators=(",", ":"))
        injection = f'<script type="application/json" id="build-info">{payload}</script>\n'
        if "</head>" in html:
            html = html.replace("</head>", injection + "</head>", 1)
        else:
            html = injection + html
        return web.Response(
            text=html,
            content_type="text/html",
            charset="utf-8",
            headers={"Cache-Control": "no-cache"},
        )

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

    async def practice_session(self, request: web.Request) -> web.StreamResponse:
        sid = request.match_info["sid"]
        session = self.sessions.get(sid)
        if not session:
            return web.json_response({"ok": False, "error": "invalid session"}, status=404)
        try:
            data = await request.json()
        except Exception:
            data = {}
        if not isinstance(data, dict):
            data = {}
        lang = str(data.get("wikipedia_language") or "en").strip() or "en"
        try:
            result = await session.conn.start_practice(lang)
        except (ValueError, FileNotFoundError, RuntimeError) as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=400)
        return web.json_response(result)

    async def disconnect_session(self, request: web.Request) -> web.StreamResponse:
        sid = request.match_info["sid"]
        session = self.sessions.get(sid)
        if not session:
            return web.json_response({"ok": False, "error": "invalid session"}, status=404)
        await session.conn.disconnect()
        return web.json_response({"ok": True, "status": session.conn.state.to_status()})

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

        session.conn.state.last_seen = time.time()
        bingo_completed: list[dict[str, Any]] = []
        if session.state.connected_to_ap:
            bingo_completed = await session.conn.apply_bingo_visit(page_title)

        if not submit_check:
            session.conn.state.last_page = page_title
            session.conn.state.clicks_used = clicks_used
            return web.json_response({
                "ok": True,
                "matched": False,
                "advanced": False,
                "locked": False,
                "display_only": True,
                "bingo_completed": bingo_completed,
                "target": session.conn.state.current_target(),
                "next_target": session.conn.state.current_target(),
                "boss_completed": session.conn.state.boss_completed,
                "status": session.conn.state.to_status(),
            })

        result = await session.conn.on_page_check(page_title, clicks_used)
        result["bingo_completed"] = bingo_completed
        return web.json_response({"ok": True, **result})

    async def session_reroll_target(self, request: web.Request) -> web.StreamResponse:
        sid = request.match_info["sid"]
        session = self.sessions.get(sid)
        if not session:
            return web.json_response({"ok": False, "error": "invalid session"}, status=404)
        result = await session.conn.reroll_target()
        status_code = 200 if result.get("ok") else 400
        return web.json_response(result, status=status_code)

    async def session_use_back(self, request: web.Request) -> web.StreamResponse:
        sid = request.match_info["sid"]
        session = self.sessions.get(sid)
        if not session:
            return web.json_response({"ok": False, "error": "invalid session"}, status=404)
        result = await session.conn.use_back()
        status_code = 200 if result.get("ok") else 400
        return web.json_response(result, status=status_code)

    async def session_bingo_stamps(self, request: web.Request) -> web.StreamResponse:
        sid = request.match_info["sid"]
        session = self.sessions.get(sid)
        if not session:
            return web.json_response({"ok": False, "error": "invalid session"}, status=404)
        if not session.state.connected_to_ap:
            return web.json_response({"ok": False, "error": "not connected"}, status=400)
        try:
            data = await request.json()
        except Exception:
            data = {}
        if not isinstance(data, dict):
            data = {}
        stamped_pairs = data.get("stamped_pairs")
        if not isinstance(stamped_pairs, (list, dict)):
            stamped_pairs = []
        bingo_completed = await session.conn.merge_bingo_stamps(stamped_pairs)
        return web.json_response({
            "ok": True,
            "bingo_completed": bingo_completed,
            "status": session.conn.state.to_status(),
        })

    async def session_use_bingo_stamp(self, request: web.Request) -> web.StreamResponse:
        sid = request.match_info["sid"]
        session = self.sessions.get(sid)
        if not session:
            return web.json_response({"ok": False, "error": "invalid session"}, status=404)
        try:
            data = await request.json()
        except Exception:
            data = {}
        if not isinstance(data, dict):
            data = {}
        result = await session.conn.use_bingo_stamp(
            data.get("board"),
            data.get("row"),
            data.get("col"),
        )
        status_code = 200 if result.get("ok") else 400
        return web.json_response(result, status=status_code)

    async def session_debug(self, request: web.Request) -> web.StreamResponse:
        sid = request.match_info["sid"]
        session = self.sessions.get(sid)
        if not session:
            return web.json_response({"ok": False, "error": "invalid session"}, status=404)
        try:
            data = await request.json()
        except Exception:
            data = {}
        if not isinstance(data, dict):
            data = {}
        action = str(data.get("action") or "").strip()
        result = await session.conn.debug_action(action, data)
        # Drain pending events once (same as /status) so DeathLink/traps don't double-fire on poll.
        if isinstance(result.get("status"), dict):
            result["status"]["pending_events"] = session.conn.take_pending_events()
        status_code = 200 if result.get("ok") else 400
        return web.json_response(result, status=status_code)

    def build(self) -> web.Application:
        app = web.Application()
        app.router.add_get("/", self.index)
        app.router.add_get("/manifest.webmanifest", self.manifest)
        app.router.add_get("/service-worker.js", self.service_worker)
        app.router.add_get("/health", self.health)
        app.router.add_post("/api/session", self.create_session)
        app.router.add_post("/api/session/{sid}/connect", self.connect_session)
        app.router.add_post("/api/session/{sid}/practice", self.practice_session)
        app.router.add_post("/api/session/{sid}/disconnect", self.disconnect_session)
        app.router.add_get("/api/session/{sid}/status", self.session_status)
        app.router.add_post("/api/session/{sid}/death", self.session_death)
        app.router.add_post("/api/session/{sid}/check", self.session_check)
        app.router.add_post("/api/session/{sid}/bingo-stamps", self.session_bingo_stamps)
        app.router.add_post("/api/session/{sid}/bingo-stamp", self.session_use_bingo_stamp)
        app.router.add_post("/api/session/{sid}/reroll-target", self.session_reroll_target)
        app.router.add_post("/api/session/{sid}/use-back", self.session_use_back)
        app.router.add_post("/api/session/{sid}/debug", self.session_debug)
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


















