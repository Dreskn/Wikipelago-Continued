#!/usr/bin/env python3
"""Enrich entertainment pool from WikiProject Popular pages.

Rules:
- Max 500 titles per category (keep existing; add until cap).
- New titles must have daily_avg >= 40% of mean(top-10 daily_avg) on the
  merged Popular-pages list for that category.
- Skip lists/outlines/meta, disambiguations, redirects-to-bad, and titles that
  fail the world's usable-title filters.
"""
from __future__ import annotations

import ast
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
POOL_PATH = ROOT / "APWorldSource" / "wikipelago" / "entertainment_articles.py"
OPTIONS_PATH = ROOT / "APWorldSource" / "wikipelago" / "Options.py"
REPORT_PATH = ROOT / "pool_enrichment_report.json"

API = "https://en.wikipedia.org/w/api.php"
UA = "WikipelagoPoolEnricher/1.0 (https://github.com/Dreskn/Wikipelago-Continued)"
MAX_PER_CATEGORY = 500
TOP_N_FOR_FLOOR = 10
FLOOR_FRACTION = 0.40

# Game category -> one or more Popular pages report titles
CATEGORY_SOURCES: dict[str, list[str]] = {
    "video_games": ["Wikipedia:WikiProject Video games/Popular pages"],
    "board_games": ["Wikipedia:WikiProject Board and table games/Popular pages"],
    "movies": ["Wikipedia:WikiProject Film/Popular pages"],
    "tv_shows": ["Wikipedia:WikiProject Television/Popular pages"],
    "anime_manga": ["Wikipedia:WikiProject Anime and manga/Popular pages"],
    "sports": ["Wikipedia:WikiProject Sports/Popular pages"],
    "food_cuisine": ["Wikipedia:WikiProject Food and drink/Popular pages"],
    "history": ["Wikipedia:WikiProject History/Popular pages"],
    "geography": ["Wikipedia:WikiProject Geography/Popular pages"],
    "technology": [
        "Wikipedia:WikiProject Computing/Popular pages",
        "Wikipedia:WikiProject Internet/Popular pages",
    ],
    "science_space": [
        "Wikipedia:WikiProject Astronomy/Popular pages",
        "Wikipedia:WikiProject Physics/Popular pages",
        "Wikipedia:WikiProject Spaceflight/Popular pages",
    ],
    "art_literature": [
        "Wikipedia:WikiProject Literature/Popular pages",
        "Wikipedia:WikiProject Novels/Popular pages",
        "Wikipedia:WikiProject Visual arts/Popular pages",
    ],
    # Mythology has no Popular pages report; Folklore is the closest clean list.
    # (Classical Greece and Rome is too broad — emperors/countries pollute the pool.)
    "mythology_folklore": [
        "Wikipedia:WikiProject Folklore/Popular pages",
    ],
    "music": [
        # WikiProject Music/Popular pages 404s; use these instead.
        "Wikipedia:WikiProject Musicians/Popular pages",
        "Wikipedia:WikiProject Albums/Popular pages",
        "Wikipedia:WikiProject Songs/Popular pages",
    ],
}

# Mirror of world usable-title filters (keep in sync with __init__.py).
BANNED_TITLE_KEYWORDS = (
    "rifle", "pistol", "shotgun", "revolver", "machine gun", "submachine gun",
    "discography", "president", "prime minister", "king of",
    "queen of", "emperor", "sultan", "chancellor", "chemistry", "chemical",
    "compound", "acid", "molecule", "molecular", "atom", "isotope", "reaction",
    "periodic table", "organic chemistry", "inorganic chemistry",
)
BANNED_TITLE_SUFFIXES = (
    "(programming language)", "(operating system)", "(software)", "(computer)",
)
BANNED_EXACT_TITLES = {
    "George Washington", "Abraham Lincoln", "Theodore Roosevelt",
    "Franklin D. Roosevelt", "John F. Kennedy", "Winston Churchill",
    "Napoleon", "Julius Caesar", "Cleopatra", "Genghis Khan", "Alexander the Great",
}

# Skip adult/NSFW topics so enrich runs do not re-add them.
NSFW_BLOCKLIST_SUBSTRINGS = (
    "hentai",
    "nhentai",
    "pornography",
    "rule 34",
    ".xxx",
)
NSFW_BLOCKLIST_EXACT = {
    "bonnie blue",
}


def is_nsfw_blocked(title: str) -> bool:
    lowered = title.lower().strip()
    if lowered in NSFW_BLOCKLIST_EXACT:
        return True
    return any(s in lowered for s in NSFW_BLOCKLIST_SUBSTRINGS)



def api_get(params: dict) -> dict:
    params = {**params, "format": "json"}
    url = f"{API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def load_pool() -> list[tuple[str, str]]:
    text = POOL_PATH.read_text(encoding="utf-8-sig")
    mod = ast.parse(text)
    for node in mod.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "ENTERTAINMENT_ARTICLE_POOL":
                return [tuple(x) for x in ast.literal_eval(node.value)]
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "ENTERTAINMENT_ARTICLE_POOL":
                    return [tuple(x) for x in ast.literal_eval(node.value)]
    raise KeyError("ENTERTAINMENT_ARTICLE_POOL")


class PopularTableParser(HTMLParser):
    """Extract (title, daily_avg) from Community Tech Popular pages HTML tables."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[tuple[str, int]] = []
        self._in_table = False
        self._in_tr = False
        self._in_td = False
        self._in_th = False
        self._in_a = False
        self._td_index = -1
        self._row_cells: list[str] = []
        self._cell_text = ""
        self._cell_link: str | None = None
        self._header_mode = False
        self._col_title: int | None = None
        self._col_daily: int | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_d = dict(attrs)
        if tag == "table" and "wikitable" in (attrs_d.get("class") or ""):
            self._in_table = True
            self._header_mode = True
            self._col_title = None
            self._col_daily = None
        elif self._in_table and tag == "tr":
            self._in_tr = True
            self._td_index = -1
            self._row_cells = []
            self._row_links: list[str | None] = []
        elif self._in_tr and tag in ("td", "th"):
            self._in_td = tag == "td"
            self._in_th = tag == "th"
            self._td_index += 1
            self._cell_text = ""
            self._cell_link = None
        elif self._in_tr and tag == "a" and (self._in_td or self._in_th):
            href = attrs_d.get("href") or ""
            title = attrs_d.get("title")
            if title and not href.startswith("/wiki/Wikipedia:") and "/wiki/" in href:
                # Prefer first article link in the cell.
                if self._cell_link is None and not title.startswith(
                    ("Wikipedia:", "Category:", "Template:", "Help:", "Portal:", "Talk:", "User:")
                ):
                    # Decode underscores later from title attribute (already spaces).
                    self._cell_link = title

    def handle_endtag(self, tag: str) -> None:
        if tag == "table" and self._in_table:
            self._in_table = False
        elif self._in_table and tag == "tr" and self._in_tr:
            self._in_tr = False
            if self._header_mode and (self._in_th or self._row_cells):
                # Determine columns from header labels.
                headers = [c.lower().strip() for c in self._row_cells]
                for i, h in enumerate(headers):
                    if "page title" in h or h == "page" or h.startswith("page title"):
                        self._col_title = i
                    if "daily" in h:
                        self._col_daily = i
                # Fallback common layout: Rank | Page title | Views | Daily average | ...
                if self._col_title is None:
                    self._col_title = 1 if len(headers) > 1 else 0
                if self._col_daily is None:
                    self._col_daily = 3 if len(headers) > 3 else (len(headers) - 1 if headers else 0)
                self._header_mode = False
            elif not self._header_mode and self._row_cells:
                ti = self._col_title if self._col_title is not None else 1
                di = self._col_daily if self._col_daily is not None else 3
                if ti < len(self._row_links) and self._row_links[ti]:
                    title = self._row_links[ti]
                elif ti < len(self._row_cells):
                    title = self._row_cells[ti].strip()
                else:
                    title = ""
                daily_raw = self._row_cells[di] if di < len(self._row_cells) else ""
                daily = _parse_int(daily_raw)
                if title and daily is not None:
                    self.rows.append((title, daily))
        elif tag in ("td", "th") and (self._in_td or self._in_th):
            self._row_cells.append(self._cell_text.strip())
            if not hasattr(self, "_row_links"):
                self._row_links = []
            # pad links list
            while len(getattr(self, "_row_links", [])) < self._td_index:
                self._row_links.append(None)
            if len(self._row_links) == self._td_index:
                self._row_links.append(self._cell_link)
            else:
                self._row_links[self._td_index] = self._cell_link
            self._in_td = False
            self._in_th = False

    def handle_data(self, data: str) -> None:
        if self._in_td or self._in_th:
            self._cell_text += data


def _parse_int(text: str) -> int | None:
    cleaned = re.sub(r"[^\d]", "", text or "")
    if not cleaned:
        return None
    try:
        return int(cleaned)
    except ValueError:
        return None


def fetch_popular_rows(page_title: str) -> list[tuple[str, int]]:
    data = api_get({
        "action": "parse",
        "page": page_title,
        "prop": "text",
        "disablelimitreport": "1",
        "disableeditsection": "1",
    })
    if "error" in data:
        raise RuntimeError(f"{page_title}: {data['error']}")
    html = data["parse"]["text"]["*"]
    parser = PopularTableParser()
    parser.feed(html)
    # Deduplicate within page keeping first (highest rank)
    seen: set[str] = set()
    out: list[tuple[str, int]] = []
    for title, daily in parser.rows:
        if title in seen:
            continue
        seen.add(title)
        out.append((title, daily))
    return out


def is_reasonable_title(title: str) -> bool:
    if len(title) < 3 or len(title) > 120:
        return False
    if "$" in title:
        return False
    if not re.search(r"[A-Za-z]", title):
        return False
    if re.search(r"^[^A-Za-z0-9]+$", title):
        return False
    return True


def looks_common_knowledge(title: str) -> bool:
    lowered = title.lower().strip()
    if title in BANNED_EXACT_TITLES:
        return False
    if lowered.startswith((
        "list of ", "outline of ", "timeline of ", "index of ",
        "category:", "template:", "help:", "portal:", "wikipedia:",
        "talk:", "user:", "file:", "draft:",
    )):
        return False
    if any(keyword in lowered for keyword in BANNED_TITLE_KEYWORDS):
        return False
    if any(lowered.endswith(suffix) for suffix in BANNED_TITLE_SUFFIXES):
        return False
    if any(ch in title for ch in ('"', "$", "%", "@", "#")):
        return False
    if title.count(",") > 1:
        return False
    if re.search(r"^\d", title):
        return False
    if re.search(r"\((disambiguation|magazine|journal)\)$", lowered):
        return False
    if len(title.split()) > 6:
        return False
    if re.search(r"[A-Za-z].*\d.*\d.*\d", title):
        return False
    return True


def passes_skip_filters(title: str) -> bool:
    return (
        is_reasonable_title(title)
        and looks_common_knowledge(title)
        and not is_nsfw_blocked(title)
    )


def passes_category_coherence(title: str, cat: str) -> bool:
    """Drop obvious cross-scope bleed from broad WikiProject reports."""
    low = title.lower()
    if cat == "video_games":
        if "(film)" in low or "(tv series)" in low or "television series" in low:
            return False
        if low.endswith(" (franchise)") and "mario" not in low and "zelda" not in low and "pokemon" not in low and "pokémon" not in low:
            # keep most franchises; still allow through — no extra block
            pass
    if cat == "movies" and ("(video game)" in low or "(board game)" in low):
        return False
    if cat == "tv_shows" and ("(video game)" in low or "(film)" in low):
        return False
    if cat == "board_games" and ("(video game)" in low or "(film)" in low):
        return False
    return True


def classify_titles(titles: list[str]) -> dict[str, dict]:
    """Return status per title: ok / missing / disambiguation / redirect_ok(+canonical)."""
    results: dict[str, dict] = {}
    for i in range(0, len(titles), 50):
        batch = titles[i : i + 50]
        params = {
            "action": "query",
            "redirects": "1",
            "prop": "info|pageprops",
            "ppprop": "disambiguation",
            "titles": "|".join(batch),
        }
        # Preserve order mapping via redirects/normalized
        attempt = 0
        while True:
            attempt += 1
            try:
                data = api_get(params)
                break
            except urllib.error.HTTPError as e:
                if attempt >= 5:
                    raise
                time.sleep(min(2 ** attempt, 20))
                print(f"  retry batch after HTTP {e.code}")
        query = data.get("query") or {}
        redirects = {(r["from"]): r["to"] for r in query.get("redirects") or []}
        normalized = {(n["from"]): n["to"] for n in query.get("normalized") or []}
        pages = list((query.get("pages") or {}).values())
        by_title = {p.get("title"): p for p in pages}

        for original in batch:
            cur = normalized.get(original, original)
            followed = False
            if cur in redirects:
                cur = redirects[cur]
                followed = True
            # sometimes chain
            if cur in redirects:
                cur = redirects[cur]
                followed = True
            page = by_title.get(cur)
            if page is None:
                # try match missing
                results[original] = {"status": "missing"}
                continue
            if page.get("missing") is not None or page.get("invalid") is not None:
                results[original] = {"status": "missing"}
                continue
            pp = page.get("pageprops") or {}
            if "disambiguation" in pp:
                results[original] = {"status": "disambiguation", "canonical": page.get("title")}
                continue
            results[original] = {
                "status": "redirect_ok" if followed else "ok",
                "canonical": page.get("title"),
            }
        time.sleep(0.05)
    return results


def floor_from_top10(rows: list[tuple[str, int]]) -> float:
    """40% of the 10th-ranked page's daily visits (not the top-10 mean).

    Mean is skewed by viral outliers (e.g. The Backrooms). Using the 10th entry
    matches the intended Folklore sanity check: Bigfoot @2228 → floor 891.
    """
    if not rows:
        return float("inf")
    idx = min(TOP_N_FOR_FLOOR, len(rows)) - 1
    return FLOOR_FRACTION * rows[idx][1]


def write_pool(entries: list[tuple[str, str]]) -> None:
    lines = [
        '"""Curated Wikipelago article pool: (Wikipedia title, category)."""',
        "",
        "ENTERTAINMENT_ARTICLE_POOL: list[tuple[str, str]] = [",
    ]
    for title, topic in entries:
        lines.append(f"    ({title!r}, {topic!r}),")
    lines.append("]")
    lines.append("")
    POOL_PATH.write_text("\n".join(lines), encoding="utf-8")


def update_range_end(usable: int) -> int:
    cap = usable // 2
    text = OPTIONS_PATH.read_text(encoding="utf-8")
    text2, n1 = re.subn(
        r"(class CheckCount\(Range\):.*?range_end = )\d+",
        rf"\g<1>{cap}",
        text,
        count=1,
        flags=re.S,
    )
    text3, n2 = re.subn(
        r"(class RequiredFragments\(Range\):.*?range_end = )\d+",
        rf"\g<1>{cap}",
        text2,
        count=1,
        flags=re.S,
    )
    if n1 != 1 or n2 != 1:
        raise RuntimeError(f"Failed to patch Options range_end (n1={n1}, n2={n2})")
    OPTIONS_PATH.write_text(text3, encoding="utf-8")
    return cap


def main() -> None:
    existing = load_pool()
    by_cat: dict[str, list[str]] = defaultdict(list)
    title_to_cat: dict[str, str] = {}
    for title, cat in existing:
        by_cat[cat].append(title)
        title_to_cat[title] = cat

    before_counts = {c: len(v) for c, v in by_cat.items()}
    report: dict = {"categories": {}, "added_total": 0, "rules": {
        "max_per_category": MAX_PER_CATEGORY,
        "floor": "0.4 * daily_avg of the 10th-ranked Popular pages entry",
        "floor_fraction": FLOOR_FRACTION,
    }}

    added_entries: list[tuple[str, str]] = []

    for cat, sources in CATEGORY_SOURCES.items():
        print(f"\n=== {cat} ===")
        merged: dict[str, int] = {}
        source_stats = []
        for src in sources:
            print(f"  fetch {src}")
            try:
                rows = fetch_popular_rows(src)
            except Exception as e:
                print(f"  ERROR {src}: {e}")
                source_stats.append({"source": src, "error": str(e), "rows": 0})
                time.sleep(0.2)
                continue
            print(f"  parsed {len(rows)} rows")
            source_stats.append({"source": src, "rows": len(rows)})
            for title, daily in rows:
                prev = merged.get(title)
                if prev is None or daily > prev:
                    merged[title] = daily
            time.sleep(0.3)

        ranked = sorted(merged.items(), key=lambda kv: kv[1], reverse=True)
        floor = floor_from_top10(ranked)
        top10 = ranked[:10]
        tenth_daily = ranked[min(9, len(ranked) - 1)][1] if ranked else None
        print(f"  merged={len(ranked)} 10th_daily={tenth_daily} floor={floor:.1f}")

        # Candidates: meet floor, pass skip filters, not already in ANY category
        candidates: list[tuple[str, int]] = []
        skipped = Counter()
        for title, daily in ranked:
            if daily < floor:
                skipped["below_floor"] += 1
                continue
            if not passes_skip_filters(title):
                skipped["skip_filters"] += 1
                continue
            if not passes_category_coherence(title, cat):
                skipped["category_coherence"] += 1
                continue
            if title in title_to_cat:
                skipped["already_in_pool"] += 1
                continue
            candidates.append((title, daily))

        slots = max(0, MAX_PER_CATEGORY - len(by_cat.get(cat, [])))
        provisional = candidates[: max(slots * 3, slots)]  # validate extra in case of dabs
        print(f"  candidates={len(candidates)} slots={slots} validating={len(provisional)}")

        accepted: list[tuple[str, str]] = []
        if provisional and slots > 0:
            statuses = classify_titles([t for t, _ in provisional])
            for title, daily in provisional:
                if len(accepted) >= slots:
                    break
                st = statuses.get(title) or {"status": "missing"}
                status = st["status"]
                if status == "missing":
                    skipped["missing"] += 1
                    continue
                if status == "disambiguation":
                    skipped["disambiguation"] += 1
                    continue
                canonical = st.get("canonical") or title
                if not passes_skip_filters(canonical):
                    skipped["canonical_fail_filters"] += 1
                    continue
                if not passes_category_coherence(canonical, cat):
                    skipped["canonical_coherence"] += 1
                    continue
                if canonical in title_to_cat:
                    skipped["canonical_already_in_pool"] += 1
                    continue
                # Avoid adding same canonical twice in this batch
                if any(a[0] == canonical for a in accepted):
                    skipped["dup_in_batch"] += 1
                    continue
                accepted.append((canonical, cat))
                title_to_cat[canonical] = cat
                by_cat[cat].append(canonical)

        added_entries.extend(accepted)
        report["categories"][cat] = {
            "sources": source_stats,
            "merged_rows": len(ranked),
            "top10": [{"title": t, "daily": d} for t, d in top10],
            "tenth_daily": tenth_daily,
            "floor_daily": round(floor, 2),
            "before": before_counts.get(cat, 0),
            "added": len(accepted),
            "after": len(by_cat.get(cat, [])),
            "skipped": dict(skipped),
            "added_titles": [t for t, _ in accepted],
            "last_added": accepted[-1] if accepted else None,
        }
        print(f"  added {len(accepted)} -> {len(by_cat.get(cat, []))}")

    # Rebuild pool: keep original order, append new titles at end grouped by discovery order
    new_pool = list(existing) + added_entries
    # Deduplicate by title (keep first)
    seen: set[str] = set()
    deduped: list[tuple[str, str]] = []
    for title, cat in new_pool:
        if title in seen:
            continue
        seen.add(title)
        deduped.append((title, cat))

    write_pool(deduped)

    # Usable count with same filters
    usable = sum(1 for t, _ in deduped if passes_skip_filters(t))
    range_end = update_range_end(usable)

    after_counts = Counter(c for _, c in deduped)
    report["added_total"] = len(added_entries)
    report["pool_size"] = len(deduped)
    report["usable"] = usable
    report["range_end"] = range_end
    report["after_counts"] = dict(after_counts)
    report["before_counts"] = before_counts

    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n=== SUMMARY ===")
    print(f"added_total={len(added_entries)} pool={len(deduped)} usable={usable} range_end={range_end}")
    for cat in CATEGORY_SOURCES:
        b = before_counts.get(cat, 0)
        a = after_counts.get(cat, 0)
        floor = report["categories"][cat]["floor_daily"]
        print(f"  {cat}: {b} -> {a} (floor {floor})")
    print(f"wrote {POOL_PATH}")
    print(f"wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
