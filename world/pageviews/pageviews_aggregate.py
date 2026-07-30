#!/usr/bin/env python3
"""Standalone test: aggregate monthly pageview tops for one or more wikis."""

from __future__ import annotations

import email.utils
import json
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

# Run sequentially; one output file per project
PROJECTS = [
    "en.wikipedia",
    "fr.wikipedia",
    "de.wikipedia",
    "es.wikipedia",
    "it.wikipedia",
    "pt.wikipedia",
    "nl.wikipedia",
    "sv.wikipedia",
    "pl.wikipedia",
]
ACCESS = "all-access"
START = date(2016, 7, 1)
END = date(2026, 6, 1)
MONTHLY_TOP_N = 1000
ELITE_TOP_N = 200
FINAL_SUM_TOP_N = 5000
SLEEP_S = 0.45
MAX_RETRIES = 8
UA = "PageviewsAggregateTest/0.1 (https://github.com/Dreskn; email@email)"
BASE = "https://wikimedia.org/api/rest_v1/metrics/pageviews/top"

# Non-article noise common across languages
SKIP_EXACT = {
    "Main Page",
    "Wikipédia:Accueil principal",
    "Wikipedia:Hauptseite",
    "Wikipedia:Portada",
    "Pagina principale",
    "Wikipédia:Página principal",
    "Hoofdpagina",
    "Portal:Huvudsida",
    "Strona główna",
}


def months_inclusive(start: date, end: date) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return out


def lang_code(project: str) -> str:
    # "fr.wikipedia" -> "fr"
    return project.split(".", 1)[0]


def should_skip(title: str) -> bool:
    if title in SKIP_EXACT:
        return True
    lower = title.lower()
    return (
        lower.startswith("special:")
        or lower.startswith("spécial:")
        or lower.startswith("spezial:")
        or lower.startswith("especial:")
        or lower.startswith("speciaal:")
        or lower.startswith("specjalna:")
        or lower.startswith("file:")
        or lower.startswith("fichier:")
        or lower.startswith("datei:")
        or lower.startswith("archivo:")
        or lower.startswith("categoria:")
        or lower.startswith("catégorie:")
        or lower.startswith("category:")
        or lower.startswith("utente:")
        or lower.startswith("utilisateur:")
        or lower.startswith("user:")
        or lower.startswith("ayuda:")
        or lower.startswith("aide:")
        or lower.startswith("help:")
    )


def _retry_after_seconds(headers) -> float:
    raw = headers.get("Retry-After")
    if not raw:
        return 5.0
    try:
        return max(5.0, float(raw))
    except ValueError:
        when = email.utils.parsedate_to_datetime(raw)
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        return max(5.0, (when - datetime.now(timezone.utc)).total_seconds())


def fetch_month_top(project: str, year: int, month: int) -> list[tuple[str, int]] | None:
    """Return rows, or None if this month has no data (HTTP 404)."""
    url = f"{BASE}/{project}/{ACCESS}/{year}/{month:02d}/all-days"
    req = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept": "application/json"}
    )
    data = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code == 404:
                return None
            if exc.code in (429, 503) and attempt < MAX_RETRIES:
                wait = _retry_after_seconds(exc.headers)
                print(f"  {project} {year}-{month:02d}: HTTP {exc.code}, wait {wait:.0f}s (try {attempt})")
                time.sleep(wait)
                continue
            raise RuntimeError(f"{year}-{month:02d}: HTTP {exc.code} {body[:200]}") from exc
    if data is None:
        raise RuntimeError(f"{year}-{month:02d}: exhausted retries")

    items = data["items"][0]["articles"]
    rows: list[tuple[str, int]] = []
    for row in items:
        title = str(row.get("article") or "").replace("_", " ")
        views = int(row.get("views") or 0)
        if not title or views <= 0 or should_skip(title):
            continue
        rows.append((title, views))
    return rows


def run_project(project: str, months: list[tuple[int, int]]) -> Path:
    sums: dict[str, int] = defaultdict(int)
    elite: set[str] = set()
    errors: list[str] = []
    skipped: list[str] = []
    code = lang_code(project)

    print(f"\n=== {project} ({code}) — {len(months)} months {START:%Y-%m} .. {END:%Y-%m} ===")
    for i, (year, month) in enumerate(months, start=1):
        try:
            rows = fetch_month_top(project, year, month)
        except Exception as exc:
            errors.append(f"{year}-{month:02d}: {exc}")
            print(f"[{i}/{len(months)}] FAIL {year}-{month:02d}: {exc}")
            time.sleep(1.0)
            continue

        if rows is None:
            skipped.append(f"{year}-{month:02d}")
            print(f"[{i}/{len(months)}] SKIP {year}-{month:02d}: no data (404)")
            time.sleep(SLEEP_S)
            continue

        for rank, (title, views) in enumerate(rows[:MONTHLY_TOP_N], start=1):
            sums[title] += views
            if rank <= ELITE_TOP_N:
                elite.add(title)

        print(f"[{i}/{len(months)}] OK {year}-{month:02d} rows={len(rows)} unique={len(sums)}")
        time.sleep(SLEEP_S)

    by_sum = sorted(sums.items(), key=lambda kv: (-kv[1], kv[0]))
    top_by_sum = {title for title, _ in by_sum[:FINAL_SUM_TOP_N]}
    final = sorted(top_by_sum | elite)

    out = {
        "project": project,
        "lang": code,
        "start_month": f"{START:%Y-%m}",
        "end_month": f"{END:%Y-%m}",
        "months_requested": len(months),
        "months_skipped_404": skipped,
        "unique_seen_in_monthly_tops": len(sums),
        "top_by_sum_count": len(top_by_sum),
        "elite_any_month_count": len(elite),
        "final_union_count": len(final),
        "errors": errors,
        "top_by_sum": [
            {"title": t, "views_summed_from_monthly_tops": v}
            for t, v in by_sum[:FINAL_SUM_TOP_N]
        ],
        "final_titles_sorted": final,
    }

    path = Path(__file__).with_name(f"pageviews_aggregate_{code}.json")
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {path} final_union={len(final)} errors={len(errors)} skipped_404={len(skipped)}")
    return path


def main() -> None:
    months = months_inclusive(START, END)
    written: list[Path] = []
    for project in PROJECTS:
        written.append(run_project(project, months))
    print("\nDone. Files:")
    for p in written:
        print(f"  {p}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FATAL: {exc}")
        raise
    finally:
        input("Press Enter to close…")