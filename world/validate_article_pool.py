#!/usr/bin/env python3
"""Validate shipped Wikipelago article pools (data/pool_*.json) against Wikipedia."""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APWORLD = ROOT / "APWorldSource" / "wikipelago"
DATA_DIR = APWORLD / "data"
SUPPORTED_LANGS = ("en", "fr", "de", "es", "it", "pt", "nl", "sv", "pl")

USER_AGENT = "WikipelagoPoolValidator/1.1 (https://github.com/Dreskn/Wikipelago-Continued)"
BATCH_SIZE = 50
SLEEP_SECONDS = 0.1
REPORT_PATH = ROOT / "pool_validation_report.json"


def load_pool_titles(lang: str) -> list[str]:
    """Titles from the runtime pool JSON used by the apworld."""
    code = (lang or "en").strip().lower()
    if code not in SUPPORTED_LANGS:
        raise ValueError(
            f"Unsupported language '{lang}'. Supported: {', '.join(SUPPORTED_LANGS)}"
        )
    path = DATA_DIR / f"pool_{code}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Missing runtime article pool: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    titles: list[str] = []
    for entry in payload.get("entries") or []:
        title = str(entry.get("title") or "").strip()
        if title:
            titles.append(title)
    if not titles:
        raise RuntimeError(f"Pool for '{code}' is empty: {path}")
    return titles


def wiki_api_url(lang: str) -> str:
    code = (lang or "en").strip().lower() or "en"
    return f"https://{code}.wikipedia.org/w/api.php"


def query_batch(lang: str, titles: list[str]) -> dict:
    params = {
        "action": "query",
        "format": "json",
        "redirects": "1",
        "prop": "info|pageprops",
        "ppprop": "disambiguation",
        "titles": "|".join(titles),
    }
    url = f"{wiki_api_url(lang)}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def is_disambiguation(page: dict) -> bool:
    pp = page.get("pageprops") or {}
    return "disambiguation" in pp


def classify_batch(titles: list[str], data: dict) -> dict[str, dict]:
    """Map each original title to classification info."""
    query = data.get("query") or {}
    pages = query.get("pages") or {}
    redirects = query.get("redirects") or []
    normalized = query.get("normalized") or []

    # Build maps from requested/normalized titles to final page titles
    # MediaWiki may normalize then redirect.
    from_to: dict[str, str] = {}
    for n in normalized:
        from_to[n["from"]] = n["to"]
    for r in redirects:
        from_to[r["from"]] = r["to"]

    def resolve(title: str) -> str:
        seen: set[str] = set()
        cur = title
        while cur in from_to and cur not in seen:
            seen.add(cur)
            cur = from_to[cur]
        return cur

    # Index pages by title
    by_title: dict[str, dict] = {}
    for page in pages.values():
        t = page.get("title")
        if t:
            by_title[t] = page

    results: dict[str, dict] = {}
    for original in titles:
        final_title = resolve(original)
        page = by_title.get(final_title)
        if page is None:
            # Try case-insensitive match among pages
            lower = final_title.casefold()
            for t, p in by_title.items():
                if t.casefold() == lower:
                    page = p
                    final_title = t
                    break

        if page is None:
            results[original] = {"status": "missing", "canonical": None}
            continue

        if page.get("missing") is not None or page.get("invalid") is not None:
            results[original] = {"status": "missing", "canonical": None}
            continue

        if is_disambiguation(page):
            results[original] = {
                "status": "disambiguation",
                "canonical": page.get("title"),
            }
            continue

        # More reliable: check if we followed a redirect (not just normalization)
        followed_redirect = False
        cur = original
        # apply normalization first
        for n in normalized:
            if n["from"] == cur:
                cur = n["to"]
                break
        for r in redirects:
            if r["from"] == cur:
                followed_redirect = True
                cur = r["to"]
                break
        # also check if original itself was a redirect source
        if not followed_redirect:
            for r in redirects:
                if r["from"] == original:
                    followed_redirect = True
                    break

        canonical = page.get("title")
        if followed_redirect:
            results[original] = {
                "status": "redirect_ok",
                "canonical": canonical,
            }
        else:
            results[original] = {"status": "ok", "canonical": canonical}

    return results


def validate_lang(lang: str) -> dict:
    pool = load_pool_titles(lang)
    counts = Counter(pool)
    duplicates = {t: c for t, c in sorted(counts.items()) if c > 1}

    # Unique titles for API (still classify every occurrence via unique query)
    unique_titles = list(dict.fromkeys(pool))

    classifications: dict[str, dict] = {}
    total_batches = (len(unique_titles) + BATCH_SIZE - 1) // BATCH_SIZE
    for i in range(0, len(unique_titles), BATCH_SIZE):
        batch = unique_titles[i : i + BATCH_SIZE]
        attempt = 0
        while True:
            attempt += 1
            try:
                data = query_batch(lang, batch)
                break
            except urllib.error.HTTPError as e:
                if e.code in (429, 503) and attempt < 5:
                    time.sleep(1.0 * attempt)
                    continue
                raise
            except urllib.error.URLError:
                if attempt < 5:
                    time.sleep(1.0 * attempt)
                    continue
                raise
        batch_results = classify_batch(batch, data)
        classifications.update(batch_results)
        print(
            f"[{lang}] Batch {i // BATCH_SIZE + 1}/{total_batches}: {len(batch)} titles",
            flush=True,
        )
        time.sleep(SLEEP_SECONDS)

    missing: list[str] = []
    disambiguation: list[str] = []
    redirect_ok: list[dict] = []
    ok_count = 0

    for title in unique_titles:
        info = classifications[title]
        status = info["status"]
        if status == "ok":
            ok_count += 1
        elif status == "missing":
            missing.append(title)
        elif status == "disambiguation":
            disambiguation.append(title)
        elif status == "redirect_ok":
            redirect_ok.append(
                {"title": title, "canonical": info["canonical"]}
            )

    return {
        "lang": lang,
        "pool_file": str(DATA_DIR / f"pool_{lang}.json"),
        "summary": {
            "pool_size": len(pool),
            "unique_titles": len(unique_titles),
            "ok": ok_count,
            "missing": len(missing),
            "disambiguation": len(disambiguation),
            "redirect_ok": len(redirect_ok),
            "duplicates": len(duplicates),
        },
        "missing": missing,
        "disambiguation": disambiguation,
        "redirect_ok": redirect_ok,
        "duplicates": duplicates,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--lang",
        default="en",
        help=(
            "Wikipedia language pool to validate (default: en). "
            f"One of: {', '.join(SUPPORTED_LANGS)}, or 'all'."
        ),
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if any missing, disambiguation, or duplicate titles are found.",
    )
    args = parser.parse_args()

    lang_arg = (args.lang or "en").strip().lower()
    if lang_arg == "all":
        langs = list(SUPPORTED_LANGS)
    elif lang_arg in SUPPORTED_LANGS:
        langs = [lang_arg]
    else:
        print(
            f"Unsupported --lang '{args.lang}'. "
            f"Use one of: {', '.join(SUPPORTED_LANGS)}, or 'all'.",
            file=sys.stderr,
        )
        return 2

    def _safe_print(text: str) -> None:
        # CI/Windows consoles may not be UTF-8; never crash on title dumps.
        try:
            print(text)
        except UnicodeEncodeError:
            encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
            print(text.encode(encoding, errors="replace").decode(encoding, errors="replace"))

    lang_reports: list[dict] = []
    failed = False
    for lang in langs:
        report = validate_lang(lang)
        lang_reports.append(report)
        summary = report["summary"]
        if report["missing"] or report["disambiguation"] or report["duplicates"]:
            failed = True
        _safe_print(f"\n=== Wikipelago article pool validation ({lang}) ===")
        _safe_print(f"pool_file:       {report['pool_file']}")
        _safe_print(f"pool_size:       {summary['pool_size']}")
        _safe_print(f"unique_titles:   {summary['unique_titles']}")
        _safe_print(f"ok:              {summary['ok']}")
        _safe_print(f"missing:         {summary['missing']}")
        _safe_print(f"disambiguation:  {summary['disambiguation']}")
        _safe_print(f"redirect_ok:     {summary['redirect_ok']}")
        _safe_print(f"duplicates:      {summary['duplicates']}")
        if report["missing"]:
            _safe_print("missing titles: " + ", ".join(report["missing"][:20]))
        if report["disambiguation"]:
            _safe_print("disambiguation titles: " + ", ".join(report["disambiguation"][:20]))
        if report["duplicates"]:
            _safe_print("duplicate titles: " + ", ".join(list(report["duplicates"])[:20]))

    out = {
        "langs": langs,
        "reports": lang_reports,
    }
    REPORT_PATH.write_text(
        json.dumps(out, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _safe_print(f"\nReport written to: {REPORT_PATH}")

    if args.strict and failed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
