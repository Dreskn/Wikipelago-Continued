#!/usr/bin/env python3
"""Build letter-pair frequency weights from an English Wikipedia title dump.

Source dump (mainspace titles, includes redirects):
  https://dumps.wikimedia.org/enwiki/latest/enwiki-latest-all-titles-in-ns0.gz

Letter-pair rule (must match in-game bingo stamping):
  Scan the title left-to-right for A-Z letters only; take the first two.
  Examples: The_Beatles -> TH, Dota_2 -> DO, 2001:_A_Space_Odyssey -> AS.
  Titles that never yield two Latin letters are skipped.

Usage:
  # Download dump (if needed) and write the shipped JSON:
  python world/build_letter_pair_weights.py

  # Use an already-downloaded dump:
  python world/build_letter_pair_weights.py --dump path/to/enwiki-latest-all-titles-in-ns0.gz

  # Skip download; fail if dump missing:
  python world/build_letter_pair_weights.py --no-download
"""

from __future__ import annotations

import argparse
import gzip
import json
import string
import sys
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_DUMP = ROOT / "_cache" / "enwiki-latest-all-titles-in-ns0.gz"
DEFAULT_OUT = ROOT / "APWorldSource" / "Wikipelago" / "letter_pair_weights.json"
DUMP_URL = "https://dumps.wikimedia.org/enwiki/latest/enwiki-latest-all-titles-in-ns0.gz"
USER_AGENT = "WikipelagoLetterPairWeights/1.0 (https://github.com/Dreskn/Wikipelago-Continued)"

ALL_PAIRS = [a + b for a in string.ascii_uppercase for b in string.ascii_uppercase]


def letter_pair_from_title(title: str) -> str | None:
    """Return first two A-Z letters in title, or None if fewer than two exist."""
    letters: list[str] = []
    for ch in title:
        if "A" <= ch <= "Z" or "a" <= ch <= "z":
            letters.append(ch.upper())
            if len(letters) == 2:
                return letters[0] + letters[1]
    return None


def title_from_dump_line(line: str) -> str:
    """Parse one dump line into a display-ish title (spaces, not underscores)."""
    raw = line.strip()
    if not raw or raw.startswith("#"):
        return ""
    # all-titles.gz style: "0\tPage_Title"; ns0 file is often bare "Page_Title".
    if "\t" in raw:
        raw = raw.split("\t", 1)[-1]
    return raw.replace("_", " ")


def download_dump(dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {DUMP_URL}")
    print(f"  -> {dest}")
    req = urllib.request.Request(DUMP_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=600) as resp, dest.open("wb") as out:
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
    print(f"Download complete ({dest.stat().st_size:,} bytes)")


def count_pairs_from_dump(dump_path: Path) -> tuple[Counter[str], int, int]:
    counts: Counter[str] = Counter()
    total_lines = 0
    skipped = 0
    with gzip.open(dump_path, "rt", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            total_lines += 1
            title = title_from_dump_line(line)
            if not title:
                skipped += 1
                continue
            pair = letter_pair_from_title(title)
            if pair is None:
                skipped += 1
                continue
            counts[pair] += 1
            if total_lines % 1_000_000 == 0:
                print(f"  … {total_lines:,} lines, {sum(counts.values()):,} counted")
    return counts, total_lines, skipped


def build_weights(counts: Counter[str]) -> dict[str, int]:
    return {pair: int(counts.get(pair, 0)) for pair in ALL_PAIRS}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dump",
        type=Path,
        default=DEFAULT_DUMP,
        help=f"Path to enwiki-*-all-titles-in-ns0.gz (default: {DEFAULT_DUMP})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Output JSON path (default: {DEFAULT_OUT})",
    )
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="Do not download the dump if missing",
    )
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Re-download the dump even if it already exists",
    )
    args = parser.parse_args()

    dump_path: Path = args.dump
    if args.force_download or not dump_path.is_file():
        if args.no_download:
            print(f"Dump not found: {dump_path}", file=sys.stderr)
            return 1
        download_dump(dump_path)
    else:
        print(f"Using existing dump: {dump_path} ({dump_path.stat().st_size:,} bytes)")

    print("Counting letter pairs…")
    counts, total_lines, skipped = count_pairs_from_dump(dump_path)
    weights = build_weights(counts)
    nonzero = sum(1 for v in weights.values() if v > 0)
    print(
        f"Done: {total_lines:,} dump lines, {skipped:,} skipped, "
        f"{sum(weights.values()):,} counted, {nonzero}/676 pairs with weight > 0"
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(weights, indent=0, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {args.out}")

    # Quick sanity peek for humans.
    top = sorted(weights.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
    print("Top 10 pairs:")
    for pair, n in top:
        print(f"  {pair}: {n:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
