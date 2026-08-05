#!/usr/bin/env python3
"""Unit checks for Scrabble-aware bingo letter pairs (world + bridge parity)."""

from __future__ import annotations

import importlib.util
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LP_PATH = ROOT / "APWorldSource" / "Wikipelago" / "letter_pairs.py"
BRIDGE_PATH = ROOT.parent / "bridge" / "bridge.py"

CASES = [
    ("en", "Pokémon", "PO"),
    ("fr", "Électricité", "EL"),
    ("es", "Ñandú", "ÑA"),
    ("de", "Äpfel", "ÄP"),
    ("de", "ßuper", "SS"),
    ("de", "Fußball", "FU"),
    ("pl", "Łódź", "ŁÓ"),
    ("pt", "Ação", "AÇ"),
    ("sv", "Öl", "ÖL"),
    ("it", "Città", "CI"),
]


def _load_world_lp():
    spec = importlib.util.spec_from_file_location("wikipelago_letter_pairs", LP_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {LP_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _bridge_letter_pair(title: str, lang: str) -> str | None:
    """Mirror of bridge.letter_pair_from_title (kept in sync by smoke + this test)."""
    alphabet_map = {
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
    code = (lang or "en").strip().lower()
    alphabet = set(alphabet_map.get(code, alphabet_map["en"]))
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
            decomposed = unicodedata.normalize("NFKD", ch)
            for part in decomposed:
                if unicodedata.combining(part):
                    continue
                if "A" <= part <= "Z" or "a" <= part <= "z":
                    letter = part.upper()
                    if letter in alphabet:
                        letters.append(letter)
        if len(letters) >= 2:
            return letters[0] + letters[1]
    return None


def main() -> int:
    world = _load_world_lp()
    failures = 0
    for lang, title, expect in CASES:
        got = world.letter_pair_from_title(title, lang)
        if got != expect:
            print(f"FAIL world {lang}: {title!r} -> {got!r} (expect {expect!r})", file=sys.stderr)
            failures += 1
        bridge_got = _bridge_letter_pair(title, lang)
        if bridge_got != expect:
            print(f"FAIL bridge {lang}: {title!r} -> {bridge_got!r} (expect {expect!r})", file=sys.stderr)
            failures += 1

    # Bridge source must still expose lang-aware signature / Scrabble table.
    bridge_src = BRIDGE_PATH.read_text(encoding="utf-8")
    if "def letter_pair_from_title(title: str, lang: str" not in bridge_src:
        print("FAIL bridge letter_pair_from_title missing lang parameter", file=sys.stderr)
        failures += 1
    if "ĄĆĘŁŃÓŚŹŻ" not in bridge_src:
        print("FAIL bridge missing Polish Scrabble letters", file=sys.stderr)
        failures += 1

    if world.MAX_BINGO_GRID_SIZE != 20:
        print(f"FAIL MAX_BINGO_GRID_SIZE={world.MAX_BINGO_GRID_SIZE} (expect 20)", file=sys.stderr)
        failures += 1

    pl_pairs = len(world.all_pairs_for_lang("pl"))
    if pl_pairs != 35 * 35:
        print(f"FAIL pl pair space {pl_pairs} (expect 1225)", file=sys.stderr)
        failures += 1

    # Shipped weights must include expanded Scrabble pair keys.
    weights_dir = LP_PATH.parent
    pl_weights = __import__("json").loads((weights_dir / "letter_pair_weights_pl.json").read_text(encoding="utf-8"))
    de_weights = __import__("json").loads((weights_dir / "letter_pair_weights_de.json").read_text(encoding="utf-8"))
    if "ŁÓ" not in pl_weights:
        print("FAIL pl weights missing ŁÓ key", file=sys.stderr)
        failures += 1
    if len(pl_weights) != 1225:
        print(f"FAIL pl weights size {len(pl_weights)} (expect 1225)", file=sys.stderr)
        failures += 1
    if "ÄP" not in de_weights:
        print("FAIL de weights missing ÄP key", file=sys.stderr)
        failures += 1
    if len(de_weights) != 29 * 29:
        print(f"FAIL de weights size {len(de_weights)} (expect 841)", file=sys.stderr)
        failures += 1

    if failures:
        print(f"{failures} failure(s)", file=sys.stderr)
        return 1
    print(f"OK: {len(CASES)} cases × world+bridge, grid max 20, pl pairs={pl_pairs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
