#!/usr/bin/env python3
"""Unit checks for Scrabble-aware bingo letter pairs (world + bridge parity)."""

from __future__ import annotations

import importlib.util
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LP_PATH = ROOT / "APWorldSource" / "wikipelago" / "letter_pairs.py"
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
    ("fr", "Œuf", "OE"),
    ("fr", "Œsophage", "OE"),
    ("fr", "Cœur", "CO"),
    ("en", "Æsir", "AE"),
]


def _load_world_lp():
    spec = importlib.util.spec_from_file_location("wikipelago_letter_pairs", LP_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {LP_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_BRIDGE_PAIR_NAMES = ("_SCRABBLE_LETTERS", "_BINGO_LIGATURES", "_bingo_alphabet", "_fold_bingo_base_latin", "letter_pair_from_title")


def _load_bridge_letter_pair():
    """The bridge's real letter-pair code, lifted out of bridge.py (importing it would need aiohttp)."""
    import ast

    tree = ast.parse(BRIDGE_PATH.read_text(encoding="utf-8"))
    chunks = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in _BRIDGE_PAIR_NAMES:
            chunks.append(node)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(t, ast.Name) and t.id in _BRIDGE_PAIR_NAMES for t in targets):
                chunks.append(node)
    namespace = {"unicodedata": unicodedata}
    exec(compile(ast.Module(body=chunks, type_ignores=[]), str(BRIDGE_PATH), "exec"), namespace)
    missing = [name for name in _BRIDGE_PAIR_NAMES if name not in namespace]
    if missing:
        raise RuntimeError(f"bridge.py is missing {missing}")
    return namespace["letter_pair_from_title"]


def main() -> int:
    world = _load_world_lp()
    bridge_letter_pair = _load_bridge_letter_pair()
    failures = 0
    for lang, title, expect in CASES:
        got = world.letter_pair_from_title(title, lang)
        if got != expect:
            print(f"FAIL world {lang}: {title!r} -> {got!r} (expect {expect!r})", file=sys.stderr)
            failures += 1
        bridge_got = bridge_letter_pair(title, lang)
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
