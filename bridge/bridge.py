
import argparse
import asyncio
import functools
import ipaddress
import json
import logging
import math
import os
import random
import socket
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
LOG = logging.getLogger("wikipelago-bridge")

# Client/release label for the hosted UI (independent of apworld tag until a release cut).
CLIENT_VERSION = "1.1.0"
TELEPORT_COOLDOWN_SEC = 60
# Wiki Compass: backlink pages (500 titles each) fetched per target, once per session.
COMPASS_BACKLINK_PAGES = 2
# Wikimedia asks API clients for a descriptive User-Agent with a contact URL; vague ones get throttled first.
WIKI_USER_AGENT = f"WikipelagoBridge/{CLIENT_VERSION} (https://github.com/Dreskn/Wikipelago-Continued)"
# The 9 wikis the apworld supports. Anything else from slot_data or a request falls back to English,
# so a room can't point the bridge's Wikipedia requests at another host.
WIKI_LANGUAGES = frozenset({"en", "fr", "de", "es", "it", "pt", "nl", "sv", "pl"})
WIKI_MAX_RESPONSE_BYTES = 4 * 1024 * 1024
# Per-session Compass/title caches are small LRUs: targets stay hot, old pages fall out.
LINK_CACHE_SIZE = 40
BACKLINK_CACHE_SIZE = 20
TITLE_CACHE_SIZE = 2000
# Wikipedia titles are at most 255 bytes; anything much longer is not a page.
MAX_TITLE_CHARS = 300
MAX_REQUEST_BYTES = 256 * 1024
MAX_SESSIONS = 1000
MAX_SESSIONS_PER_CLIENT = 40
# A full server or client may reclaim sessions idle this long (they still expire after SESSION_TTL_SECONDS).
SESSION_RECLAIM_IDLE_SECONDS = 120
PRIVATE_SERVER_ERROR = (
    "This address is on a private network, which the hosted client can't reach. "
    "For private or VPN rooms, run the client on your own computer (see the setup guide)."
)

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _env_first(*names: str) -> str:
    for name in names:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return ""


def debug_menu_enabled() -> bool:
    """Playtest debug console. Off by default; set WIKIPELAGO_DEBUG_MENU=1 and restart."""
    return (_env_first("WIKIPELAGO_DEBUG_MENU") or "").lower() in ("1", "true", "yes", "on")


def _git_output(*args: str) -> str:
    """Best-effort git identity for self-hosted deploys."""
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


@functools.lru_cache(maxsize=1)
def _git_identity() -> tuple[str, str]:
    """(branch, commit) of the checkout, read once: a deploy restarts the bridge, so they can't change while it runs."""
    branch = _git_output("rev-parse", "--abbrev-ref", "HEAD")
    if branch == "HEAD":
        # Detached checkout — keep a usable label if possible.
        branch = _git_output("name-rev", "--name-only", "--no-undefined", "HEAD") or "HEAD"
    return branch, _git_output("rev-parse", "HEAD")


def build_info() -> dict[str, Any]:
    """Deploy identity for the UI: WIKIPELAGO_* overrides, then `git` in the repo root."""
    branch = _env_first("WIKIPELAGO_GIT_BRANCH")
    commit_full = _env_first("WIKIPELAGO_GIT_COMMIT")
    service = _env_first("WIKIPELAGO_SERVICE_NAME")

    if not branch or not commit_full:
        git_branch, git_commit = _git_identity()
        branch = branch or git_branch
        commit_full = commit_full or git_commit
    if not branch:
        branch = "local"

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
        "debug_menu": debug_menu_enabled(),
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
    "Branch Key": 1_870_048,
    "Wrong Wiki": 1_870_049,
}

# Topic Realms: must match world Items.PORTAL_ITEM_BY_TOPIC (same order, ids from +50).
PORTAL_ITEM_BY_TOPIC: dict[str, str] = {
    "video_games": "Video Games Portal",
    "movies": "Film Portal",
    "tv_shows": "Television Portal",
    "anime_manga": "Anime & Manga Portal",
    "sports": "Sports Portal",
    "science_space": "Science & Space Portal",
    "technology": "Technology Portal",
    "history": "History Portal",
    "geography": "Geography Portal",
    "food_cuisine": "Food Portal",
    "art_literature": "Arts & Literature Portal",
    "mythology_folklore": "Legends & Beliefs Portal",
    "music": "Music Portal",
    "politics": "Politics Portal",
    "famous_people": "People Portal",
    "miscellaneous": "Curiosities Portal",
    "animals": "Animals Portal",
    "biology_medicine": "Biology & Medicine Portal",
}
for _portal_index, _portal_name in enumerate(PORTAL_ITEM_BY_TOPIC.values(), start=50):
    DEFAULT_ITEMS[_portal_name] = 1_870_000 + _portal_index

TRAP_ITEM_NAMES = frozenset({"Foggy Links", "Missing Links", "Wrong Wiki"})
LINK_BOMB_DENSITY_COUNTS = {0: 1, 1: 5, 2: 20}
# Fallback max for legacy seeds that omit target_rerolls_start.
TARGET_REROLLS_PER_ROUND = 3
MAX_TRAVEL_EVENTS = 5000
# The stored journey may run this far past MAX_TRAVEL_EVENTS before it is rewritten trimmed.
TRAVEL_TRIM_SLACK = 500
PROGRESSIVE_STACK_ITEMS = frozenset({
    "Knowledge Fragment",
    "Round Access",
    "Branch Key",
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
    "Branch Key",
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

SESSION_TTL_SECONDS = 60 * 60
# Transient AP drops: retry a few times, then stop and surface last_error.
# ConnectionRefused (bad password/slot) never retries.
MAX_AP_CONNECT_ATTEMPTS = 3


def normalize_title(title: str) -> str:
    # Accents stay: in many wikis "Año" and "Ano", or "Bürger" and "Burger", are different articles.
    spaced = " ".join(title.replace("_", " ").strip().split())
    return unicodedata.normalize("NFC", spaced).casefold()


def wiki_language(value: Any) -> str:
    """A supported Wikipedia language code, or "" when the value isn't one."""
    code = str(value or "").strip().lower()
    return code if code in WIKI_LANGUAGES else ""


def cache_get(cache: dict[str, Any], key: str) -> Any:
    """Read from a dict used as a small LRU cache; a hit moves the entry to the newest end."""
    if key not in cache:
        return None
    value = cache.pop(key)
    cache[key] = value
    return value


def cache_put(cache: dict[str, Any], key: str, value: Any, limit: int) -> None:
    cache.pop(key, None)
    cache[key] = value
    while len(cache) > limit:
        del cache[next(iter(cache))]


def _is_public_ip(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(str(address or "").split("%", 1)[0])
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global


def client_address(request: web.Request) -> str:
    """The browser's address. Behind Caddy the bridge only sees 127.0.0.1, so use the address the proxy appended."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.remote or ""


def is_local_request(request: web.Request) -> bool:
    """True when the browser reaches this bridge directly from this machine or its own network, not through
    a reverse proxy: only then may it connect to Archipelago servers on private addresses."""
    if any(name in request.headers for name in ("X-Forwarded-For", "Forwarded", "X-Real-IP")):
        return False
    remote = request.remote or ""
    try:
        ipaddress.ip_address(remote.split("%", 1)[0])
    except ValueError:
        return False
    return not _is_public_ip(remote)


def split_server_address(server: str) -> tuple[str, int | None]:
    """(host, port) from what players type: "archipelago.gg:38281", "wss://host:port/", "[::1]:38281"."""
    cleaned = str(server or "").strip()
    for prefix in ("wss://", "ws://", "https://", "http://"):
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix):]
            break
    hostport = cleaned.strip("/").split("/", 1)[0]
    port_text = ""
    if hostport.startswith("["):
        host, _, rest = hostport[1:].partition("]")
        port_text = rest[1:] if rest.startswith(":") else ""
    elif hostport.count(":") == 1:
        host, port_text = hostport.split(":", 1)
    else:
        host = hostport
    port: int | None = None
    if port_text:
        try:
            port = int(port_text)
        except ValueError:
            port = None
    return host.strip().lower(), port


async def ap_server_address_error(server: str, allow_private: bool) -> str:
    """Why this Archipelago address can't be used, or "". A public bridge must not let visitors reach
    machines on the network behind it, so private, loopback and similar addresses are refused there."""
    host, port = split_server_address(server)
    if not host:
        return "Unable to reach server. Check the address."
    if allow_private:
        return ""
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, port or 38281, type=socket.SOCK_STREAM)
    except (OSError, UnicodeError):
        return "Unable to reach server. Check the address."
    if not infos or any(not _is_public_ip(info[4][0]) for info in infos):
        return PRIVATE_SERVER_ERROR
    return ""


async def read_json_body(request: web.Request) -> dict[str, Any]:
    """The request's JSON object, or {} when the body is missing or malformed."""
    try:
        data = await request.json()
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def compass_hint(previous: tuple[int, int] | None, current: tuple[int, int]) -> str:
    """Wiki Compass word for a (level, overlap) reading compared with the previous one for that target."""
    level, overlap = current
    if level == 0:
        return "On target"
    if previous is None:
        return "Calibrating"
    prev_level, prev_overlap = previous
    if level != prev_level:
        return "Warmer" if level < prev_level else "Colder"
    # Same level: compare link overlap, ignoring small wobbles (about 12%).
    margin = max(1, prev_overlap // 8)
    if overlap >= prev_overlap + margin:
        return "Warmer"
    if overlap <= prev_overlap - margin:
        return "Colder"
    return "Same"


# Must match world/APWorldSource/wikipelago/letter_pairs.py (Scrabble alphabets).
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


# Ligatures Unicode does not decompose; Scrabble plays them as two tiles (French Œuf = O-E).
_BINGO_LIGATURES: dict[str, str] = {"œ": "OE", "Œ": "OE", "æ": "AE", "Æ": "AE"}


def _fold_bingo_base_latin(ch: str) -> str:
    if ch in ("ß", "ẞ"):
        return "SS"
    if ch in _BINGO_LIGATURES:
        return _BINGO_LIGATURES[ch]
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
    Path(__file__).resolve().parent.parent / "world" / "APWorldSource" / "wikipelago" / "data"
)
PRACTICE_SUPPORTED_LANGS = ("en", "fr", "de", "es", "it", "pt", "nl", "sv", "pl")
_PRACTICE_POOL_CACHE: dict[str, list[str]] = {}
# Practice extras: one 5x5 bingo board and one open Realm, each replaceable once finished. No checks.
PRACTICE_BINGO_GRID = 5
PRACTICE_REALM_LENGTH = 5
PRACTICE_REALM_REROLL_MAX = 300
_PRACTICE_TOPIC_CACHE: dict[str, dict[str, list[str]]] = {}
_LETTER_PAIRS_MODULE: Any = None
_ARTICLE_POOL_MODULE: Any = None


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
        if not article_pool_module().is_usable_title(title, code):
            continue
        titles.append(title)
    # Preserve order, drop dupes.
    titles = list(dict.fromkeys(titles))
    if len(titles) < 3:
        raise RuntimeError(f"Practice pool for '{code}' is too small ({len(titles)} titles).")
    _PRACTICE_POOL_CACHE[cache_key] = titles
    return list(titles)


def load_practice_topics(lang: str = "en") -> dict[str, list[str]]:
    """Non-sensitive practice titles grouped by Realm topic tag (same pools and tags as the apworld)."""
    code = (lang or "en").strip().lower()
    cached = _PRACTICE_TOPIC_CACHE.get(code)
    if cached is not None:
        return {tag: list(titles) for tag, titles in cached.items()}
    path = PRACTICE_POOL_DIR / f"pool_{code}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    by_tag: dict[str, list[str]] = {}
    for entry in payload.get("entries") or []:
        title = str(entry.get("title") or "").strip()
        if not title or bool(entry.get("sensitive")) or not article_pool_module().is_usable_title(title, code):
            continue
        for tag in entry.get("tags") or []:
            if tag in PORTAL_ITEM_BY_TOPIC:
                by_tag.setdefault(str(tag), []).append(title)
    by_tag = {tag: list(dict.fromkeys(titles)) for tag, titles in by_tag.items()}
    _PRACTICE_TOPIC_CACHE[code] = by_tag
    return {tag: list(titles) for tag, titles in by_tag.items()}


def article_pool_module() -> Any:
    """The apworld's article_pool.py, so Practice skips the same titles real seeds skip (list pages, banned words)."""
    global _ARTICLE_POOL_MODULE
    if _ARTICLE_POOL_MODULE is None:
        import importlib.util

        path = PRACTICE_POOL_DIR.parent / "article_pool.py"
        spec = importlib.util.spec_from_file_location("wikipelago_article_pool", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _ARTICLE_POOL_MODULE = module
    return _ARTICLE_POOL_MODULE


def letter_pairs_module() -> Any:
    """The apworld's letter_pairs.py, for building practice boards with the same weights as real seeds."""
    global _LETTER_PAIRS_MODULE
    if _LETTER_PAIRS_MODULE is None:
        import importlib.util

        path = PRACTICE_POOL_DIR.parent / "letter_pairs.py"
        spec = importlib.util.spec_from_file_location("wikipelago_letter_pairs", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _LETTER_PAIRS_MODULE = module
    return _LETTER_PAIRS_MODULE


@dataclass
class SessionState:
    connected_to_ap: bool = False
    practice: bool = False
    practice_pool_titles: list[str] = field(default_factory=list)
    ap_server: str = ""
    slot_name: str = ""
    goal: str = "grand_goal"
    topic_portals: bool = False
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
    bingo_letterpairs_boards: list[list[list[str]]] = field(default_factory=list)
    bingo_cards_start: int = 0
    bingo_letterpairs_location_ids: dict[str, dict[str, int]] = field(default_factory=dict)
    bingo_stamped_pairs: dict[str, set[str]] = field(default_factory=dict)
    bingo_stamps_used: int = 0
    bingo_storage_ready: bool = False
    # Practice only: bingo lines already completed per board (no AP locations to tick).
    practice_bingo_lines: dict[str, set[str]] = field(default_factory=dict)
    pending_events: list[dict[str, Any]] = field(default_factory=list)
    round_pairs: list[dict[str, str]] = field(default_factory=list)
    goal_article_title: str = ""
    goal_question: str = ""
    wikipedia_language: str = "en"
    reroll_pool: list[str] = field(default_factory=list)
    target_rerolls_start: int = TARGET_REROLLS_PER_ROUND
    target_rerolls_used: int = 0
    target_rerolls_round: str = ""
    back_depth_start: int = 0
    backs_used: int = 0
    backs_round: str = ""
    # Rerolled targets and this main round's Reroll/Back use, kept across reconnects and stored in AP
    # DataStorage (wikipelago_progress_{team}_{slot}): {"main:3": {"target": ..., "n": 1},
    # "branch:0:1": {"target": ..., "n": 2}, "uses": {"round": 3, "rerolls": 1, "backs": 2}}.
    # n counts the rerolls of that round, so the most rerolled copy wins when devices race.
    progress_entries: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Seed, team and slot the entries belong to.
    progress_owner: str = ""
    progress_storage_ready: bool = False
    location_round_ids: list[int] = field(default_factory=list)
    location_grand_goal: int | None = None
    location_branch_ids: list[list[int]] = field(default_factory=list)
    item_ids: dict[str, int] = field(default_factory=lambda: DEFAULT_ITEMS.copy())
    received_items: list[int] = field(default_factory=list)
    checked_locations: set[int] = field(default_factory=set)
    round_index: int = 0
    clicks_used: int = 0
    clicks_storage_ready: bool = False
    last_page: str = ""
    last_teleport_at: float = 0.0
    crossroads: list[dict[str, Any]] = field(default_factory=list)
    branches: list[dict[str, Any]] = field(default_factory=list)
    branch_round_index: dict[int, int] = field(default_factory=dict)
    travel_events: list[dict[str, Any]] = field(default_factory=list)
    visit_counts: dict[str, int] = field(default_factory=dict)
    travel_storage_ready: bool = False
    warmer_colder: str | None = None
    # Wiki Compass: last (level, overlap) reading per live target title, and which target the hint is about.
    compass_memory: dict[str, tuple[int, int]] = field(default_factory=dict)
    compass_target: dict[str, Any] | None = None
    boss_completed: bool = False
    goal_status_sent: bool = False
    last_error: str = ""
    last_seen: float = field(default_factory=lambda: time.time())
    slot: int = 0
    team: int = 0
    player_names: dict[int, str] = field(default_factory=dict)
    slot_games: dict[int, str] = field(default_factory=dict)
    item_id_to_name: dict[str, dict[int, str]] = field(default_factory=dict)

    def progress_key(self) -> str:
        return f"main:{self.round_index}"

    def current_target(self) -> str:
        if self.round_index >= len(self.round_pairs):
            return self.goal_article()
        return self.round_pairs[self.round_index]["target"]

    def current_start(self) -> str:
        if not self.round_pairs:
            return ""
        if self.round_index >= len(self.round_pairs):
            return self.round_pairs[-1]["target"]
        return self.round_pairs[self.round_index]["start"]

    def is_realm_master(self) -> bool:
        return self.goal == "realm_master"

    def reset_compass(self) -> None:
        self.warmer_colder = None
        self.compass_memory = {}
        self.compass_target = None

    def compass_targets(self) -> list[dict[str, Any]]:
        """Live targets the Wiki Compass can point at: the main road plus every open branch / Realm."""
        targets: list[dict[str, Any]] = []
        if self.boss_completed:
            return targets
        main = self.current_target()
        if main:
            targets.append({"kind": "main", "title": main})
        for live in self.live_branch_targets():
            if live.get("target"):
                targets.append({
                    "kind": "branch",
                    "branch_id": live["id"],
                    "fork": live["fork"],
                    "theme_tag": live["theme_tag"],
                    "title": live["target"],
                })
        return targets

    def goal_article(self) -> str:
        if self.is_realm_master():
            return ""
        if self.goal_article_title:
            return self.goal_article_title
        return self.round_pairs[-1]["target"] if self.round_pairs else ""

    def realm_cleared(self, branch_id: int) -> bool:
        if self.practice:
            pairs = self.branch_pairs(branch_id)
            return bool(pairs) and int(self.branch_round_index.get(int(branch_id), 0) or 0) >= len(pairs)
        try:
            loc_ids = self.location_branch_ids[int(branch_id)]
        except Exception:
            return False
        return bool(loc_ids) and all(loc_id in self.checked_locations for loc_id in loc_ids)

    def realms_cleared_count(self) -> int:
        return sum(1 for bid in range(len(self.location_branch_ids)) if self.realm_cleared(bid))

    def realm_master_met(self) -> bool:
        if not self.is_realm_master() or not self.location_branch_ids:
            return False
        return self.realms_cleared_count() >= len(self.location_branch_ids)

    def branch_portal_item(self, branch_id: int) -> str:
        branch = self.branch_by_id(branch_id)
        return str((branch or {}).get("portal_item") or "")

    def realms_payload(self) -> list[dict[str, Any]]:
        """One row per branch / Realm for the HUD (locked, open, cleared)."""
        unlocked = set(self.unlocked_branch_ids())
        crossroad_by_branch: dict[int, int] = {}
        for cr in self.crossroads:
            try:
                crossroad_by_branch[int(cr.get("branch_id") or 0)] = int(cr.get("main_round") or 0)
            except Exception:
                continue
        rows: list[dict[str, Any]] = []
        for branch in self.branches:
            try:
                bid = int(branch.get("id") or 0)
            except Exception:
                continue
            pairs = branch.get("pairs") or []
            length = len(pairs) if isinstance(pairs, list) else 0
            idx = int(self.branch_round_index.get(bid, 0) or 0)
            portal = str(branch.get("portal_item") or "")
            rows.append({
                "id": bid,
                "fork": bid + 1,
                "theme_tag": str(branch.get("theme_tag") or ""),
                "portal_item": portal,
                "has_portal": bool(portal) and self.has_item(portal),
                "crossroad_round": crossroad_by_branch.get(bid, 0),
                "unlocked": bid in unlocked,
                "completed": min(idx, length),
                "length": length,
                "cleared": self.realm_cleared(bid),
            })
        return rows

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

    def teleport_cooldown_remaining(self) -> int:
        if self.last_teleport_at <= 0:
            return 0
        left = TELEPORT_COOLDOWN_SEC - (time.time() - self.last_teleport_at)
        if left <= 0:
            return 0
        return int(math.ceil(left))

    def owned_search_letters(self) -> list[str]:
        letters = set(self.search_starting_letters)
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            if self.has_item(f"Search Letter {letter}"):
                letters.add(letter)
        return sorted(letters)

    def boss_ready(self) -> bool:
        if self.practice or self.is_realm_master():
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

    def stored_round_uses(self, kind: str) -> int:
        """Rerolls or Backs ("rerolls" / "backs") already spent this main round, from the slot's stored progress."""
        uses = self.progress_entries.get("uses")
        if self.practice or not uses or uses.get("round") != self.round_index:
            return 0
        return int(uses.get(kind) or 0)

    def progress_ready(self) -> bool:
        """Rerolls and Backs wait until the slot's stored progress has been read (Practice keeps none)."""
        return self.practice or self.progress_storage_ready

    def sync_back_counter(self) -> None:
        key = self.progress_key()
        if self.backs_round != key:
            self.backs_round = key
            self.backs_used = self.stored_round_uses("backs")

    def sync_target_reroll_counter(self) -> None:
        key = self.progress_key()
        if self.target_rerolls_round != key:
            self.target_rerolls_round = key
            self.target_rerolls_used = self.stored_round_uses("rerolls")

    def backs_remaining(self) -> int:
        self.sync_back_counter()
        return max(0, self.back_depth_max() - self.backs_used)

    def can_go_back(self) -> bool:
        self.sync_back_counter()
        if not self.is_playable() or not self.progress_ready():
            return False
        return self.backs_remaining() > 0

    def target_rerolls_max(self) -> int:
        return max(0, self.target_rerolls_start) + self.item_count("Progressive Reroll")

    def target_rerolls_remaining(self) -> int:
        self.sync_target_reroll_counter()
        return max(0, self.target_rerolls_max() - self.target_rerolls_used)

    def can_reroll_target(self) -> bool:
        self.sync_target_reroll_counter()
        if not self.is_playable() or self.boss_completed or not self.progress_ready():
            return False
        if self.target_rerolls_remaining() <= 0:
            return False
        if not self.reroll_pool:
            return False
        return bool(self.rerollable_target_slots())

    def rerollable_target_slots(self) -> list[dict[str, Any]]:
        slots: list[dict[str, Any]] = []
        if self.round_index < len(self.round_pairs):
            target = str(self.round_pairs[self.round_index].get("target") or "")
            if target:
                slots.append({"kind": "main", "old_target": target})
        for item in self.live_branch_targets():
            target = str(item.get("target") or "")
            if not target:
                continue
            slots.append({
                "kind": "branch",
                "branch_id": int(item.get("id") or 0),
                "fork": int(item.get("fork") or 0),
                "old_target": target,
            })
        return slots

    def target_in_use(self, title: str) -> bool:
        """True when a main road or Realm round has this target."""
        def _norm(value: Any) -> str:
            return str(value or "").replace("_", " ").strip().casefold()

        needle = _norm(title)
        if not needle:
            return False
        if any(_norm(pair.get("target")) == needle for pair in self.round_pairs):
            return True
        return any(
            isinstance(pair, dict) and _norm(pair.get("target")) == needle
            for branch in self.branches
            for pair in (branch.get("pairs") or [])
        )

    def branch_key_count(self) -> int:
        return self.item_count("Branch Key")

    def branch_keys_available(self) -> int:
        if self.topic_portals:
            return 0
        return max(0, self.branch_key_count() - len(self.unlocked_branch_ids()))

    def reached_main_round(self) -> int:
        if self.boss_completed:
            return max(self.check_count, 1)
        return min(self.round_index + 1, max(self.check_count, 1))

    def completed_crossroad_branch_ids(self) -> list[int]:
        completed: list[tuple[int, int]] = []
        for cr in self.crossroads:
            try:
                main_round = int(cr.get("main_round") or 0)
                branch_id = int(cr.get("branch_id") or 0)
            except Exception:
                continue
            if main_round < 1 or main_round > len(self.location_round_ids):
                continue
            loc_id = self.location_round_ids[main_round - 1]
            if loc_id in self.checked_locations:
                completed.append((main_round, branch_id))
        completed.sort(key=lambda item: item[0])
        return [branch_id for _main, branch_id in completed]

    def unlocked_branch_ids(self) -> list[int]:
        if self.practice:
            # The practice Realm is open from the start: no crossroad, key or Portal.
            return [int(branch.get("id") or 0) for branch in self.branches]
        if self.topic_portals:
            # Topic Realms: finished crossroad + that Realm's own Portal, in any order.
            return [
                bid for bid in self.completed_crossroad_branch_ids()
                if self.branch_portal_item(bid) and self.has_item(self.branch_portal_item(bid))
            ]
        keys = self.branch_key_count()
        if keys <= 0:
            return []
        completed = self.completed_crossroad_branch_ids()
        return completed[: min(keys, len(completed), len(self.branches))]

    def is_branch_unlocked(self, branch_id: int) -> bool:
        return int(branch_id) in set(self.unlocked_branch_ids())

    def revealed_crossroad(self) -> dict[str, Any] | None:
        current_round = self.reached_main_round()
        for cr in self.crossroads:
            try:
                main_round = int(cr.get("main_round") or 0)
                branch_id = int(cr.get("branch_id") or 0)
            except Exception:
                continue
            if main_round != current_round:
                continue
            unlocked = self.is_branch_unlocked(branch_id)
            branch = self.branch_by_id(branch_id)
            portal = str((branch or {}).get("portal_item") or "")
            return {
                "main_round": main_round,
                "branch_id": branch_id,
                "fork": branch_id + 1,
                "theme_tag": str((branch or {}).get("theme_tag") or ""),
                "portal_item": portal,
                "has_portal": bool(portal) and self.has_item(portal),
                "unlocked": unlocked,
                "needs_key": not unlocked,
            }
        return None

    def crossroad_rounds(self) -> list[int]:
        current = self.reached_main_round()
        rounds: list[int] = []
        for cr in self.crossroads:
            try:
                main_round = int(cr.get("main_round") or 0)
            except Exception:
                continue
            if 1 <= main_round <= current:
                rounds.append(main_round)
        return rounds

    def unlocked_crossroad_rounds(self) -> list[int]:
        reached = set(self.crossroad_rounds())
        unlocked = set(self.unlocked_branch_ids())
        rounds: list[int] = []
        for cr in self.crossroads:
            try:
                main_round = int(cr.get("main_round") or 0)
                branch_id = int(cr.get("branch_id") or 0)
            except Exception:
                continue
            if main_round in reached and branch_id in unlocked:
                rounds.append(main_round)
        return rounds

    def branch_by_id(self, branch_id: int) -> dict[str, Any] | None:
        try:
            bid = int(branch_id)
        except Exception:
            return None
        for branch in self.branches:
            try:
                if int(branch.get("id", -1)) == bid:
                    return branch
            except Exception:
                continue
        return None

    def branch_pairs(self, branch_id: int) -> list[dict[str, str]]:
        branch = self.branch_by_id(branch_id)
        if branch is None:
            return []
        pairs = branch.get("pairs") or []
        return pairs if isinstance(pairs, list) else []

    def branch_current_target(self, branch_id: int) -> str:
        pairs = self.branch_pairs(branch_id)
        try:
            idx = int(self.branch_round_index.get(int(branch_id), 0) or 0)
        except Exception:
            idx = 0
        if idx < 0 or idx >= len(pairs):
            return ""
        return str(pairs[idx].get("target") or "")

    def live_branch_targets(self) -> list[dict[str, Any]]:
        live: list[dict[str, Any]] = []
        for bid in self.unlocked_branch_ids():
            branch = self.branch_by_id(bid)
            if branch is None:
                continue
            pairs = self.branch_pairs(bid)
            idx = int(self.branch_round_index.get(bid, 0) or 0)
            if idx >= len(pairs):
                continue
            live.append({
                "id": bid,
                "fork": bid + 1,
                "theme_tag": str(branch.get("theme_tag") or ""),
                "portal_item": str(branch.get("portal_item") or ""),
                "target": str(pairs[idx].get("target") or ""),
                "round": min(idx + 1, max(len(pairs), 1)),
                "length": len(pairs),
                "completed": min(idx, len(pairs)),
            })
        return live

    def path_payload(self) -> list[dict[str, Any]]:
        unlocked = set(self.unlocked_branch_ids())
        paths: list[dict[str, Any]] = [{
            "id": "main",
            "label": "Main road",
            "theme_tag": "",
            "unlocked": True,
            "round": min(self.round_index + 1, self.check_count),
            "length": self.check_count,
            "completed": min(self.round_index, self.check_count),
            "current_target": self.current_target(),
        }]
        for branch in self.branches:
            try:
                bid = int(branch.get("id") or 0)
            except Exception:
                continue
            if bid not in unlocked:
                continue
            pairs = branch.get("pairs") or []
            length = len(pairs) if isinstance(pairs, list) else 0
            idx = int(self.branch_round_index.get(bid, 0) or 0)
            current_target = ""
            if isinstance(pairs, list) and 0 <= idx < length:
                current_target = str(pairs[idx].get("target") or "")
            paths.append({
                "id": f"branch:{bid}",
                "fork": bid + 1,
                "label": str(branch.get("theme_tag") or f"Branch {bid + 1}"),
                "theme_tag": str(branch.get("theme_tag") or ""),
                "unlocked": bid in unlocked,
                "round": min(idx + 1, max(length, 1)),
                "length": length,
                "completed": min(idx, length),
                "current_target": current_target,
            })
        return paths

    def travel_payload(self) -> dict[str, Any]:
        return {
            "events": list(self.travel_events),
            "visit_counts": dict(self.visit_counts),
        }

    def merge_clicks(self, reported: int) -> int:
        try:
            incoming = max(0, int(reported))
        except Exception:
            incoming = 0
        self.clicks_used = max(int(self.clicks_used or 0), incoming)
        return self.clicks_used

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

    def bingo_line_keys(self, board_key: str) -> list[str]:
        n = len(self.bingo_board_for_key(board_key))
        if n <= 0:
            return []
        return [f"row_{i}" for i in range(1, n + 1)] + [f"col_{i}" for i in range(1, n + 1)] + ["diag", "anti", "full"]

    def practice_board_full(self) -> bool:
        return self.practice and self.bingo_letterpairs and "full" in self.bingo_completed_line_keys_for_board("1")

    def bingo_lines_checked(self) -> dict[str, dict[str, bool]]:
        result: dict[str, dict[str, bool]] = {}
        if self.practice:
            for board_key in self.unlocked_bingo_board_keys():
                done = set(self.bingo_completed_line_keys_for_board(board_key))
                result[board_key] = {key: key in done for key in self.bingo_line_keys(board_key)}
            return result
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
            "goal": self.goal,
            "topic_portals": self.topic_portals,
            "realms": self.realms_payload(),
            "practice_bingo_full": self.practice_board_full(),
            "practice_realm_cleared": bool(self.practice and self.branches and self.realm_cleared(0)),
            "ap_server": self.ap_server,
            "slot_name": self.slot_name,
            "current_start": self.current_start(),
            "current_target": self.current_target(),
            "goal_article": self.goal_article(),
            "goal_question": self.goal_question,
            "wikipedia_language": self.wikipedia_language or "en",
            "round": min(self.round_index + 1, self.check_count),
            "rounds_completed": min(self.round_index, self.check_count),
            "check_count": self.check_count,
            "target_rerolls_max": self.target_rerolls_max(),
            "target_rerolls_remaining": self.target_rerolls_remaining(),
            "can_reroll_target": self.can_reroll_target(),
            "clicks_used": self.clicks_used,
            "fragments": self.fragments(),
            "required_fragments": self.required_fragments,
            "round_access_count": self.round_access_count(),
            "unlocked_rounds": self.unlocked_rounds(),
            "searchsanity": self.searchsanity,
            "scrollsanity": self.scrollsanity,
            "scroll_speed_upgrades": self.scroll_speed_upgrades,
            "scroll_speed_level": self.item_count("Progressive Scroll Speed"),
            "back_depth_max": self.back_depth_max(),
            "backs_remaining": self.backs_remaining(),
            "can_go_back": self.can_go_back(),
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
            "bingo_letterpairs_boards": self.bingo_letterpairs_boards,
            "bingo_unlocked_boards": self.unlocked_bingo_boards(),
            "bingo_stamps_max": self.bingo_stamps_max(),
            "bingo_stamps_remaining": self.bingo_stamps_remaining(),
            "bingo_stamped_pairs": stamped_pairs,
            "bingo_stamped_cells": self.bingo_stamped_cells(),
            "bingo_lines_checked": self.bingo_lines_checked(),
            "bingo_storage_ready": self.bingo_storage_ready,
            # Filled only by the endpoints that drain the queue (/status, /debug): every other
            # response carries a status too, and listing events there delivered them twice.
            "pending_events": [],
            "tables_unlocked": (not self.randomize_tables) or self.has_item("Table Lens"),
            "pictures_unlocked": (not self.randomize_pictures) or self.has_item("Picture Lens"),
            "incipit_unlocked": (not self.randomize_incipit) or self.has_item("Lead Lens"),
            "infoboxes_unlocked": (not self.randomize_infoboxes) or self.has_item("Infobox Lens"),
            "toc_unlocked": (not self.randomize_toc) or self.has_item("Contents Lens"),
            "navboxes_unlocked": (not self.randomize_navboxes) or self.has_item("Navbox Lens"),
            "hatnotes_unlocked": (not self.randomize_hatnotes) or self.has_item("Hatnote Lens"),
            "references_unlocked": (not self.randomize_references) or self.has_item("Reference Lens"),
            "warmer_colder": self.warmer_colder,
            "compass_target": self.compass_target,
            "boss_ready": self.boss_ready(),
            "boss_completed": self.boss_completed,
            "last_page": self.last_page,
            "teleport_cooldown_remaining": self.teleport_cooldown_remaining(),
            "last_error": self.last_error,
            "paths": self.path_payload(),
            "crossroads": list(self.crossroads),
            "crossroad_rounds": self.crossroad_rounds(),
            "unlocked_crossroad_rounds": self.unlocked_crossroad_rounds(),
            "branches": [
                {key: value for key, value in branch.items() if key != "reroll_pool"}
                for branch in self.branches
            ],
            "unlocked_branch_ids": self.unlocked_branch_ids(),
            "live_branch_targets": self.live_branch_targets(),
            "branch_keys_available": self.branch_keys_available(),
            "revealed_crossroad": self.revealed_crossroad(),
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
        self.allow_private = False
        self.link_cache: dict[str, set[str]] = {}
        self.backlink_cache: dict[str, tuple[set[str], set[str]]] = {}
        self.resolved_title_cache: dict[str, str] = {}
        # Length of the travel list in AP DataStorage, which only grows between full rewrites.
        self._travel_stored_len = 0
        self._clicks_persisted = -1
        self._compass_seq = 0
        self._compass_tasks: set[asyncio.Task] = set()
        self._scout_waiters: dict[int, asyncio.Future] = {}
        self._datapackage_requested = False
        # From RoomInfo: tells a reconnect to the same game from a new seed on the same address.
        self._room_seed = ""

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
            fresh_race = False
        else:
            start, target = random.sample(titles, 2)
            fresh_race = True

        blocked = {_norm(start), _norm(target)}
        rest = [title for title in titles if _norm(title) not in blocked]
        random.shuffle(rest)
        self.state.round_pairs = [{"start": start, "target": target}]
        self.state.round_index = 0
        self.state.check_count = 1
        self.state.reroll_pool = rest
        self.state.goal_article_title = ""
        self.state.goal_question = ""
        self.state.backs_used = 0
        self.state.backs_round = ""
        self.state.target_rerolls_used = 0
        self.state.target_rerolls_round = ""
        self.state.last_page = start
        self.state.crossroads = []
        self.state.goal = "grand_goal"
        self.state.topic_portals = False
        if fresh_race:
            # A chained practice round keeps its Realm; only a fresh race starts without one.
            self.state.branches = []
            self.state.branch_round_index = {}
            self.state.clicks_used = 0
            self.state.travel_events = []
            self.state.visit_counts = {}
            self.state.travel_storage_ready = False
            self.state.clicks_storage_ready = False
        self.state.reset_compass()
        self.state.boss_completed = False
        self.state.goal_status_sent = False

    def _new_practice_board(self) -> None:
        """A fresh 5x5 practice board, built like a real seed's (same per-language pair weights)."""
        lang = (self.state.wikipedia_language or "en").strip().lower() or "en"
        board = letter_pairs_module().build_letter_pair_bingo_board(random.Random(), PRACTICE_BINGO_GRID, lang)
        self.state.bingo_letterpairs = True
        self.state.bingo_letterpairs_boards = [board]
        self.state.bingo_cards_start = 1
        self.state.bingo_stamped_pairs.clear()
        self.state.practice_bingo_lines = {}

    def _new_practice_realm(self, *, avoid_topic: str = "") -> None:
        """One open practice Realm: PRACTICE_REALM_LENGTH targets from a single topic."""
        lang = (self.state.wikipedia_language or "en").strip().lower() or "en"
        by_tag = load_practice_topics(lang)

        def _norm(title: str) -> str:
            return str(title or "").replace("_", " ").strip().casefold()

        here = self.state.last_page or self.state.current_start()
        busy = {_norm(here), _norm(self.state.current_target())}
        options = {
            tag: [title for title in titles if _norm(title) not in busy]
            for tag, titles in by_tag.items()
            if tag != avoid_topic
        }
        viable = sorted(tag for tag, titles in options.items() if len(titles) >= PRACTICE_REALM_LENGTH)
        if not viable:
            self.state.branches = []
            self.state.branch_round_index = {}
            return
        tag = random.choice(viable)
        titles = options[tag]
        random.shuffle(titles)
        targets = titles[:PRACTICE_REALM_LENGTH]
        starts = [here] + targets[:-1]
        self.state.branches = [{
            "id": 0,
            "theme_tag": tag,
            "pairs": [{"start": start, "target": target} for start, target in zip(starts, targets)],
            # Realm rerolls stay on topic.
            "reroll_pool": titles[PRACTICE_REALM_LENGTH:PRACTICE_REALM_LENGTH + PRACTICE_REALM_REROLL_MAX],
        }]
        self.state.branch_round_index = {0: 0}

    async def new_practice_board(self) -> dict[str, Any]:
        if not self.state.practice:
            return {"ok": False, "error": "practice only", "status": self.state.to_status()}
        if not self.state.practice_board_full():
            return {"ok": False, "error": "board not full yet", "status": self.state.to_status()}
        self._new_practice_board()
        return {"ok": True, "status": self.state.to_status()}

    async def new_practice_realm(self) -> dict[str, Any]:
        if not self.state.practice:
            return {"ok": False, "error": "practice only", "status": self.state.to_status()}
        if not (self.state.branches and self.state.realm_cleared(0)):
            return {"ok": False, "error": "realm not cleared yet", "status": self.state.to_status()}
        previous = str((self.state.branch_by_id(0) or {}).get("theme_tag") or "")
        self._new_practice_realm(avoid_topic=previous)
        self._schedule_compass(self.state.last_page)
        return {"ok": True, "status": self.state.to_status()}

    async def start_practice(self, wikipedia_language: str = "en") -> dict[str, Any]:
        """Begin unlimited local Practice (no Archipelago). Exits any AP connection."""
        # Drop AP without treating this as "exit practice" (we are entering it).
        lang = wiki_language(wikipedia_language or "en")
        if not lang:
            raise ValueError("Unsupported Wikipedia language.")
        await self.disconnect(leave_practice=False)
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
        self.state.bingo_letterpairs_boards = []
        self.state.bingo_cards_start = 0
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
        self._new_practice_board()
        self._new_practice_realm()
        LOG.info(
            "Practice started lang=%s pool=%s start=%s target=%s",
            lang,
            len(titles),
            self.state.current_start(),
            self.state.current_target(),
        )
        return {"ok": True, "status": self.state.to_status()}

    async def connect(self, server: str, slot_name: str, password: str = "", *, allow_private: bool = False) -> None:
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
        self.allow_private = allow_private

        self.state.ap_server = server
        self.state.slot_name = slot_name
        self.state.connected_to_ap = False
        self.state.last_error = ""
        self.state.round_index = 0
        self.state.checked_locations.clear()
        self.state.received_items.clear()
        self.state.boss_completed = False
        self.state.goal_status_sent = False
        self.state.reset_compass()
        self.state.pending_events.clear()
        self.state.bingo_letterpairs = False
        self.state.bingo_letterpairs_boards = []
        self.state.bingo_cards_start = 0
        self.state.bingo_letterpairs_location_ids = {}
        self.state.bingo_stamped_pairs.clear()
        self.state.bingo_stamps_used = 0
        self.state.bingo_storage_ready = False
        self.state.clicks_storage_ready = False
        self.state.travel_storage_ready = False
        self.state.progress_storage_ready = False
        self.state.target_rerolls_start = TARGET_REROLLS_PER_ROUND
        self.state.target_rerolls_used = 0
        self.state.target_rerolls_round = ""
        self.state.back_depth_start = 0
        self.state.backs_used = 0
        self.state.backs_round = ""
        self.state.crossroads = []
        self.state.branches = []
        self.state.branch_round_index = {}
        self.state.location_branch_ids = []
        self.state.slot = 0
        self.state.team = 0
        self.state.player_names.clear()
        self.state.slot_games.clear()
        self.state.item_id_to_name.clear()
        # Switching slots/languages must not resume the previous wiki page.
        if slot_changed:
            self.state.last_page = ""
            self.state.clicks_used = 0
            self.state.travel_events = []
            self.state.visit_counts = {}
            self.state.wikipedia_language = "en"
            self.state.round_pairs = []
            self.state.goal_article_title = ""
            self.state.goal_question = ""
            self.state.reroll_pool = []
        self.items_seen = 0
        self.link_cache.clear()
        self.backlink_cache.clear()
        self.resolved_title_cache.clear()
        self._travel_stored_len = 0
        self._clicks_persisted = -1
        self._datapackage_requested = False
        self._room_seed = ""
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
            self.state.goal_question = ""
            self.state.received_items.clear()
            self.state.back_depth_start = 0
            self.state.target_rerolls_start = TARGET_REROLLS_PER_ROUND
            self.state.clicks_used = 0
            self.state.last_page = ""
            self.state.travel_events = []
            self.state.visit_counts = {}
            self.state.crossroads = []
            self.state.branches = []
            self.state.branch_round_index = {}
            # Practice bingo board goes with practice.
            self.state.bingo_letterpairs = False
            self.state.bingo_letterpairs_boards = []
            self.state.bingo_stamped_pairs.clear()
            self.state.practice_bingo_lines = {}
            self.state.reset_compass()
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
                # Checked on every attempt: the name could resolve differently on a retry.
                address_error = await ap_server_address_error(self.server, self.allow_private)
                if address_error:
                    self.state.connected_to_ap = False
                    self.state.last_error = address_error
                    return
                ws_url = self._to_ws_url(self.server)
                async with websockets.connect(ws_url, ping_interval=20, ping_timeout=20, max_size=2**24) as ws:
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
        # Raw socket errors would tell visitors which ports answer on the target; keep it generic.
        return "Unable to connect to the server. Check the address and that the room is running."

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
            if cmd == "RoomInfo":
                self._room_seed = str(packet.get("seed_name") or "")
            elif cmd == "Connected":
                self.state.connected_to_ap = True
                self.state.last_error = ""
                self._apply_connected(packet)
                await self._update_link_tags()
                await self._canonicalize_active_targets()
                await self._request_data_package()
                await self._request_bingo_stamps_from_storage()
                await self._request_clicks_from_storage()
                await self._request_travel_from_storage()
                await self._request_progress_from_storage()
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
            elif cmd == "RoomUpdate":
                await self._apply_room_update(packet)

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

        self.state.crossroads = []
        self.state.branches = []
        self.state.branch_round_index = {}
        crossroads_raw = slot_data.get("crossroads")
        if isinstance(crossroads_raw, list):
            parsed_cross: list[dict[str, Any]] = []
            for item in crossroads_raw:
                if not isinstance(item, dict):
                    continue
                try:
                    parsed_cross.append({
                        "main_round": int(item.get("main_round")),
                        "branch_id": int(item.get("branch_id")),
                    })
                except Exception:
                    continue
            self.state.crossroads = parsed_cross
        branches_raw = slot_data.get("branches")
        if isinstance(branches_raw, list):
            parsed_branches: list[dict[str, Any]] = []
            for item in branches_raw:
                if not isinstance(item, dict):
                    continue
                try:
                    bid = int(item.get("id"))
                except Exception:
                    continue
                pairs_raw = item.get("pairs") or []
                pairs: list[dict[str, str]] = []
                if isinstance(pairs_raw, list):
                    for pair in pairs_raw:
                        if not isinstance(pair, dict):
                            continue
                        start = self._canonicalize_known_title(str(pair.get("start", "")).strip())
                        target = self._canonicalize_known_title(str(pair.get("target", "")).strip())
                        if start and target:
                            pairs.append({"start": start, "target": target})
                parsed_branch: dict[str, Any] = {
                    "id": bid,
                    "theme_tag": str(item.get("theme_tag") or ""),
                    "pairs": pairs,
                }
                portal = str(item.get("portal_item") or "").strip()
                if portal:
                    parsed_branch["portal_item"] = portal
                realm_pool = item.get("reroll_pool")
                if isinstance(realm_pool, list):
                    parsed_branch["reroll_pool"] = [
                        self._canonicalize_known_title(str(title).strip())
                        for title in realm_pool
                        if str(title).strip()
                    ]
                parsed_branches.append(parsed_branch)
                self.state.branch_round_index[bid] = 0
            self.state.branches = parsed_branches

        goal_from_slot = slot_data.get("goal_article")
        if isinstance(goal_from_slot, str) and goal_from_slot.strip():
            self.state.goal_article_title = self._canonicalize_known_title(goal_from_slot.strip())
        elif self.state.round_pairs:
            # Legacy seeds: last round target was the Grand Goal.
            self.state.goal_article_title = self.state.round_pairs[-1]["target"]

        question_from_slot = slot_data.get("goal_question")
        if isinstance(question_from_slot, str) and question_from_slot.strip():
            self.state.goal_question = question_from_slot.strip()
        else:
            self.state.goal_question = ""

        wiki_lang = wiki_language(slot_data.get("wikipedia_language", "en"))
        if not wiki_lang:
            LOG.info("Unsupported wikipedia_language in slot_data: %r; using en", slot_data.get("wikipedia_language"))
        self.state.wikipedia_language = wiki_lang or "en"

        reroll_pool = slot_data.get("reroll_pool")
        if isinstance(reroll_pool, list):
            self.state.reroll_pool = [
                self._canonicalize_known_title(str(title).strip())
                for title in reroll_pool
                if str(title).strip()
            ]

        goal_raw = str(slot_data.get("goal") or "grand_goal").strip().lower()
        self.state.goal = goal_raw if goal_raw in ("grand_goal", "realm_master") else "grand_goal"
        self.state.topic_portals = bool(slot_data.get("topic_portals", False))
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
        self.state.bingo_cards_start = int(slot_data.get("bingo_cards_start", 0) or 0)
        self.state.bingo_stamps_used = 0
        self.state.back_depth_start = int(slot_data.get("back_depth_start", 0) or 0)
        if "target_rerolls_start" in slot_data:
            self.state.target_rerolls_start = max(0, int(slot_data.get("target_rerolls_start") or 0))
        else:
            self.state.target_rerolls_start = TARGET_REROLLS_PER_ROUND
        # Counters come back from the stored progress when they next sync; Rerolls and Backs wait for its Get reply.
        self.state.backs_used = 0
        self.state.backs_round = ""
        self.state.target_rerolls_used = 0
        self.state.target_rerolls_round = ""
        self.state.progress_storage_ready = False

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

        location_ids = slot_data.get("location_ids", {})
        self.state.location_round_ids = [int(v) for v in location_ids.get("rounds", [])]
        grand_goal = location_ids.get("grand_goal")
        self.state.location_grand_goal = int(grand_goal) if grand_goal is not None else None
        branch_ids_raw = location_ids.get("branches") if isinstance(location_ids, dict) else None
        branch_loc_ids: list[list[int]] = []
        if isinstance(branch_ids_raw, list):
            for group in branch_ids_raw:
                if not isinstance(group, list):
                    continue
                parsed_ids: list[int] = []
                for value in group:
                    try:
                        parsed_ids.append(int(value))
                    except Exception:
                        continue
                branch_loc_ids.append(parsed_ids)
        self.state.location_branch_ids = branch_loc_ids
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

        # Same seed and slot as before a dropped connection: put the rerolled targets back on the rounds just
        # reloaded from slot_data. The stored copy is merged in when its Get reply arrives.
        owner = f"{self._room_seed}:{self.state.team}:{self.state.slot}"
        if owner != self.state.progress_owner:
            self.state.progress_owner = owner
            self.state.progress_entries = {}
        for key, entry in list(self.state.progress_entries.items()):
            if entry.get("target"):
                self._apply_stored_target(key, entry["target"])

        checked_locations = packet.get("checked_locations", [])
        if isinstance(checked_locations, list):
            restored_checked: set[int] = set()
            for loc in checked_locations:
                try:
                    restored_checked.add(int(loc))
                except Exception:
                    pass
            self.state.checked_locations = restored_checked
            self._sync_progress_from_checked(assume_goal_already_sent=True)

        self._rebuild_bingo_stamps_from_checked()

        # Fresh connect to this slot: resume only within-slot last_page, else round start.
        if not self.state.last_page:
            self.state.last_page = self.state.current_start()

    def _sync_progress_from_checked(self, *, assume_goal_already_sent: bool = False) -> None:
        """Derive round/branch/goal HUD progress from Archipelago checked_locations."""
        checked = self.state.checked_locations
        restored_round_index = 0
        for round_loc in self.state.location_round_ids:
            if round_loc in checked:
                restored_round_index += 1
            else:
                break
        self.state.round_index = min(restored_round_index, self.state.check_count)
        self.state.sync_target_reroll_counter()
        self.state.sync_back_counter()

        for bid, loc_ids in enumerate(self.state.location_branch_ids):
            restored_branch_index = 0
            for loc_id in loc_ids:
                if loc_id in checked:
                    restored_branch_index += 1
                else:
                    break
            self.state.branch_round_index[bid] = restored_branch_index

        if self.state.location_grand_goal and self.state.location_grand_goal in checked:
            self.state.boss_completed = True
            if assume_goal_already_sent:
                self.state.goal_status_sent = True
        if self.state.realm_master_met():
            # Realm Master: no goal location; completion is "every Realm's last round checked".
            self.state.boss_completed = True
            if assume_goal_already_sent:
                self.state.goal_status_sent = True

    async def _apply_room_update(self, packet: dict[str, Any]) -> None:
        """Keep the slot HUD in sync when the room checks locations (Release / !release)."""
        locations = packet.get("checked_locations")
        if not isinstance(locations, list) or not locations:
            return
        added = False
        for loc in locations:
            try:
                loc_id = int(loc)
            except Exception:
                continue
            if loc_id not in self.state.checked_locations:
                self.state.checked_locations.add(loc_id)
                added = True
        if not added:
            return
        self._sync_progress_from_checked()
        self._rebuild_bingo_stamps_from_checked()
        await self.ensure_goal_status_if_complete()

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
        if self.state.trap_type == 3:
            return trap_name == "Wrong Wiki"
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
        if self.state.practice:
            return await self._apply_practice_bingo_visit(page_title)
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
            extra = {"pair": pair} if pair else None
            await self._append_travel_event("bingo_cell", page_title, extra=extra)
        return events

    async def _apply_practice_bingo_visit(self, page_title: str) -> list[dict[str, Any]]:
        """Practice: stamp the page's pair and report newly finished lines. Nothing is sent to AP."""
        wiki_lang = (self.state.wikipedia_language or "en").strip().lower() or "en"
        pair = letter_pair_from_title(page_title, wiki_lang)
        if not pair or not self._stamp_pair_on_unlocked_boards(pair):
            return []
        events: list[dict[str, Any]] = []
        for board_key in self.state.unlocked_bingo_board_keys():
            done = self.state.practice_bingo_lines.setdefault(board_key, set())
            for key in self.state.bingo_completed_line_keys_for_board(board_key):
                if key in done:
                    continue
                done.add(key)
                events.append({
                    "board": board_key,
                    "key": key,
                    "label": self._bingo_line_label(key, board_key),
                    "sent_text": "",
                })
        await self._append_travel_event("bingo_cell", page_title, extra={"pair": pair})
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

    def _clicks_storage_key(self) -> str:
        return f"wikipelago_clicks_{self.state.team}_{self.state.slot}"

    def _travel_storage_key(self) -> str:
        # 1.0 saves: one dict replaced on every click. Still read so older journeys carry over.
        return f"wikipelago_travel_{self.state.team}_{self.state.slot}"

    def _travel_events_key(self) -> str:
        return f"wikipelago_travel_events_{self.state.team}_{self.state.slot}"

    def _travel_visits_key(self) -> str:
        return f"wikipelago_travel_visits_{self.state.team}_{self.state.slot}"

    def _progress_storage_key(self) -> str:
        return f"wikipelago_progress_{self.state.team}_{self.state.slot}"

    def _resolve_retrieved(self, packet: dict[str, Any]) -> None:
        keys = packet.get("keys")
        if not isinstance(keys, dict):
            return
        bingo_key = self._bingo_storage_key()
        clicks_key = self._clicks_storage_key()
        progress_key = self._progress_storage_key()
        travel_keys = (self._travel_storage_key(), self._travel_events_key(), self._travel_visits_key())
        if progress_key in keys:
            asyncio.create_task(self._apply_progress_storage_payload(keys.get(progress_key), self.state.progress_owner))
        if bingo_key in keys:
            asyncio.create_task(self._apply_bingo_storage_payload(keys.get(bingo_key), source="Retrieved"))
        if clicks_key in keys:
            asyncio.create_task(self._apply_clicks_storage_payload(keys.get(clicks_key), source="Retrieved"))
        if any(key in keys for key in travel_keys):
            asyncio.create_task(self._apply_travel_retrieved(*(keys.get(key) for key in travel_keys)))

    def _resolve_set_reply(self, packet: dict[str, Any]) -> None:
        key = packet.get("key")
        raw = packet.get("value")
        if key == self._bingo_storage_key():
            asyncio.create_task(self._apply_bingo_storage_payload(raw, source="SetReply"))
        elif key == self._clicks_storage_key():
            asyncio.create_task(self._apply_clicks_storage_payload(raw, source="SetReply"))
        elif key == self._progress_storage_key():
            asyncio.create_task(self._apply_progress_storage_payload(raw, self.state.progress_owner))

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

    def _remember_page(self, page_title: str) -> None:
        title = str(page_title or "").strip()
        if not title:
            return
        self.state.last_page = title

    def _travel_event_key(self, event: dict[str, Any]) -> tuple[Any, ...]:
        return (
            event.get("t"),
            str(event.get("kind") or ""),
            str(event.get("title") or ""),
            str(event.get("path") or ""),
        )

    def _parse_clicks_storage_payload(self, raw: Any) -> int:
        if isinstance(raw, dict):
            try:
                return max(0, int(raw.get("clicks_used") or 0))
            except Exception:
                return 0
        if isinstance(raw, (int, float)):
            try:
                return max(0, int(raw))
            except Exception:
                return 0
        return 0

    def _parse_travel_storage_payload(self, raw: Any) -> tuple[list[dict[str, Any]], dict[str, int]]:
        if not isinstance(raw, dict):
            return [], {}
        events_raw = raw.get("events")
        events: list[dict[str, Any]] = []
        if isinstance(events_raw, list):
            for item in events_raw:
                if isinstance(item, dict) and item.get("kind"):
                    events.append(item)
        visits_raw = raw.get("visit_counts")
        visits: dict[str, int] = {}
        if isinstance(visits_raw, dict):
            for title, count in visits_raw.items():
                try:
                    visits[str(title)] = max(0, int(count))
                except Exception:
                    continue
        return events, visits

    def _merge_travel_state(self, events: list[dict[str, Any]], visits: dict[str, int]) -> None:
        seen = {
            self._travel_event_key(item): item
            for item in self.state.travel_events
            if isinstance(item, dict)
        }
        for item in events:
            if isinstance(item, dict) and item.get("kind"):
                seen[self._travel_event_key(item)] = item
        merged = sorted(seen.values(), key=lambda item: float(item.get("t") or 0))
        if len(merged) > MAX_TRAVEL_EVENTS:
            merged = merged[-MAX_TRAVEL_EVENTS:]
        self.state.travel_events = merged
        for title, count in visits.items():
            key = str(title)
            self.state.visit_counts[key] = max(int(self.state.visit_counts.get(key, 0) or 0), int(count))

    async def _request_clicks_from_storage(self) -> None:
        if self.ws is None or not self.state.connected_to_ap or self.state.practice:
            return
        self.state.clicks_storage_ready = False
        key = self._clicks_storage_key()
        payload = [
            {"cmd": "SetNotify", "keys": [key]},
            {"cmd": "Get", "keys": [key]},
        ]
        try:
            async with self.send_lock:
                await self.ws.send(json.dumps(payload))
        except Exception as exc:
            LOG.info("Clicks DataStorage Get/SetNotify request failed: %s", exc)

    async def _apply_clicks_storage_payload(self, raw: Any, *, source: str = "") -> None:
        if self.state.practice:
            self.state.clicks_storage_ready = True
            return
        remote = self._parse_clicks_storage_payload(raw)
        self.state.merge_clicks(remote)
        self.state.clicks_storage_ready = True
        if self.state.clicks_used > remote:
            await self._persist_clicks(force=True)

    async def _persist_clicks(self, *, force: bool = False) -> None:
        if self.state.practice or self.ws is None or not self.state.connected_to_ap:
            return
        if not force and not self.state.clicks_storage_ready:
            return
        key = self._clicks_storage_key()
        value = {"clicks_used": max(0, int(self.state.clicks_used or 0))}
        if not force and value["clicks_used"] == self._clicks_persisted:
            return
        self._clicks_persisted = value["clicks_used"]
        payload = [{
            "cmd": "Set",
            "key": key,
            "default": {"clicks_used": 0},
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
            LOG.info("Clicks DataStorage Set failed for %s: %s", key, exc)

    async def _request_travel_from_storage(self) -> None:
        if self.ws is None or not self.state.connected_to_ap or self.state.practice:
            return
        self.state.travel_storage_ready = False
        # Get only: a SetNotify subscription would send the whole journey back after every click.
        payload = [{
            "cmd": "Get",
            "keys": [self._travel_storage_key(), self._travel_events_key(), self._travel_visits_key()],
        }]
        try:
            async with self.send_lock:
                await self.ws.send(json.dumps(payload))
        except Exception as exc:
            LOG.info("Travel DataStorage Get request failed: %s", exc)

    async def _apply_travel_retrieved(self, legacy: Any, events_raw: Any, visits_raw: Any) -> None:
        if self.state.practice:
            self.state.travel_storage_ready = True
            return
        legacy_events, legacy_visits = self._parse_travel_storage_payload(legacy)
        stored_events, stored_visits = self._parse_travel_storage_payload(
            {"events": events_raw, "visit_counts": visits_raw}
        )
        self._merge_travel_state(legacy_events, legacy_visits)
        self._merge_travel_state(stored_events, stored_visits)
        self.state.travel_storage_ready = True
        self._travel_stored_len = len(stored_events)
        stored_keys = {self._travel_event_key(item) for item in stored_events}
        merged_keys = {self._travel_event_key(item) for item in self.state.travel_events if isinstance(item, dict)}
        visits_behind = any(
            int(count or 0) > int(stored_visits.get(title, 0) or 0)
            for title, count in self.state.visit_counts.items()
        )
        if merged_keys != stored_keys or len(stored_events) != len(merged_keys) or visits_behind:
            # A 1.0 save seen for the first time, or steps taken while the room was unreachable.
            await self._persist_travel()

    async def _persist_travel(self) -> None:
        """Rewrite the whole journey. Clicks only send their new step (_send_travel_step)."""
        if self.state.practice or self.ws is None or not self.state.connected_to_ap:
            return
        if not self.state.travel_storage_ready:
            return
        payload = [
            {
                "cmd": "Set",
                "key": self._travel_events_key(),
                "default": [],
                "operations": [{"operation": "replace", "value": list(self.state.travel_events)}],
            },
            {
                "cmd": "Set",
                "key": self._travel_visits_key(),
                "default": {},
                "operations": [{"operation": "replace", "value": dict(self.state.visit_counts)}],
            },
        ]
        try:
            async with self.send_lock:
                await self.ws.send(json.dumps(payload))
            self._travel_stored_len = len(self.state.travel_events)
        except Exception as exc:
            LOG.info("Travel DataStorage Set failed: %s", exc)

    async def _send_travel_step(self, event: dict[str, Any], visited: str) -> None:
        """Append one step to the stored journey instead of resending all of it."""
        if self.state.practice or self.ws is None or not self.state.connected_to_ap:
            return
        if not self.state.travel_storage_ready:
            # The Get reply merges this step in and rewrites the journey.
            return
        if self._travel_stored_len >= MAX_TRAVEL_EVENTS + TRAVEL_TRIM_SLACK:
            # "add" only grows the stored list; now and then rewrite it trimmed to the local window.
            await self._persist_travel()
            return
        payload = [{
            "cmd": "Set",
            "key": self._travel_events_key(),
            "default": [],
            "operations": [{"operation": "add", "value": [event]}],
        }]
        if visited:
            payload.append({
                "cmd": "Set",
                "key": self._travel_visits_key(),
                "default": {},
                "operations": [{"operation": "update", "value": {visited: self.state.visit_counts.get(visited, 0)}}],
            })
        try:
            async with self.send_lock:
                await self.ws.send(json.dumps(payload))
            self._travel_stored_len += 1
        except Exception as exc:
            LOG.info("Travel DataStorage step failed: %s", exc)

    def _progress_round_pairs(self, key: str) -> tuple[list[dict[str, Any]], int, dict[str, Any] | None] | None:
        """(pairs, index, Realm or None) of the round a stored progress key names: "main:3" or "branch:0:1"."""
        parts = key.split(":")
        try:
            numbers = [int(part) for part in parts[1:]]
        except ValueError:
            return None
        branch: dict[str, Any] | None = None
        if parts[0] == "main" and len(numbers) == 1 and key == f"main:{numbers[0]}":
            pairs: Any = self.state.round_pairs
        elif parts[0] == "branch" and len(numbers) == 2 and key == f"branch:{numbers[0]}:{numbers[1]}":
            branch = self.state.branch_by_id(numbers[0])
            pairs = (branch or {}).get("pairs")
        else:
            return None
        idx = numbers[-1]
        if not isinstance(pairs, list) or not 0 <= idx < len(pairs):
            return None
        return pairs, idx, branch

    def _parse_progress_payload(self, raw: Any) -> dict[str, dict[str, Any]]:
        """The usable entries of a stored progress value; anything that doesn't fit this seed is dropped."""
        entries: dict[str, dict[str, Any]] = {}
        if not isinstance(raw, dict):
            return entries
        for key, value in raw.items():
            key = str(key)
            if not isinstance(value, dict):
                continue
            if key == "uses":
                try:
                    uses = {
                        "round": int(value.get("round")),
                        "rerolls": max(0, int(value.get("rerolls") or 0)),
                        "backs": max(0, int(value.get("backs") or 0)),
                    }
                except (TypeError, ValueError):
                    continue
                if 0 <= uses["round"] <= self.state.check_count:
                    entries[key] = uses
                continue
            target = value.get("target")
            if not isinstance(target, str) or self._progress_round_pairs(key) is None:
                continue
            target = target.strip()
            try:
                times = max(1, int(value.get("n") or 1))
            except (TypeError, ValueError):
                times = 1
            if target and len(target) <= MAX_TITLE_CHARS:
                entries[key] = {"target": target, "n": times}
        return entries

    @staticmethod
    def _merge_progress_entry(key: str, mine: dict[str, Any] | None, theirs: dict[str, Any] | None) -> dict[str, Any]:
        """Join two copies of one entry the same way on every device, whatever order writes arrive in:
        the most rerolled target wins (ties by title), and use counts keep the newest round's highest."""
        if not mine or not theirs:
            return dict(mine or theirs or {})
        if key != "uses":
            return dict(max(mine, theirs, key=lambda entry: (entry["n"], entry["target"])))
        if mine["round"] != theirs["round"]:
            return dict(max(mine, theirs, key=lambda uses: uses["round"]))
        return {
            "round": mine["round"],
            "rerolls": max(mine["rerolls"], theirs["rerolls"]),
            "backs": max(mine["backs"], theirs["backs"]),
        }

    def _apply_stored_target(self, key: str, title: str) -> bool:
        """Put a rerolled target from the stored progress on its round and update the reroll pools the way the
        reroll did: the new title leaves the pool, the one it replaces goes back (a Realm's into its own pool too)."""
        found = self._progress_round_pairs(key)
        if found is None:
            return False
        pairs, idx, branch = found
        state = self.state
        norm = self._norm_title
        old_target = str(pairs[idx].get("target") or "")
        if norm(old_target) == norm(title):
            return False
        pairs[idx]["target"] = title
        state.reroll_pool = [item for item in state.reroll_pool if norm(item) != norm(title)]
        if old_target and norm(old_target) != norm(state.goal_article()):
            realm_pool = (branch or {}).get("reroll_pool")
            if isinstance(realm_pool, list) and all(norm(item) != norm(old_target) for item in realm_pool):
                realm_pool.append(old_target)
            if not state.target_in_use(old_target) and all(norm(item) != norm(old_target) for item in state.reroll_pool):
                state.reroll_pool.append(old_target)
        return True

    def _remember_rerolled_target(self, key: str, title: str) -> None:
        if self.state.practice:
            return
        entry = self.state.progress_entries.get(key) or {}
        self.state.progress_entries[key] = {"target": title, "n": int(entry.get("n") or 0) + 1}

    def _record_round_uses(self) -> list[str]:
        """Copy this main round's Reroll and Back use into the stored progress; ["uses"] when that changed it."""
        state = self.state
        if state.practice:
            return []
        state.sync_target_reroll_counter()
        state.sync_back_counter()
        uses = {"round": state.round_index, "rerolls": state.target_rerolls_used, "backs": state.backs_used}
        current = state.progress_entries.get("uses")
        if current == uses or (current and current["round"] > uses["round"]):
            return []
        state.progress_entries["uses"] = uses
        return ["uses"]

    async def _request_progress_from_storage(self) -> None:
        if self.ws is None or not self.state.connected_to_ap or self.state.practice:
            return
        self.state.progress_storage_ready = False
        key = self._progress_storage_key()
        payload = [
            {"cmd": "SetNotify", "keys": [key]},
            {"cmd": "Get", "keys": [key]},
        ]
        try:
            async with self.send_lock:
                await self.ws.send(json.dumps(payload))
        except Exception as exc:
            LOG.info("Progress DataStorage Get/SetNotify request failed: %s", exc)

    async def _apply_progress_storage_payload(self, raw: Any, owner: str) -> None:
        """Merge the stored progress (Get reply, or any device's write) into this bridge's copy, put rerolled
        targets in place, and write back what storage lacks (progress made while it was unreachable, or a race)."""
        state = self.state
        if state.practice or owner != state.progress_owner:
            return
        stored = self._parse_progress_payload(raw)
        behind: list[str] = []
        moved = False
        for key in sorted(set(stored) | set(state.progress_entries)):
            mine = state.progress_entries.get(key)
            merged = self._merge_progress_entry(key, mine, stored.get(key))
            if merged != mine:
                state.progress_entries[key] = merged
                if merged.get("target") and merged.get("target") != (mine or {}).get("target"):
                    moved = self._apply_stored_target(key, merged["target"]) or moved
            if merged != stored.get(key):
                behind.append(key)
        state.progress_storage_ready = True
        state.sync_target_reroll_counter()
        state.sync_back_counter()
        state.target_rerolls_used = max(state.target_rerolls_used, state.stored_round_uses("rerolls"))
        state.backs_used = max(state.backs_used, state.stored_round_uses("backs"))
        if behind:
            await self._persist_progress(behind)
        if moved:
            # Another device rerolled: the new targets have no Compass history yet.
            self._schedule_compass(state.last_page)

    async def _persist_progress(self, keys: list[str]) -> None:
        """Write these entries of the stored progress. "update" replaces only the keys sent, so devices writing
        different rounds can't overwrite each other's."""
        state = self.state
        if state.practice or self.ws is None or not state.connected_to_ap:
            return
        # Writing before the Get reply was merged would replace what other devices stored.
        if not state.progress_storage_ready:
            return
        value = {key: state.progress_entries[key] for key in keys if key in state.progress_entries}
        if not value:
            return
        key = self._progress_storage_key()
        payload = [{
            "cmd": "Set",
            "key": key,
            "default": {},
            "want_reply": True,
            "operations": [{"operation": "update", "value": value}],
        }]
        try:
            async with self.send_lock:
                await self.ws.send(json.dumps(payload))
        except Exception as exc:
            LOG.info("Progress DataStorage Set failed for %s: %s", key, exc)

    async def _append_travel_event(
        self,
        kind: str,
        title: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        event: dict[str, Any] = {
            "t": int(time.time() * 1000),
            "kind": str(kind or "").strip() or "nav",
            "title": str(title or "").strip(),
            "path": str((extra or {}).get("path") or "main"),
        }
        if extra:
            event["extra"] = extra
        self.state.travel_events.append(event)
        if len(self.state.travel_events) > MAX_TRAVEL_EVENTS:
            self.state.travel_events = self.state.travel_events[-MAX_TRAVEL_EVENTS:]
        visited = ""
        if event["kind"] == "nav" and event["title"]:
            key = event["title"]
            if key in self.state.visit_counts or len(self.state.visit_counts) < MAX_TRAVEL_EVENTS:
                self.state.visit_counts[key] = int(self.state.visit_counts.get(key, 0) or 0) + 1
                visited = key
        await self._send_travel_step(event, visited)

    def _set_active_pair_target(self, new_target: str) -> bool:
        title = str(new_target or "").strip()
        if not title:
            return False
        idx = self.state.round_index
        if idx < 0 or idx >= len(self.state.round_pairs):
            return False
        self.state.round_pairs[idx]["target"] = title
        return True

    def _set_branch_pair_target(self, branch_id: int, new_target: str) -> bool:
        title = str(new_target or "").strip()
        if not title:
            return False
        pairs = self.state.branch_pairs(branch_id)
        try:
            idx = int(self.state.branch_round_index.get(int(branch_id), 0) or 0)
        except Exception:
            idx = 0
        if idx < 0 or idx >= len(pairs):
            return False
        pairs[idx]["target"] = title
        return True

    def _branch_location_ids(self, branch_id: int) -> list[int]:
        try:
            bid = int(branch_id)
        except Exception:
            return []
        if bid < 0 or bid >= len(self.state.location_branch_ids):
            return []
        return list(self.state.location_branch_ids[bid] or [])

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
        await self._append_travel_event(
            "bingo_stamp",
            self.state.last_page or pair,
            extra={"board": board_key, "pair": pair},
        )
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
        cached = cache_get(self.resolved_title_cache, norm)
        if cached:
            return cached

        canonical = self._canonicalize_known_title(title)
        try:
            resolved = self._fetch_resolved_title(canonical)
        except Exception:
            resolved = canonical

        cache_put(self.resolved_title_cache, norm, resolved, TITLE_CACHE_SIZE)
        cache_put(self.resolved_title_cache, normalize_title(resolved), resolved, TITLE_CACHE_SIZE)
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
        cached = cache_get(self.link_cache, norm)
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

            payload = self._wiki_api_json(params)
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

        cache_put(self.link_cache, norm, links, LINK_CACHE_SIZE)
        return links

    def _wikipedia_api_root(self) -> str:
        lang = wiki_language(self.state.wikipedia_language) or "en"
        return f"https://{lang}.wikipedia.org"

    def _wiki_api_json(self, params: dict[str, str]) -> dict[str, Any]:
        url = f"{self._wikipedia_api_root()}/w/api.php?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": WIKI_USER_AGENT,
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=8) as response:
            body = response.read(WIKI_MAX_RESPONSE_BYTES + 1)
        if len(body) > WIKI_MAX_RESPONSE_BYTES:
            raise ValueError("Wikipedia response too large")
        payload = json.loads(body.decode("utf-8"))
        return payload if isinstance(payload, dict) else {}

    def _fetch_backlinks(self, title: str) -> tuple[set[str], set[str]]:
        """(articles linking to `title`, redirects to `title`), capped for very popular pages."""
        norm = normalize_title(title)
        cached = cache_get(self.backlink_cache, norm)
        if cached is not None:
            return cached

        backlinks: set[str] = set()
        redirects: set[str] = set()
        blcontinue: str | None = None
        for _ in range(COMPASS_BACKLINK_PAGES):
            params: dict[str, str] = {
                "action": "query",
                "list": "backlinks",
                "bltitle": title,
                "blnamespace": "0",
                "blredirect": "1",
                "bllimit": "max",
                "format": "json",
            }
            if blcontinue:
                params["blcontinue"] = blcontinue

            payload = self._wiki_api_json(params)
            for entry in payload.get("query", {}).get("backlinks", []):
                entry_title = str(entry.get("title", "")).strip()
                if entry_title:
                    (redirects if "redirect" in entry else backlinks).add(normalize_title(entry_title))
                for sub in entry.get("redirlinks", []) or []:
                    sub_title = str(sub.get("title", "")).strip()
                    if sub_title:
                        backlinks.add(normalize_title(sub_title))

            blcontinue = payload.get("continue", {}).get("blcontinue")
            if not blcontinue:
                break

        cache_put(self.backlink_cache, norm, (backlinks, redirects), BACKLINK_CACHE_SIZE)
        return backlinks, redirects

    def _compass_reading(self, page_title: str, page_links: set[str], target_title: str) -> tuple[int, int]:
        """(level, overlap) of a page against one target. Level 0: on it; 1: linked from the page;
        2: two clicks away; 3: farther. Overlap counts the page's links into the target's
        neighbourhood (pages linking to it or linked from it); higher is closer."""
        target_norm = normalize_title(target_title)
        if normalize_title(page_title) == target_norm:
            return (0, 0)
        backlinks, redirects = self._fetch_backlinks(target_title)
        if target_norm in page_links or page_links & redirects:
            return (1, 0)
        target_links = self._fetch_page_links(target_title)
        overlap = len(page_links & (backlinks | target_links))
        return (2 if page_links & backlinks else 3, overlap)


    def _fetch_resolved_title(self, title: str) -> str:
        params = {
            "action": "query",
            "titles": title,
            "redirects": "1",
            "format": "json",
        }
        payload = self._wiki_api_json(params)
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

        # Cached (callers have usually just canonicalised both titles), so a click with several live targets
        # doesn't ask Wikipedia about the same two pages again for each one.
        try:
            resolved_page = await self._canonicalize_title(page_title)
            resolved_target = await self._canonicalize_title(target_title)
            return normalize_title(resolved_page) == normalize_title(resolved_target)
        except Exception:
            return False

    def _schedule_compass(self, page_title: str) -> None:
        """Refresh the Wiki Compass in the background so checks never wait on Wikipedia;
        the status poll picks the new hint up."""
        if not page_title or not self.state.is_playable():
            return
        self._compass_seq += 1
        task = asyncio.create_task(self._update_compass(page_title, self._compass_seq))
        self._compass_tasks.add(task)
        task.add_done_callback(self._compass_tasks.discard)

    async def _update_compass(self, page_title: str, seq: int) -> None:
        state = self.state
        if not state.has_item("Wiki Compass"):
            state.reset_compass()
            return
        targets = state.compass_targets()
        if not targets:
            state.warmer_colder = None
            state.compass_target = None
            return

        readings: list[tuple[dict[str, Any], tuple[int, int]]] = []
        try:
            page = await self._canonicalize_title(page_title)
            page_links = await asyncio.to_thread(self._fetch_page_links, page)
        except Exception:
            page_links = None
        if page_links is not None:
            for target in targets:
                try:
                    reading = await asyncio.to_thread(self._compass_reading, page, page_links, target["title"])
                except Exception:
                    continue
                readings.append((target, reading))

        if seq != self._compass_seq:
            return  # The player already moved on; the newer reading wins.
        if not readings:
            state.warmer_colder = "No signal"
            return

        # Point at the nearest live target, compared with that target's own previous reading.
        target, reading = min(readings, key=lambda item: (item[1][0], -item[1][1]))
        state.warmer_colder = compass_hint(state.compass_memory.get(normalize_title(target["title"])), reading)
        state.compass_target = target
        state.compass_memory = {normalize_title(t["title"]): r for t, r in readings}

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
                "hits": [],
                "status": self.state.to_status(),
                "next_target": self.state.current_target(),
            }

        self.state.merge_clicks(clicks_used)
        await self._persist_clicks()
        # Two checks can run at once (a double-click on a link). Remember which round this one is
        # about, so only the first can complete it and the second can't also complete the next.
        main_index = self.state.round_index
        raw_target = self.state.current_target()
        page_title = await self._canonicalize_title(page_title)
        self._remember_page(page_title)

        if raw_target:
            target = await self._canonicalize_title(raw_target)
            if self.state.round_index == main_index:
                self._set_active_pair_target(target)
            matched_main = await self._titles_match(page_title, target)
            if self.state.round_index != main_index or self.state.current_target() != target:
                matched_main = False
        else:
            # Realm Master after the last main round: only Realm targets remain.
            target = ""
            matched_main = False

        result: dict[str, Any] = {
            "matched": matched_main,
            "target": target,
            "advanced": False,
            "locked": False,
            "boss_completed": self.state.boss_completed,
            "hits": [],
        }

        if self.state.practice:
            hits: list[dict[str, Any]] = []
            if matched_main:
                # Chain like AP: keep the player on the cleared target; only roll a new target.
                # Roll before awaiting anything, so a concurrent check no longer matches the old target.
                self._roll_practice_race(continue_from=page_title)
                await self._append_travel_event("round_complete", page_title, extra={"path": "main"})
                result["advanced"] = True
                result["practice_rolled"] = True
                hits.append({"kind": "main", "target": target})
            for bid in list(self.state.unlocked_branch_ids()):
                raw_branch_target = self.state.branch_current_target(bid)
                if not raw_branch_target:
                    continue
                branch_target = await self._canonicalize_title(raw_branch_target)
                if not await self._titles_match(page_title, branch_target):
                    continue
                if self.state.branch_current_target(bid) != raw_branch_target:
                    continue
                idx = int(self.state.branch_round_index.get(bid, 0) or 0)
                self.state.branch_round_index[bid] = idx + 1
                branch = self.state.branch_by_id(bid) or {}
                hits.append({
                    "kind": "branch",
                    "branch_id": bid,
                    "fork": bid + 1,
                    "target": branch_target,
                    "round": idx + 1,
                    "theme_tag": str(branch.get("theme_tag") or ""),
                })
                result["advanced"] = True
                await self._append_travel_event("round_complete", page_title, extra={"path": f"branch:{bid}"})
            result["hits"] = hits
            result["matched"] = bool(hits)
            self._schedule_compass(page_title)
            result["status"] = self.state.to_status()
            result["next_target"] = self.state.current_target()
            return result

        sent_bits: list[str] = []
        hits: list[dict[str, Any]] = []

        if matched_main and self.state.round_index < self.state.check_count and self.state.location_round_ids:
            round_number = self.state.round_index + 1
            if round_number > self.state.unlocked_rounds():
                result["locked"] = True
            else:
                round_id = self.state.location_round_ids[main_index]
                # Claim the round before awaiting, so a concurrent check sees it as done.
                self.state.round_index = main_index + 1
                try:
                    scouted = await self.scout_locations([round_id])
                    await self.send_location_checks([round_id])
                except Exception:
                    if self.state.round_index == main_index + 1:
                        self.state.round_index = main_index
                    raise
                self.state.sync_target_reroll_counter()
                self.state.sync_back_counter()
                result["advanced"] = True
                hit: dict[str, Any] = {"kind": "main", "target": target, "round": round_number}
                network_item = scouted.get(round_id)
                if network_item:
                    sent_text = self._format_send_text(network_item)
                    if sent_text:
                        hit["sent_text"] = sent_text
                        sent_bits.append(sent_text)
                hits.append(hit)
                await self._append_travel_event("round_complete", page_title, extra={"path": "main"})

        for bid in list(self.state.unlocked_branch_ids()):
            loc_ids = self._branch_location_ids(bid)
            idx = int(self.state.branch_round_index.get(bid, 0) or 0)
            if idx < 0 or idx >= len(loc_ids):
                continue
            branch_target = await self._canonicalize_title(self.state.branch_current_target(bid))
            if not branch_target or not await self._titles_match(page_title, branch_target):
                continue
            if int(self.state.branch_round_index.get(bid, 0) or 0) != idx:
                continue  # a concurrent check already completed this Realm round
            loc_id = loc_ids[idx]
            self.state.branch_round_index[bid] = idx + 1
            try:
                scouted = await self.scout_locations([loc_id])
                await self.send_location_checks([loc_id])
            except Exception:
                if self.state.branch_round_index.get(bid) == idx + 1:
                    self.state.branch_round_index[bid] = idx
                raise
            result["advanced"] = True
            result["matched"] = True
            hit = {
                "kind": "branch",
                "branch_id": bid,
                "fork": bid + 1,
                "target": branch_target,
                "round": idx + 1,
            }
            branch = self.state.branch_by_id(bid)
            if branch:
                hit["theme_tag"] = str(branch.get("theme_tag") or "")
            network_item = scouted.get(loc_id)
            if network_item:
                sent_text = self._format_send_text(network_item)
                if sent_text:
                    hit["sent_text"] = sent_text
                    sent_bits.append(sent_text)
            hits.append(hit)
            await self._append_travel_event(
                "round_complete",
                page_title,
                extra={"path": f"branch:{bid}"},
            )

        if sent_bits:
            result["sent_text"] = sent_bits[-1]
        result["hits"] = hits
        result["matched"] = bool(hits)

        await self.try_finish_boss()
        await self.ensure_goal_status_if_complete()
        # After any round advance, so a new target starts at "Calibrating" instead of reusing old readings.
        self._schedule_compass(page_title)
        result["status"] = self.state.to_status()
        result["next_target"] = self.state.current_target()
        return result

    async def reroll_target(self) -> dict[str, Any]:
        self.state.last_seen = time.time()
        self.state.sync_target_reroll_counter()

        if not self.state.is_playable():
            return {"ok": False, "error": "not connected", "status": self.state.to_status()}
        if not self.state.progress_ready():
            return {"ok": False, "error": "progress not loaded yet", "status": self.state.to_status()}
        if self.state.boss_completed:
            return {"ok": False, "error": "seed already complete", "status": self.state.to_status()}
        slots = self.state.rerollable_target_slots()
        if not slots:
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
        blocked = {_norm(start), _norm(self.state.goal_article())}
        for pair in self.state.round_pairs:
            blocked.add(_norm(pair.get("target", "")))
        for branch in self.state.branches:
            for pair in (branch.get("pairs") or []):
                if isinstance(pair, dict):
                    blocked.add(_norm(pair.get("target", "")))

        pool = list(self.state.reroll_pool)

        async def _pick(blocked_titles: set[str], only: set[str] | None = None) -> tuple[str, str] | None:
            candidates = [
                title for title in pool
                if _norm(title) not in blocked_titles and (only is None or _norm(title) in only)
            ]
            if not candidates:
                return None
            picked = random.choice(candidates)
            resolved = await self._canonicalize_title(picked)
            if resolved and _norm(resolved) not in blocked_titles:
                return picked, resolved
            random.shuffle(candidates)
            for candidate in candidates[:12]:
                resolved = await self._canonicalize_title(candidate)
                if resolved and _norm(resolved) not in blocked_titles:
                    return candidate, resolved
            return None

        picks: list[tuple[dict[str, Any], str, str]] = []
        for slot in slots:
            realm_titles: set[str] | None = None
            if slot.get("kind") == "branch":
                realm = self.state.branch_by_id(int(slot.get("branch_id") or 0)) or {}
                realm_pool = realm.get("reroll_pool")
                if isinstance(realm_pool, list) and realm_pool:
                    realm_titles = {_norm(title) for title in realm_pool}
            chosen = await _pick(blocked, realm_titles) if realm_titles else None
            if not chosen:
                # Off-topic fallback once a Realm's own slice runs dry.
                chosen = await _pick(blocked)
            if not chosen:
                return {
                    "ok": False,
                    "error": "no alternate targets left in the seed pool",
                    "status": self.state.to_status(),
                }
            picked, new_target = chosen
            picks.append((slot, picked, new_target))
            blocked.add(_norm(picked))
            blocked.add(_norm(new_target))
            pool = [title for title in pool if _norm(title) != _norm(picked)]

        changes: list[dict[str, Any]] = []
        recycled: list[str] = []
        stored_keys: list[str] = []
        for slot, picked, new_target in picks:
            old_target = str(slot.get("old_target") or "")
            if slot.get("kind") == "branch":
                bid = int(slot.get("branch_id") or 0)
                if not self._set_branch_pair_target(bid, new_target):
                    return {"ok": False, "error": "no active branch round", "status": self.state.to_status()}
                stored_keys.append(f"branch:{bid}:{int(self.state.branch_round_index.get(bid, 0) or 0)}")
            else:
                if not self._set_active_pair_target(new_target):
                    return {"ok": False, "error": "no active round", "status": self.state.to_status()}
                stored_keys.append(f"main:{self.state.round_index}")
            self._remember_rerolled_target(stored_keys[-1], new_target)
            change = {
                "kind": str(slot.get("kind") or "main"),
                "old_target": old_target,
                "new_target": new_target,
            }
            if slot.get("kind") == "branch":
                change["branch_id"] = int(slot.get("branch_id") or 0)
                change["fork"] = int(slot.get("fork") or 0)
            changes.append(change)
            if old_target and _norm(old_target) != _norm(self.state.goal_article()):
                recycled.append(old_target)
                if slot.get("kind") == "branch":
                    realm = self.state.branch_by_id(int(slot.get("branch_id") or 0)) or {}
                    realm_pool = realm.get("reroll_pool")
                    if isinstance(realm_pool, list) and all(_norm(t) != _norm(old_target) for t in realm_pool):
                        realm_pool.append(old_target)

        for old_target in recycled:
            if self.state.target_in_use(old_target):
                continue
            if all(_norm(title) != _norm(old_target) for title in pool):
                pool.append(old_target)

        self.state.reroll_pool = pool
        self.state.target_rerolls_used += 1
        if not self.state.practice:
            await self._persist_progress(stored_keys + self._record_round_uses())
        # New targets have no Compass history yet: recalibrate on the page the player is on.
        self._schedule_compass(self.state.last_page)

        main_change = next((item for item in changes if item.get("kind") == "main"), None)
        first = main_change or (changes[0] if changes else {})
        return {
            "ok": True,
            "rerolled": True,
            "changes": changes,
            "old_target": first.get("old_target") or "",
            "new_target": first.get("new_target") or "",
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
        if not self.state.progress_ready():
            return {"ok": False, "error": "progress not loaded yet", "status": self.state.to_status()}
        if not self.state.can_go_back():
            return {
                "ok": False,
                "error": f"no backs left this round ({self.state.back_depth_max()} max)",
                "status": self.state.to_status(),
            }

        self.state.backs_used += 1
        await self._persist_progress(self._record_round_uses())
        await self._append_travel_event("back", self.state.last_page)
        return {
            "ok": True,
            "used_back": True,
            "backs_used": self.state.backs_used,
            "backs_remaining": self.state.backs_remaining(),
            "back_depth_max": self.state.back_depth_max(),
            "status": self.state.to_status(),
        }

    def _norm_title(self, title: str) -> str:
        return str(title or "").replace("_", " ").strip().casefold()

    def _seed_pool_titles(self) -> list[str]:
        titles: list[str] = []
        seen: set[str] = set()

        def add(title: Any) -> None:
            text = str(title or "").replace("_", " ").strip()
            if not text:
                return
            key = text.casefold()
            if key in seen:
                return
            seen.add(key)
            titles.append(text)

        for pair in self.state.round_pairs:
            if isinstance(pair, dict):
                add(pair.get("start"))
                add(pair.get("target"))
        for title in self.state.reroll_pool:
            add(title)
        if self.state.practice:
            for title in self.state.practice_pool_titles:
                add(title)
        for branch in self.state.branches:
            for pair in (branch.get("pairs") or []):
                if isinstance(pair, dict):
                    add(pair.get("start"))
                    add(pair.get("target"))
        add(self.state.goal_article())
        return titles

    def _current_block_titles(self) -> set[str]:
        blocked = {self._norm_title(self.state.last_page)}
        target = self.state.current_target()
        if target:
            blocked.add(self._norm_title(target))
        for item in self.state.live_branch_targets():
            if isinstance(item, dict):
                blocked.add(self._norm_title(item.get("target")))
        return {title for title in blocked if title}

    async def teleport_random_page(self) -> dict[str, Any]:
        """Move last_page to a random seed article. No checks, bingo, or scoring."""
        self.state.last_seen = time.time()
        if not self.state.is_playable():
            return {"ok": False, "error": "not connected", "status": self.state.to_status()}

        remaining = self.state.teleport_cooldown_remaining()
        if remaining > 0:
            return {
                "ok": False,
                "error": f"teleport cooling down ({remaining}s left)",
                "cooldown_remaining": remaining,
                "status": self.state.to_status(),
            }

        blocked = self._current_block_titles()
        pool = [title for title in self._seed_pool_titles() if self._norm_title(title) not in blocked]
        if not pool:
            return {
                "ok": False,
                "error": "no alternate pages left in the seed pool",
                "status": self.state.to_status(),
            }

        random.shuffle(pool)
        resolved = ""
        for candidate in pool[:24]:
            resolved_title = await self._canonicalize_title(candidate)
            if resolved_title and self._norm_title(resolved_title) not in blocked:
                resolved = resolved_title
                break
        if not resolved:
            return {
                "ok": False,
                "error": "no alternate pages left in the seed pool",
                "status": self.state.to_status(),
            }

        old_page = self.state.last_page
        self._remember_page(resolved)
        self.state.last_teleport_at = time.time()
        await self._append_travel_event("teleport", resolved)
        return {
            "ok": True,
            "teleported": True,
            "title": resolved,
            "old_page": old_page,
            "status": self.state.to_status(),
        }

    async def try_finish_boss(self) -> None:
        if self.state.boss_completed:
            return
        if self.state.is_realm_master():
            if not self.state.realm_master_met():
                return
            self.state.boss_completed = True
            await self.send_goal_status()
            await self._append_travel_event(
                "realm_master",
                self.state.last_page,
                extra={"path": "main"},
            )
            return
        if not self.state.boss_ready():
            return
        goal_title = await self._canonicalize_title(self.state.goal_article())
        self.state.goal_article_title = goal_title
        if not await self._titles_match(self.state.last_page, goal_title):
            return

        if self.state.location_grand_goal:
            await self.send_location_checks([self.state.location_grand_goal])

        self.state.boss_completed = True
        await self.send_goal_status()
        await self._append_travel_event(
            "grand_goal",
            self.state.last_page or goal_title,
            extra={"path": "main"},
        )

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

    async def _debug_complete_branch_at(self, branch_id: int, round_index: int) -> dict[str, Any]:
        loc_ids = self._branch_location_ids(branch_id)
        if round_index < 0 or round_index >= len(loc_ids):
            return {"advanced": False, "error": "no branch location for index"}
        if self.state.boss_completed:
            return {"advanced": False, "error": "seed already complete"}
        loc_id = loc_ids[round_index]
        if loc_id in self.state.checked_locations:
            current = int(self.state.branch_round_index.get(branch_id, 0) or 0)
            if current <= round_index:
                self.state.branch_round_index[branch_id] = min(round_index + 1, len(loc_ids))
                self.state.sync_target_reroll_counter()
                self.state.sync_back_counter()
            return {"advanced": False, "already_checked": True}
        scouted = await self.scout_locations([loc_id])
        await self.send_location_checks([loc_id])
        self.state.branch_round_index[branch_id] = max(
            int(self.state.branch_round_index.get(branch_id, 0) or 0),
            min(round_index + 1, len(loc_ids)),
        )
        self.state.sync_target_reroll_counter()
        self.state.sync_back_counter()
        result: dict[str, Any] = {
            "advanced": True,
            "branch_id": branch_id,
            "round_completed": round_index + 1,
        }
        network_item = scouted.get(loc_id)
        if network_item:
            sent_text = self._format_send_text(network_item)
            if sent_text:
                result["sent_text"] = sent_text
        return result

    async def debug_action(self, action: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Full AP/session debug mutators for playtesting.
        The HTTP route is only registered when WIKIPELAGO_DEBUG_MENU is set.
        """
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
                self.state.reset_compass()
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

            if action == "unlock_all_branches":
                if self.state.topic_portals:
                    for branch in self.state.branches:
                        portal = str(branch.get("portal_item") or "")
                        if portal and not self.state.has_item(portal):
                            await self._debug_grant_named(portal, unique=True, fire_trap=False)
                need = 0 if self.state.topic_portals else max(0, len(self.state.branches))
                while self.state.item_count("Branch Key") < need:
                    await self._debug_grant_named("Branch Key", unique=False, fire_trap=False)
                return {
                    "ok": True,
                    "action": action,
                    "branch_key_count": self.state.branch_key_count(),
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
                new_target = await self._canonicalize_title(title)
                if not self._set_active_pair_target(new_target):
                    return {"ok": False, "error": "no active round", "status": self.state.to_status()}
                self.state.reset_compass()
                return {
                    "ok": True,
                    "action": action,
                    "new_target": new_target,
                    "status": self.state.to_status(),
                }

            if action == "reset_rerolls":
                self.state.target_rerolls_used = 0
                self.state.target_rerolls_round = self.state.progress_key()
                await self._persist_progress(self._record_round_uses())
                return {"ok": True, "action": action, "status": self.state.to_status()}

            if action == "reset_backs":
                self.state.backs_used = 0
                self.state.backs_round = self.state.progress_key()
                await self._persist_progress(self._record_round_uses())
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
                    return {"ok": False, "error": "trap must be Foggy Links, Missing Links, or Wrong Wiki", "status": self.state.to_status()}
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

            if action == "complete_branch_rounds":
                # Advance every live Realm / branch by one round (sends real checks).
                completed: list[dict[str, Any]] = []
                for bid in list(self.state.unlocked_branch_ids()):
                    idx = int(self.state.branch_round_index.get(bid, 0) or 0)
                    result = await self._debug_complete_branch_at(bid, idx)
                    if result.get("advanced"):
                        completed.append(result)
                await self.try_finish_boss()
                await self.ensure_goal_status_if_complete()
                if not completed:
                    return {"ok": False, "error": "no live branch rounds", "status": self.state.to_status()}
                return {"ok": True, "action": action, "completed": completed, "status": self.state.to_status()}

            if action == "finish_boss":
                if self.state.is_realm_master():
                    self.state.boss_completed = True
                    await self.send_goal_status()
                    return {"ok": True, "action": action, "status": self.state.to_status()}
                self._debug_set_item_count("Knowledge Fragment", max(self.state.required_fragments, self.state.fragments()))
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
    client: str = ""


class SessionManager:
    def __init__(self):
        self.sessions: dict[str, Session] = {}

    def create(self, client: str = "") -> Session | None:
        """A new session, or None when this client or the whole server has too many active ones."""
        self._make_room(client)
        mine = sum(1 for session in self.sessions.values() if client and session.client == client)
        if len(self.sessions) >= MAX_SESSIONS or mine >= MAX_SESSIONS_PER_CLIENT:
            return None
        sid = uuid.uuid4().hex
        state = SessionState()
        session = Session(id=sid, state=state, conn=APConnection(state), client=client)
        self.sessions[sid] = session
        return session

    def _make_room(self, client: str) -> None:
        """Drop idle sessions of this client, then idle ones anywhere if the server is full."""
        now = time.time()
        idle = sorted(
            (s for s in self.sessions.values() if now - s.state.last_seen > SESSION_RECLAIM_IDLE_SECONDS),
            key=lambda s: s.state.last_seen,
        )
        mine = [s for s in self.sessions.values() if client and s.client == client]
        for session in idle:
            if not client or session.client != client or len(mine) < MAX_SESSIONS_PER_CLIENT:
                continue
            self.drop(session.id)
            mine.remove(session)
        for session in idle:
            if len(self.sessions) < MAX_SESSIONS:
                break
            if session.id in self.sessions:
                self.drop(session.id)

    def drop(self, sid: str) -> None:
        session = self.sessions.pop(sid, None)
        if session and session.conn.reader_task and not session.conn.reader_task.done():
            session.conn.reader_task.cancel()

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
                self.drop(sid)
            await asyncio.sleep(120)

class App:
    def __init__(self, web_root: Path):
        self.web_root = web_root
        self.sessions = SessionManager()

    async def index(self, request: web.Request) -> web.StreamResponse:
        # Embed deploy identity in HTML so the badge does not depend on a separate /health fetch.
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

    async def favicon(self, request: web.Request) -> web.StreamResponse:
        response = web.FileResponse(self.web_root / "icons" / "icon-192.png")
        response.content_type = "image/png"
        return response

    async def health(self, request: web.Request) -> web.StreamResponse:
        info = build_info()
        info["sessions"] = len(self.sessions.sessions)
        return web.json_response(info)

    async def create_session(self, request: web.Request) -> web.StreamResponse:
        session = self.sessions.create(client_address(request))
        if session is None:
            return web.json_response({"ok": False, "error": "Too many open sessions. Close some tabs and try again."}, status=503)
        return web.json_response({"ok": True, "session_id": session.id})

    async def connect_session(self, request: web.Request) -> web.StreamResponse:
        sid = request.match_info["sid"]
        session = self.sessions.get(sid)
        if not session:
            return web.json_response({"ok": False, "error": "invalid session"}, status=404)

        data = await read_json_body(request)
        server = str(data.get("server", "")).strip()
        slot_name = str(data.get("slot_name", "")).strip()
        password = str(data.get("password", "")).strip()

        if not server or not slot_name:
            return web.json_response({"ok": False, "error": "server and slot_name are required"}, status=400)
        if len(server) > 255 or len(slot_name) > 64 or len(password) > 256:
            return web.json_response({"ok": False, "error": "server, slot name or password is too long"}, status=400)
        allow_private = is_local_request(request)
        address_error = await ap_server_address_error(server, allow_private)
        if address_error:
            return web.json_response({"ok": False, "error": address_error}, status=400)

        await session.conn.connect(server, slot_name, password, allow_private=allow_private)
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

    async def practice_new_board(self, request: web.Request) -> web.StreamResponse:
        session = self.sessions.get(request.match_info["sid"])
        if not session:
            return web.json_response({"ok": False, "error": "invalid session"}, status=404)
        result = await session.conn.new_practice_board()
        return web.json_response(result, status=200 if result.get("ok") else 400)

    async def practice_new_realm(self, request: web.Request) -> web.StreamResponse:
        session = self.sessions.get(request.match_info["sid"])
        if not session:
            return web.json_response({"ok": False, "error": "invalid session"}, status=404)
        result = await session.conn.new_practice_realm()
        return web.json_response(result, status=200 if result.get("ok") else 400)

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
        # The Journey pop-out window polls with ?peek=1 so it never takes the main window's deaths and traps.
        if request.query.get("peek") != "1":
            status["pending_events"] = session.conn.take_pending_events()
        return web.json_response({"ok": True, "status": status})

    async def session_death(self, request: web.Request) -> web.StreamResponse:
        sid = request.match_info["sid"]
        session = self.sessions.get(sid)
        if not session:
            return web.json_response({"ok": False, "error": "invalid session"}, status=404)
        if not session.state.connected_to_ap:
            return web.json_response({"ok": False, "error": "not connected"}, status=400)
        data = await read_json_body(request)
        cause = str(data.get("cause") or "").strip()[:200]
        await session.conn.send_death_link(cause)
        return web.json_response({"ok": True})

    async def session_check(self, request: web.Request) -> web.StreamResponse:
        sid = request.match_info["sid"]
        session = self.sessions.get(sid)
        if not session:
            return web.json_response({"ok": False, "error": "invalid session"}, status=404)

        data = await read_json_body(request)
        page_title = str(data.get("page_title", "")).strip()
        try:
            clicks_used = max(0, int(data.get("clicks_used", 0)))
        except (TypeError, ValueError):
            clicks_used = 0
        # Strict mode: display/restore callers must not score. Only intentional
        # in-article clicks should send submit_check=true (client default).
        submit_check = bool(data.get("submit_check", True))
        travel_kind = str(data.get("travel_kind") or "").strip().lower()
        if travel_kind not in {"nav", "back", "restore", "death"}:
            travel_kind = "nav" if submit_check else "restore"

        if not page_title:
            return web.json_response({"ok": False, "error": "page_title is required"}, status=400)
        if len(page_title) > MAX_TITLE_CHARS:
            return web.json_response({"ok": False, "error": "page_title is too long"}, status=400)

        session.conn.state.last_seen = time.time()
        session.conn.state.merge_clicks(clicks_used)
        await session.conn._persist_clicks()
        session.conn._remember_page(page_title)
        bingo_completed: list[dict[str, Any]] = []
        if session.state.connected_to_ap or session.state.practice:
            bingo_completed = await session.conn.apply_bingo_visit(page_title)

        if travel_kind == "nav":
            await session.conn._append_travel_event("nav", page_title)
        elif travel_kind == "death":
            await session.conn._append_travel_event("death", page_title)

        if not submit_check:
            # Back, death and restore still change the page the Compass reads.
            session.conn._schedule_compass(page_title)
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

    async def session_teleport(self, request: web.Request) -> web.StreamResponse:
        sid = request.match_info["sid"]
        session = self.sessions.get(sid)
        if not session:
            return web.json_response({"ok": False, "error": "invalid session"}, status=404)
        result = await session.conn.teleport_random_page()
        status_code = 200 if result.get("ok") else 400
        return web.json_response(result, status=status_code)

    async def session_journey(self, request: web.Request) -> web.StreamResponse:
        sid = request.match_info["sid"]
        session = self.sessions.get(sid)
        if not session:
            return web.json_response({"ok": False, "error": "invalid session"}, status=404)
        payload = session.state.travel_payload()
        return web.json_response({
            "ok": True,
            "events": payload.get("events") or [],
            "visit_counts": payload.get("visit_counts") or {},
            "paths": session.state.path_payload(),
            "travel_storage_ready": session.state.travel_storage_ready,
        })

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
        if not debug_menu_enabled():
            return web.json_response({"ok": False, "error": "not found"}, status=404)
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
        app = web.Application(client_max_size=MAX_REQUEST_BYTES)
        app.router.add_get("/", self.index)
        app.router.add_get("/favicon.ico", self.favicon)
        app.router.add_get("/manifest.webmanifest", self.manifest)
        app.router.add_get("/service-worker.js", self.service_worker)
        app.router.add_get("/health", self.health)
        app.router.add_post("/api/session", self.create_session)
        app.router.add_post("/api/session/{sid}/connect", self.connect_session)
        app.router.add_post("/api/session/{sid}/practice", self.practice_session)
        app.router.add_post("/api/session/{sid}/practice/new-board", self.practice_new_board)
        app.router.add_post("/api/session/{sid}/practice/new-realm", self.practice_new_realm)
        app.router.add_post("/api/session/{sid}/disconnect", self.disconnect_session)
        app.router.add_get("/api/session/{sid}/status", self.session_status)
        app.router.add_post("/api/session/{sid}/death", self.session_death)
        app.router.add_post("/api/session/{sid}/check", self.session_check)
        app.router.add_post("/api/session/{sid}/bingo-stamps", self.session_bingo_stamps)
        app.router.add_post("/api/session/{sid}/bingo-stamp", self.session_use_bingo_stamp)
        app.router.add_post("/api/session/{sid}/reroll-target", self.session_reroll_target)
        app.router.add_post("/api/session/{sid}/use-back", self.session_use_back)
        app.router.add_post("/api/session/{sid}/teleport", self.session_teleport)
        app.router.add_get("/api/session/{sid}/journey", self.session_journey)
        if debug_menu_enabled():
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

    LOG.info(f"Wikipelago bridge running on http://{args.host}:{args.port}")
    if debug_menu_enabled():
        LOG.info("Debug menu enabled (WIKIPELAGO_DEBUG_MENU)")
    while True:
        await asyncio.sleep(3600)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Wikipelago bridge")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "5000")))
    parser.add_argument(
        "--debug-menu",
        action="store_true",
        help="Enable the playtest debug console (same as WIKIPELAGO_DEBUG_MENU=1)",
    )
    return parser.parse_args()


def launch() -> None:
    args = parse_args()
    if args.debug_menu:
        os.environ["WIKIPELAGO_DEBUG_MENU"] = "1"
    asyncio.run(main_async(args))


if __name__ == "__main__":
    launch()
