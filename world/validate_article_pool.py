#!/usr/bin/env python3
"""Validate Wikipelago entertainment article pool against English Wikipedia."""

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
sys.path.insert(0, str(APWORLD))

from entertainment_articles import ENTERTAINMENT_ARTICLE_POOL  # noqa: E402

API_URL = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "WikipelagoPoolValidator/1.0 (https://github.com/Dreskn/Wikipelago-Continued)"
BATCH_SIZE = 50
SLEEP_SECONDS = 0.1
REPORT_PATH = ROOT / "pool_validation_report.json"


def query_batch(titles: list[str]) -> dict:
    params = {
        "action": "query",
        "format": "json",
        "redirects": "1",
        "prop": "info|pageprops",
        "ppprop": "disambiguation",
        "titles": "|".join(titles),
    }
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
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

        redirected = final_title != original and (
            original in from_to
            or any(n["from"] == original for n in normalized)
            or resolve(original) != original
        )
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if any missing, disambiguation, or duplicate titles are found.",
    )
    args = parser.parse_args()

    pool = [
        entry[0] if isinstance(entry, (list, tuple)) else entry
        for entry in ENTERTAINMENT_ARTICLE_POOL
    ]
    counts = Counter(pool)
    duplicates = {t: c for t, c in sorted(counts.items()) if c > 1}

    # Unique titles for API (still classify every occurrence via unique query)
    unique_titles = list(dict.fromkeys(pool))

    classifications: dict[str, dict] = {}
    for i in range(0, len(unique_titles), BATCH_SIZE):
        batch = unique_titles[i : i + BATCH_SIZE]
        attempt = 0
        while True:
            attempt += 1
            try:
                data = query_batch(batch)
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
            f"Batch {i // BATCH_SIZE + 1}/{(len(unique_titles) + BATCH_SIZE - 1) // BATCH_SIZE}: "
            f"{len(batch)} titles",
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

    report = {
        "summary": {
            "pool_size": len(pool),
            "unique_titles": len(unique_titles),
            "ok": ok_count,
            "missing": len(missing),
            "disambiguation": len(disambiguation),
            "redirect_ok": len(redirect_ok),
            "duplicates": len(duplicates),
            "all_ok": ok_count,
        },
        "missing": missing,
        "disambiguation": disambiguation,
        "redirect_ok": redirect_ok,
        "duplicates": duplicates,
        "all_ok": ok_count,
    }

    REPORT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("\n=== Wikipelago article pool validation ===")
    print(f"pool_size:       {report['summary']['pool_size']}")
    print(f"unique_titles:   {report['summary']['unique_titles']}")
    print(f"ok:              {ok_count}")
    print(f"missing:         {len(missing)}")
    print(f"disambiguation:  {len(disambiguation)}")
    print(f"redirect_ok:     {len(redirect_ok)}")
    print(f"duplicates:      {len(duplicates)}")
    print(f"all_ok:          {ok_count}")
    if missing:
        print("missing titles:", ", ".join(missing[:20]))
    if disambiguation:
        print("disambiguation titles:", ", ".join(disambiguation[:20]))
    if duplicates:
        print("duplicate titles:", ", ".join(list(duplicates)[:20]))
    print(f"\nReport written to: {REPORT_PATH}")

    if args.strict and (missing or disambiguation or duplicates):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
