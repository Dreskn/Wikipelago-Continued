"""Letter-pair bingo helpers: title key, shipped weights, board generation."""

from __future__ import annotations

import json
import string
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from random import Random

WEIGHTS_PATH = Path(__file__).resolve().parent / "letter_pair_weights.json"
ALL_PAIRS = [a + b for a in string.ascii_uppercase for b in string.ascii_uppercase]

_WEIGHTS_CACHE: dict[str, int] | None = None


def letter_pair_from_title(title: str) -> str | None:
    """Return first two A–Z letters in title order, or None if fewer than two exist."""
    letters: list[str] = []
    for ch in title:
        if "A" <= ch <= "Z" or "a" <= ch <= "z":
            letters.append(ch.upper())
            if len(letters) == 2:
                return letters[0] + letters[1]
    return None


def load_letter_pair_weights() -> dict[str, int]:
    global _WEIGHTS_CACHE
    if _WEIGHTS_CACHE is None:
        raw: str | None = None
        # Prefer package resources so zip/apworld installs still find the JSON.
        try:
            from importlib.resources import files

            raw = files(__package__).joinpath("letter_pair_weights.json").read_text(encoding="utf-8")
        except Exception:
            raw = None
        if raw is None:
            if not WEIGHTS_PATH.is_file():
                raise FileNotFoundError(
                    "letter_pair_weights.json is missing from the Wikipelago apworld. "
                    "Rebuild with world/build_apworld.ps1 and reinstall the package "
                    f"(expected next to letter_pairs.py: {WEIGHTS_PATH})."
                )
            raw = WEIGHTS_PATH.read_text(encoding="utf-8")
        parsed = json.loads(raw)
        _WEIGHTS_CACHE = {str(k).upper(): int(v) for k, v in parsed.items()}
    return _WEIGHTS_CACHE


def bingo_location_count(grid_size: int) -> int:
    """N rows + N cols + 2 diagonals + full card."""
    return 2 * grid_size + 3


def bingo_location_names(grid_size: int) -> list[str]:
    names = [f"Letter Pair Bingo - Row {index}" for index in range(1, grid_size + 1)]
    names.extend(f"Letter Pair Bingo - Column {index}" for index in range(1, grid_size + 1))
    names.extend(
        [
            "Letter Pair Bingo - Diagonal",
            "Letter Pair Bingo - Anti-Diagonal",
            "Letter Pair Bingo - Full Card",
        ]
    )
    return names


def bingo_slot_location_ids(location_name_to_id: dict[str, int], grid_size: int) -> dict[str, int]:
    ids: dict[str, int] = {}
    for index in range(1, grid_size + 1):
        ids[f"row_{index}"] = location_name_to_id[f"Letter Pair Bingo - Row {index}"]
        ids[f"col_{index}"] = location_name_to_id[f"Letter Pair Bingo - Column {index}"]
    ids["diag"] = location_name_to_id["Letter Pair Bingo - Diagonal"]
    ids["anti"] = location_name_to_id["Letter Pair Bingo - Anti-Diagonal"]
    ids["full"] = location_name_to_id["Letter Pair Bingo - Full Card"]
    return ids


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


def build_letter_pair_bingo_board(rng: Random, grid_size: int) -> list[list[str]]:
    """Build an N×N board of uppercase letter pairs.

    N=26: sorted A–Z × A–Z (unweighted).
    N=3..25: weighted sample without replacement from shipped frequencies, then shuffled into the grid.
    """
    if grid_size < 3 or grid_size > 26:
        raise Exception(f"Wikipelago bingo_letterpairs_grid must be 3–26, got {grid_size}.")

    if grid_size == 26:
        return [[f"{chr(65 + row)}{chr(65 + col)}" for col in range(26)] for row in range(26)]

    weights = load_letter_pair_weights()
    pairs = list(ALL_PAIRS)
    weight_list = [int(weights.get(pair, 0)) for pair in pairs]
    needed = grid_size * grid_size
    sampled = _weighted_sample_without_replacement(rng, pairs, weight_list, needed)
    rng.shuffle(sampled)
    return [sampled[row * grid_size : (row + 1) * grid_size] for row in range(grid_size)]
