"""Letter-pair bingo helpers: title key, shipped weights, board generation."""

from __future__ import annotations

import json
import string
from pathlib import Path
from typing import TYPE_CHECKING

from .article_pool import SUPPORTED_LANGS

if TYPE_CHECKING:
    from random import Random

WEIGHTS_DIR = Path(__file__).resolve().parent
ALL_PAIRS = [a + b for a in string.ascii_uppercase for b in string.ascii_uppercase]

_WEIGHTS_CACHE: dict[str, dict[str, int]] = {}


def letter_pair_from_title(title: str) -> str | None:
    """Return first two A–Z letters in title order, or None if fewer than two exist."""
    letters: list[str] = []
    for ch in title:
        if "A" <= ch <= "Z" or "a" <= ch <= "z":
            letters.append(ch.upper())
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
    """Build an N×N board of uppercase letter pairs.

    N=26: sorted A–Z × A–Z (unweighted).
    N=3..25: weighted sample without replacement from that language's shipped
    title-pair frequencies, then shuffled into the grid.
    """
    if grid_size < 3 or grid_size > 26:
        raise Exception(f"Wikipelago bingo_letterpairs_grid must be 3–26, got {grid_size}.")

    if grid_size == 26:
        return [[f"{chr(65 + row)}{chr(65 + col)}" for col in range(26)] for row in range(26)]

    weights = load_letter_pair_weights(lang)
    pairs = list(ALL_PAIRS)
    weight_list = [int(weights.get(pair, 0)) for pair in pairs]
    needed = grid_size * grid_size
    sampled = _weighted_sample_without_replacement(rng, pairs, weight_list, needed)
    rng.shuffle(sampled)
    return [sampled[row * grid_size : (row + 1) * grid_size] for row in range(grid_size)]
