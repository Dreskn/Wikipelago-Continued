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

USER_AGENT = "WikipelagoPoolValidator/1.2 (https://github.com/Dreskn/Wikipelago-Continued)"
# Gentler pacing for --lang all in CI (Wikipedia rate-limits aggressive clients).
BATCH_SIZE = 40
SLEEP_SECONDS = 0.35
MAX_RETRIES = 10
BACKOFF_BASE_SECONDS = 2.0
BACKOFF_MAX_SECONDS = 120.0
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


def _retry_after_seconds(error: urllib.error.HTTPError, attempt: int) -> float:
    """Backoff delay: honor Retry-After when present, else exponential with cap."""
    header = error.headers.get("Retry-After") if error.headers else None
    if header:
        try:
            return min(BACKOFF_MAX_SECONDS, max(1.0, float(header)))
        except ValueError:
            pass
    # attempt 1 → 2s, 2 → 4s, 3 → 8s, … capped
    return min(BACKOFF_MAX_SECONDS, BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)))


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
    last_error: BaseException | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_error = e
            retryable = e.code == 429 or 500 <= e.code < 600
            if not retryable or attempt >= MAX_RETRIES:
                raise
            delay = _retry_after_seconds(e, attempt)
            print(
                f"[{lang}] HTTP {e.code} on batch ({attempt}/{MAX_RETRIES}); "
                f"sleeping {delay:.1f}s",
                flush=True,
            )
            time.sleep(delay)
        except urllib.error.URLError as e:
            last_error = e
            if attempt >= MAX_RETRIES:
                raise
            delay = min(BACKOFF_MAX_SECONDS, BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)))
            print(
                f"[{lang}] network error on batch ({attempt}/{MAX_RETRIES}): {e.reason!r}; "
                f"sleeping {delay:.1f}s",
                flush=True,
            )
            time.sleep(delay)
    assert last_error is not None
    raise last_error


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


def pool_path(lang: str) -> Path:
    return DATA_DIR / f"pool_{lang}.json"


def apply_removals(lang: str, titles_to_remove: set[str]) -> dict:
    """Drop missing/disambiguation titles from the runtime pool JSON. Returns stats."""
    path = pool_path(lang)
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload.get("entries") or []
    before = len(entries)
    kept = [
        entry
        for entry in entries
        if str(entry.get("title") or "").strip() not in titles_to_remove
    ]
    removed = before - len(kept)
    if removed:
        payload["entries"] = kept
        payload["count"] = len(kept)
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return {"before": before, "after": len(kept), "removed": removed}


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
        data = query_batch(lang, batch)
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
        "pool_file": str(pool_path(lang)),
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
    parser.add_argument(
        "--apply-removals",
        action="store_true",
        help=(
            "After validation, rewrite each pool JSON by removing titles classified "
            "as missing or disambiguation. Does not remove redirect_ok titles."
        ),
    )
    parser.add_argument(
        "--from-report",
        type=Path,
        default=None,
        help=(
            "Skip live Wikipedia queries; apply removals (and/or re-check --strict) "
            "from an existing pool_validation_report.json."
        ),
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

    if args.from_report is not None:
        report_path = args.from_report
        if not report_path.is_file():
            print(f"Report not found: {report_path}", file=sys.stderr)
            return 2
        cached = json.loads(report_path.read_text(encoding="utf-8"))
        by_lang = {r["lang"]: r for r in cached.get("reports") or []}
        for lang in langs:
            if lang not in by_lang:
                print(f"No report entry for lang={lang}", file=sys.stderr)
                return 2
            lang_reports.append(by_lang[lang])
    else:
        for lang in langs:
            report = validate_lang(lang)
            lang_reports.append(report)

    for report in lang_reports:
        lang = report["lang"]
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

        if args.apply_removals:
            drop = set(report["missing"]) | set(report["disambiguation"])
            stats = apply_removals(lang, drop)
            _safe_print(
                f"applied removals: {stats['removed']} "
                f"({stats['before']} -> {stats['after']})"
            )

    out = {
        "langs": langs,
        "reports": lang_reports,
    }
    REPORT_PATH.write_text(
        json.dumps(out, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _safe_print(f"\nReport written to: {REPORT_PATH}")

    if args.strict and failed and not args.apply_removals:
        return 1
    # After applying removals, pools should be clean; caller may re-validate.
    if args.strict and failed and args.apply_removals:
        _safe_print(
            "Removals applied; re-run without --apply-removals to confirm --strict."
        )
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
