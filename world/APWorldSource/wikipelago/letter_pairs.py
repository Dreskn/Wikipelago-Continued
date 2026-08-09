"""Letter-pair bingo helpers: title key, shipped weights, board generation.

Letter extraction follows each language's Scrabble tile set
(https://en.wikipedia.org/wiki/Scrabble_letter_distributions):
distinct single-character tiles stay distinct; other diacritics fold to base
Latin. German ß/ẞ expands to SS. Digraph tiles (CH/LL/RR/IJ) are not used.
"""

from __future__ import annotations

import json
import string
import unicodedata
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from random import Random

WEIGHTS_DIR = Path(__file__).resolve().parent
MAX_BINGO_GRID_SIZE = 20
MIN_BINGO_GRID_SIZE = 3

# Uppercase alphabets: A–Z plus Scrabble distinct letters for that language.
# Order is A–Z first, then language extras (used for pair enumeration).
_ASCII = string.ascii_uppercase
SCRABBLE_LETTERS: dict[str, str] = {
    "en": _ASCII,
    "fr": _ASCII,
    "it": _ASCII,
    "nl": _ASCII,
    "es": _ASCII + "Ñ",
    "pt": _ASCII + "Ç",
    "de": _ASCII + "ÄÖÜ",
    "sv": _ASCII + "ÅÄÖ",
    "pl": _ASCII + "ĄĆĘŁŃÓŚŹŻ",
}
SUPPORTED_LANGS = tuple(SCRABBLE_LETTERS.keys())

_WEIGHTS_CACHE: dict[str, dict[str, int]] = {}


def bingo_alphabet(lang: str) -> str:
    """Return the uppercase bingo alphabet for a Wikipedia language code."""
    code = (lang or "en").strip().lower()
    if code not in SCRABBLE_LETTERS:
        code = "en"
    return SCRABBLE_LETTERS[code]


def all_pairs_for_lang(lang: str) -> list[str]:
    """Every ordered letter-pair for this language's bingo alphabet."""
    alphabet = bingo_alphabet(lang)
    return [a + b for a in alphabet for b in alphabet]


def _fold_base_latin(ch: str) -> str:
    """Fold a non-Scrabble character toward base Latin (may be empty)."""
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


def iter_bingo_letters(title: str, lang: str = "en") -> Iterator[str]:
    """Yield bingo letters from a title under the language's Scrabble rules."""
    alphabet = set(bingo_alphabet(lang))
    for ch in title:
        if not ch or ch.isspace():
            continue
        upper = ch.upper()
        if upper in alphabet:
            yield upper
            continue
        # German sharp S before generic fold (not in Scrabble alphabet).
        if ch in ("ß", "ẞ") or upper == "ẞ":
            yield "S"
            yield "S"
            continue
        folded = _fold_base_latin(ch)
        for letter in folded:
            if letter in alphabet:
                yield letter


def letter_pair_from_title(title: str, lang: str = "en") -> str | None:
    """Return first two bingo letters in title order, or None if fewer than two."""
    letters: list[str] = []
    for letter in iter_bingo_letters(title, lang):
        letters.append(letter)
        if len(letters) == 2:
            return letters[0] + letters[1]
    return None


def _weights_filename(lang: str) -> str:
    return f"letter_pair_weights_{lang}.json"


def _read_weights_raw(lang: str) -> str | None:
    name = _weights_filename(lang)
    try:
        from importlib.resources import files

        return files(__package__).joinpath(name).read_text(encoding="utf-8")
    except Exception:
        path = WEIGHTS_DIR / name
        if path.is_file():
            return path.read_text(encoding="utf-8")
    return None


def load_letter_pair_weights(lang: str = "en") -> dict[str, int]:
    """Load shipped title-pair frequencies for a Wikipedia language."""
    code = (lang or "en").strip().lower()
    if code not in SUPPORTED_LANGS:
        code = "en"
    cached = _WEIGHTS_CACHE.get(code)
    if cached is not None:
        return cached

    raw = _read_weights_raw(code)
    if raw is None and code != "en":
        # Dev/partial packages: prefer generating over hard-failing mid-roll.
        raw = _read_weights_raw("en")
        if raw is not None:
            code = "en"
    if raw is None:
        raise FileNotFoundError(
            f"{_weights_filename(code)} is missing from the Wikipelago apworld. "
            "Rebuild weights with world/build_letter_pair_weights.py --lang all, "
            "then world/build_apworld.ps1 and reinstall the package "
            f"(expected next to letter_pairs.py: {WEIGHTS_DIR / _weights_filename(code)})."
        )
    parsed = json.loads(raw)
    weights = {str(k).upper(): int(v) for k, v in parsed.items()}
    _WEIGHTS_CACHE[code] = weights
    return weights


def bingo_location_count(grid_size: int) -> int:
    """N rows + N cols + 2 diagonals + full card (one board)."""
    return 2 * grid_size + 3


def bingo_location_names(grid_size: int, board: int = 1) -> list[str]:
    names = [f"Letter Pair Bingo - Board {board} Row {index}" for index in range(1, grid_size + 1)]
    names.extend(
        f"Letter Pair Bingo - Board {board} Column {index}" for index in range(1, grid_size + 1)
    )
    names.extend(
        [
            f"Letter Pair Bingo - Board {board} Diagonal",
            f"Letter Pair Bingo - Board {board} Anti-Diagonal",
            f"Letter Pair Bingo - Board {board} Full Card",
        ]
    )
    return names


def bingo_slot_location_ids(
    location_name_to_id: dict[str, int],
    grid_size: int,
    board: int = 1,
) -> dict[str, int]:
    ids: dict[str, int] = {}
    for index in range(1, grid_size + 1):
        # Underscore keys match bridge/web (row_1 / col_1).
        ids[f"row_{index}"] = location_name_to_id[
            f"Letter Pair Bingo - Board {board} Row {index}"
        ]
        ids[f"col_{index}"] = location_name_to_id[
            f"Letter Pair Bingo - Board {board} Column {index}"
        ]
    ids["diag"] = location_name_to_id[f"Letter Pair Bingo - Board {board} Diagonal"]
    ids["anti"] = location_name_to_id[f"Letter Pair Bingo - Board {board} Anti-Diagonal"]
    ids["full"] = location_name_to_id[f"Letter Pair Bingo - Board {board} Full Card"]
    return ids


def bingo_slot_location_ids_by_board(
    location_name_to_id: dict[str, int],
    grid_size: int,
    board_count: int,
) -> dict[str, dict[str, int]]:
    return {
        str(board): bingo_slot_location_ids(location_name_to_id, grid_size, board)
        for board in range(1, board_count + 1)
    }


def _weighted_sample_without_replacement(rng: Random, pairs: list[str], weights: list[int], count: int) -> list[str]:
    pool = [(pair, weight) for pair, weight in zip(pairs, weights) if weight > 0]
    if len(pool) < count:
        raise Exception(
            "Wikipelago letter-pair bingo cannot sample a board: "
            f"need {count} positive-weight pairs, only {len(pool)} available."
        )
    picked: list[str] = []
    for _ in range(count):
        total = sum(weight for _, weight in pool)
        roll = rng.random() * total
        acc = 0.0
        chosen_index = len(pool) - 1
        for index, (_, weight) in enumerate(pool):
            acc += weight
            if roll <= acc:
                chosen_index = index
                break
        picked.append(pool.pop(chosen_index)[0])
    return picked


def build_letter_pair_bingo_board(
    rng: Random,
    grid_size: int,
    lang: str = "en",
) -> list[list[str]]:
    """Build an N×N board of uppercase letter pairs (weighted sample, N=3..20)."""
    if grid_size < MIN_BINGO_GRID_SIZE or grid_size > MAX_BINGO_GRID_SIZE:
        raise Exception(
            f"Wikipelago bingo_letterpairs_grid must be "
            f"{MIN_BINGO_GRID_SIZE}–{MAX_BINGO_GRID_SIZE}, got {grid_size}."
        )

    weights = load_letter_pair_weights(lang)
    pairs = all_pairs_for_lang(lang)
    weight_list = [int(weights.get(pair, 0)) for pair in pairs]
    needed = grid_size * grid_size
    sampled = _weighted_sample_without_replacement(rng, pairs, weight_list, needed)
    rng.shuffle(sampled)
    return [sampled[row * grid_size : (row + 1) * grid_size] for row in range(grid_size)]
