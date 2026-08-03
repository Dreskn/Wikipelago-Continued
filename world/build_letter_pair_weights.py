#!/usr/bin/env python3
"""Build letter-pair frequency weights from Wikipedia title dumps.

Supported languages match the shipped article pools:
  en, fr, de, es, it, pt, nl, sv, pl

Source dumps (mainspace titles, includes redirects), one per language:
  https://dumps.wikimedia.org/{lang}wiki/latest/{lang}wiki-latest-all-titles-in-ns0.gz

Letter-pair rule (must match in-game bingo stamping):
  Scan the title left-to-right for A-Z letters only; take the first two.
  Examples: The_Beatles -> TH, Dota_2 -> DO, 2001:_A_Space_Odyssey -> AS.
  Titles that never yield two Latin letters are skipped.

Usage:
  # All supported languages (download dumps if needed):
  python world/build_letter_pair_weights.py --lang all

  # One language:
  python world/build_letter_pair_weights.py --lang fr

  # Use an already-downloaded dump:
  python world/build_letter_pair_weights.py --lang de --dump path/to/dewiki-...gz
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
SUPPORTED_LANGS = ("en", "fr", "de", "es", "it", "pt", "nl", "sv", "pl")
DEFAULT_CACHE = ROOT / "_cache"
DEFAULT_OUT_DIR = ROOT / "APWorldSource" / "Wikipelago"
USER_AGENT = "WikipelagoLetterPairWeights/1.1 (https://github.com/Dreskn/Wikipelago-Continued)"

ALL_PAIRS = [a + b for a in string.ascii_uppercase for b in string.ascii_uppercase]


def dump_url(lang: str) -> str:
    return f"https://dumps.wikimedia.org/{lang}wiki/latest/{lang}wiki-latest-all-titles-in-ns0.gz"


def default_dump_path(lang: str) -> Path:
    return DEFAULT_CACHE / f"{lang}wiki-latest-all-titles-in-ns0.gz"


def default_out_path(lang: str) -> Path:
    return DEFAULT_OUT_DIR / f"letter_pair_weights_{lang}.json"


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


def download_dump(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {url}")
    print(f"  -> {dest}")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
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


def build_one(
    lang: str,
    *,
    dump_path: Path | None,
    out_path: Path | None,
    no_download: bool,
    force_download: bool,
) -> int:
    lang = lang.strip().lower()
    if lang not in SUPPORTED_LANGS:
        print(f"Unsupported language '{lang}'. Supported: {', '.join(SUPPORTED_LANGS)}", file=sys.stderr)
        return 1

    dump = dump_path or default_dump_path(lang)
    out = out_path or default_out_path(lang)
    url = dump_url(lang)

    if force_download or not dump.is_file():
        if no_download:
            print(f"Dump not found: {dump}", file=sys.stderr)
            return 1
        download_dump(url, dump)
    else:
        print(f"[{lang}] Using existing dump: {dump} ({dump.stat().st_size:,} bytes)")

    print(f"[{lang}] Counting letter pairs…")
    counts, total_lines, skipped = count_pairs_from_dump(dump)
    weights = build_weights(counts)
    nonzero = sum(1 for v in weights.values() if v > 0)
    print(
        f"[{lang}] Done: {total_lines:,} dump lines, {skipped:,} skipped, "
        f"{sum(weights.values()):,} counted, {nonzero}/676 pairs with weight > 0"
    )

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(weights, indent=0, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[{lang}] Wrote {out}")

    top = sorted(weights.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
    print(f"[{lang}] Top 10 pairs:")
    for pair, n in top:
        print(f"  {pair}: {n:,}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--lang",
        default="all",
        help=f"Language code, or 'all' ({', '.join(SUPPORTED_LANGS)})",
    )
    parser.add_argument(
        "--dump",
        type=Path,
        default=None,
        help="Path to a titles dump (only valid with a single --lang)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output JSON path (only valid with a single --lang)",
    )
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="Do not download dumps if missing",
    )
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Re-download dumps even if they already exist",
    )
    args = parser.parse_args()

    lang_arg = str(args.lang or "all").strip().lower()
    if lang_arg == "all":
        if args.dump is not None or args.out is not None:
            print("--dump/--out require a single --lang, not 'all'", file=sys.stderr)
            return 1
        languages = list(SUPPORTED_LANGS)
    else:
        languages = [lang_arg]

    failures = 0
    for lang in languages:
        code = build_one(
            lang,
            dump_path=args.dump if len(languages) == 1 else None,
            out_path=args.out if len(languages) == 1 else None,
            no_download=bool(args.no_download),
            force_download=bool(args.force_download),
        )
        if code != 0:
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
