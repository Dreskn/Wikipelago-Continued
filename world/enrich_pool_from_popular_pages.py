#!/usr/bin/env python3
"""Enrich annotated multi-tag pools from EN WikiProject Popular pages.

Rules:
- Max 500 titles per category (count = entries that already carry the tag).
- Keep titles with daily_avg >= 20% of the 20th-ranked page's daily_avg on
  the merged Popular-pages list for that category.
- Existing pool titles above the floor get the seed category tag if missing.
- New titles are Wikidata-annotated, then the seed category is unioned in.
- New EN QIDs propagate to other language pools via sitelinks when present.
- Skip lists/outlines/meta, disambiguations, and unusable titles.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PAGEVIEWS = ROOT / "pageviews"
ANNOTATED_DIR = PAGEVIEWS / "annotated"
REPORT_PATH = ROOT / "pool_enrichment_report.json"

sys.path.insert(0, str(PAGEVIEWS))
import annotate_pools as ap  # noqa: E402

API = "https://en.wikipedia.org/w/api.php"
UA = "WikipelagoPoolEnricher/1.0 (https://github.com/Dreskn/Wikipelago-Continued)"
MAX_PER_CATEGORY = 500
# Floor = FLOOR_FRACTION × daily_avg of the FLOOR_RANK-th page (1-based).
FLOOR_RANK = 20
FLOOR_FRACTION = 0.20
LANGS = ("en", "fr", "de", "es", "it", "pt", "nl", "sv", "pl")

CATEGORY_SOURCES: dict[str, list[str]] = {
    "video_games": ["Wikipedia:WikiProject Video games/Popular pages"],
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
    "mythology_folklore": [
        "Wikipedia:WikiProject Folklore/Popular pages",
    ],
    "music": [
        "Wikipedia:WikiProject Musicians/Popular pages",
        "Wikipedia:WikiProject Albums/Popular pages",
        "Wikipedia:WikiProject Songs/Popular pages",
    ],
}

# Mirror of world usable-title filters (keep in sync with __init__.py).
BANNED_TITLE_KEYWORDS = (
    "rifle",
    "pistol",
    "shotgun",
    "revolver",
    "machine gun",
    "submachine gun",
    "discography",
    "chemistry",
    "chemical",
    "compound",
    "acid",
    "molecule",
    "molecular",
    "atom",
    "isotope",
    "reaction",
    "periodic table",
    "organic chemistry",
    "inorganic chemistry",
)
BANNED_TITLE_SUFFIXES = (
    "(programming language)",
    "(operating system)",
    "(software)",
    "(computer)",
)
BANNED_EXACT_TITLES = {
    "George Washington",
    "Abraham Lincoln",
    "Theodore Roosevelt",
    "Franklin D. Roosevelt",
    "John F. Kennedy",
    "Winston Churchill",
    "Napoleon",
    "Julius Caesar",
    "Cleopatra",
    "Genghis Khan",
    "Alexander the Great",
}

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


class PopularTableParser(HTMLParser):
    """Extract (title, daily_avg) from Community Tech Popular pages HTML tables."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[tuple[str, int]] = []
        self._in_table = False
        self._in_tr = False
        self._in_td = False
        self._in_th = False
        self._td_index = -1
        self._row_cells: list[str] = []
        self._cell_text = ""
        self._cell_link: str | None = None
        self._header_mode = False
        self._col_title: int | None = None
        self._col_daily: int | None = None
        self._row_links: list[str | None] = []

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
            self._row_links = []
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
                if self._cell_link is None and not title.startswith(
                    ("Wikipedia:", "Category:", "Template:", "Help:", "Portal:", "Talk:", "User:")
                ):
                    self._cell_link = title

    def handle_endtag(self, tag: str) -> None:
        if tag == "table" and self._in_table:
            self._in_table = False
        elif self._in_table and tag == "tr" and self._in_tr:
            self._in_tr = False
            if self._header_mode and (self._in_th or self._row_cells):
                headers = [c.lower().strip() for c in self._row_cells]
                for i, h in enumerate(headers):
                    if "page title" in h or h == "page" or h.startswith("page title"):
                        self._col_title = i
                    if "daily" in h:
                        self._col_daily = i
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
            while len(self._row_links) < self._td_index:
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
    data = api_get(
        {
            "action": "parse",
            "page": page_title,
            "prop": "text",
            "disablelimitreport": "1",
            "disableeditsection": "1",
        }
    )
    if "error" in data:
        raise RuntimeError(f"{page_title}: {data['error']}")
    html = data["parse"]["text"]["*"]
    parser = PopularTableParser()
    parser.feed(html)
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
    if lowered.startswith(
        (
            "list of ",
            "outline of ",
            "timeline of ",
            "index of ",
            "category:",
            "template:",
            "help:",
            "portal:",
            "wikipedia:",
            "talk:",
            "user:",
            "file:",
            "draft:",
        )
    ):
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
    if cat == "movies" and ("(video game)" in low or "(board game)" in low):
        return False
    if cat == "tv_shows" and ("(video game)" in low or "(film)" in low):
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
        attempt = 0
        while True:
            attempt += 1
            try:
                data = api_get(params)
                break
            except urllib.error.HTTPError as e:
                if attempt >= 5:
                    raise
                time.sleep(min(2**attempt, 20))
                print(f"  retry batch after HTTP {e.code}")
        query = data.get("query") or {}
        redirects = {r["from"]: r["to"] for r in query.get("redirects") or []}
        normalized = {n["from"]: n["to"] for n in query.get("normalized") or []}
        pages = list((query.get("pages") or {}).values())
        by_title = {p.get("title"): p for p in pages}

        for original in batch:
            cur = normalized.get(original, original)
            followed = False
            if cur in redirects:
                cur = redirects[cur]
                followed = True
            if cur in redirects:
                cur = redirects[cur]
                followed = True
            page = by_title.get(cur)
            if page is None:
                results[original] = {"status": "missing"}
                continue
            if page.get("missing") is not None or page.get("invalid") is not None:
                results[original] = {"status": "missing"}
                continue
            pp = page.get("pageprops") or {}
            if "disambiguation" in pp:
                results[original] = {
                    "status": "disambiguation",
                    "canonical": page.get("title"),
                }
                continue
            results[original] = {
                "status": "redirect_ok" if followed else "ok",
                "canonical": page.get("title"),
            }
        time.sleep(0.05)
    return results


def floor_from_rank(rows: list[tuple[str, int]]) -> tuple[float, int | None]:
    """FLOOR_FRACTION × daily_avg of the FLOOR_RANK-th page (1-based)."""
    if not rows:
        return float("inf"), None
    idx = min(FLOOR_RANK, len(rows)) - 1
    rank_daily = rows[idx][1]
    return FLOOR_FRACTION * rank_daily, rank_daily


def annotated_path(lang: str) -> Path:
    return ANNOTATED_DIR / f"pool_annotated_{lang}.json"


def load_pools() -> dict[str, dict]:
    pools: dict[str, dict] = {}
    for lang in LANGS:
        path = annotated_path(lang)
        if not path.is_file():
            raise FileNotFoundError(f"Missing annotated pool: {path}")
        pools[lang] = json.loads(path.read_text(encoding="utf-8"))
    return pools


def save_pools(pools: dict[str, dict]) -> None:
    for lang, data in pools.items():
        path = annotated_path(lang)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def title_index(entries: list[dict]) -> dict[str, int]:
    idx: dict[str, int] = {}
    for i, row in enumerate(entries):
        for key in ("canonical_title", "title"):
            t = (row.get(key) or "").strip()
            if t:
                idx[ap.norm_title(t)] = i
    return idx


def count_with_tag(entries: list[dict], cat: str) -> int:
    return sum(1 for e in entries if cat in (e.get("tags") or []))


def union_tags(existing: list[str], seed: str) -> list[str]:
    tags = set(existing or [])
    tags.discard(ap.MISC_TAG)
    tags.add(seed)
    return ap.finalize_tags(tags)


def annotate_en_titles(
    titles: list[str],
    store: ap.AnnotationStore,
    subclass: ap.ClaimParentIndex,
    taxon_index: ap.ClaimParentIndex,
) -> dict[str, dict]:
    """Resolve + classify EN titles. Returns canonical -> {qid, tags, sensitive, sitelinks}."""
    if not titles:
        return {}
    resolved, canonical = ap.resolve_titles(titles, "en")
    entities: dict[str, dict] = {}
    for t in titles:
        qid, ent = resolved.get(t, (None, None))
        if qid and ent is not None and qid not in store.by_qid:
            entities[qid] = ent
        elif qid and ent is not None:
            store._index_sitelinks(qid, ap.sitelinks_map(ent))
    ap.classify_entities(entities, subclass, taxon_index, store)
    store.save(ap.CACHE_PATH)

    out: dict[str, dict] = {}
    for t in titles:
        qid, ent = resolved.get(t, (None, None))
        canon = canonical.get(t, t)
        if not qid:
            out[canon] = {
                "qid": None,
                "tags": [ap.MISC_TAG],
                "sensitive": False,
                "sitelinks": {},
                "note": "no_wikidata",
            }
            continue
        ann = store.get(qid) or {}
        sl = dict(ann.get("sitelinks") or {})
        if ent is not None:
            sl.update(ap.sitelinks_map(ent))
        out[canon] = {
            "qid": qid,
            "tags": list(ann.get("tags") or [ap.MISC_TAG]),
            "sensitive": bool(ann.get("sensitive")),
            "sitelinks": sl,
        }
    return out


def add_or_tag_entry(
    pools: dict[str, dict],
    lang: str,
    title: str,
    qid: str | None,
    tags: list[str],
    sensitive: bool,
    note: str | None = None,
) -> str:
    """Add title or union tags. Returns 'added' | 'tagged' | 'noop'."""
    entries = pools[lang]["entries"]
    idx = title_index(entries)
    key = ap.norm_title(title)
    if key in idx:
        row = entries[idx[key]]
        before = list(row.get("tags") or [])
        after = ap.finalize_tags(set(before) | set(tags))
        if after == before and (not qid or row.get("qid") == qid):
            return "noop"
        row["tags"] = after
        if qid and not row.get("qid"):
            row["qid"] = qid
        if sensitive:
            row["sensitive"] = True
        return "tagged"

    row = {
        "title": title,
        "canonical_title": title,
        "qid": qid,
        "tags": list(tags),
        "sensitive": bool(sensitive),
    }
    if note:
        row["note"] = note
    entries.append(row)
    return "added"


def propagate_to_other_langs(
    pools: dict[str, dict],
    qid: str | None,
    sitelinks: dict[str, str],
    tags: list[str],
    sensitive: bool,
) -> dict[str, str]:
    """Add/tag sitelink titles on non-EN pools. Returns lang -> action."""
    actions: dict[str, str] = {}
    if not qid:
        return actions
    for lang in LANGS:
        if lang == "en":
            continue
        site = f"{lang}wiki"
        local = sitelinks.get(site)
        if not local:
            continue
        if not passes_skip_filters(local):
            actions[lang] = "skipped_filters"
            continue
        actions[lang] = add_or_tag_entry(
            pools,
            lang,
            local,
            qid,
            tags,
            sensitive,
            note="popular_pages_sitelink",
        )
    return actions


def refresh_pool_stats(data: dict) -> None:
    entries = data.get("entries") or []
    tag_counts: Counter[str] = Counter()
    sens = 0
    misc = 0
    no_qid = 0
    for e in entries:
        tags = e.get("tags") or [ap.MISC_TAG]
        for t in tags:
            tag_counts[t] += 1
        if e.get("sensitive"):
            sens += 1
        if tags == [ap.MISC_TAG]:
            misc += 1
        if not e.get("qid"):
            no_qid += 1
    data["annotated_count"] = len(entries)
    data["pool_size"] = len(entries)
    data["miscellaneous_only"] = misc
    data["sensitive_flagged"] = sens
    data["no_qid"] = no_qid
    data["tag_counts"] = dict(tag_counts.most_common())


def main() -> None:
    pools = load_pools()
    en_entries = pools["en"]["entries"]
    before_counts = {cat: count_with_tag(en_entries, cat) for cat in CATEGORY_SOURCES}

    store = ap.AnnotationStore()
    store.load(ap.CACHE_PATH)
    subclass = ap.ClaimParentIndex(ap.SUBCLASS_DEPTH, "P279", "subclass")
    taxon_index = ap.ClaimParentIndex(ap.TAXON_DEPTH, "P171", "taxon")

    report: dict = {
        "rules": {
            "max_per_category": MAX_PER_CATEGORY,
            "floor": (
                f"{FLOOR_FRACTION} * daily_avg of the {FLOOR_RANK}th-ranked "
                "Popular-pages entry (merged list)"
            ),
            "floor_rank": FLOOR_RANK,
            "floor_fraction": FLOOR_FRACTION,
            "target": "annotated multi-tag pools",
        },
        "categories": {},
        "added_total_en": 0,
        "tagged_total_en": 0,
    }

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
                source_stats.append({"source": src, "error": str(e), "rows": 0, "ok": False})
                time.sleep(0.2)
                continue
            print(f"  parsed {len(rows)} rows")
            source_stats.append({"source": src, "rows": len(rows), "ok": True})
            for title, daily in rows:
                prev = merged.get(title)
                if prev is None or daily > prev:
                    merged[title] = daily
            time.sleep(0.3)

        ranked = sorted(merged.items(), key=lambda kv: kv[1], reverse=True)
        floor, rank_daily = floor_from_rank(ranked)
        rank_title = ranked[min(FLOOR_RANK, len(ranked)) - 1][0] if ranked else None
        print(
            f"  merged={len(ranked)} "
            f"{FLOOR_RANK}th_daily={rank_daily} "
            f"floor={floor:.1f} ({FLOOR_FRACTION:.0%} of {FLOOR_RANK}th)"
        )

        en_idx = title_index(pools["en"]["entries"])
        current = count_with_tag(pools["en"]["entries"], cat)
        slots = max(0, MAX_PER_CATEGORY - current)
        skipped: Counter[str] = Counter()
        tag_adds: list[str] = []
        new_candidates: list[tuple[str, int]] = []

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
            key = ap.norm_title(title)
            if key in en_idx:
                row = pools["en"]["entries"][en_idx[key]]
                if cat in (row.get("tags") or []):
                    skipped["already_tagged"] += 1
                    continue
                if slots <= 0:
                    skipped["cap_reached_tag"] += 1
                    continue
                action = add_or_tag_entry(pools, "en", row.get("canonical_title") or title, row.get("qid"), [cat], bool(row.get("sensitive")))
                if action == "tagged":
                    tag_adds.append(row.get("canonical_title") or title)
                    slots -= 1
                    current += 1
                    en_idx = title_index(pools["en"]["entries"])
                else:
                    skipped["tag_noop"] += 1
                continue
            new_candidates.append((title, daily))

        provisional = new_candidates[: max(slots * 3, slots)]
        print(
            f"  above_floor_new={len(new_candidates)} "
            f"tag_adds={len(tag_adds)} slots_left={slots} validating={len(provisional)}"
        )

        accepted_new: list[str] = []
        lang_prop: Counter[str] = Counter()
        if provisional and slots > 0:
            statuses = classify_titles([t for t, _ in provisional])
            to_annotate: list[str] = []
            canon_for: dict[str, str] = {}
            for title, _daily in provisional:
                if len(to_annotate) >= slots:
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
                if ap.norm_title(canonical) in title_index(pools["en"]["entries"]):
                    # Redirect landed on an existing pool title — tag it.
                    row = pools["en"]["entries"][title_index(pools["en"]["entries"])[ap.norm_title(canonical)]]
                    if cat not in (row.get("tags") or []) and slots > 0:
                        add_or_tag_entry(
                            pools,
                            "en",
                            canonical,
                            row.get("qid"),
                            [cat],
                            bool(row.get("sensitive")),
                        )
                        tag_adds.append(canonical)
                        slots -= 1
                        current += 1
                    else:
                        skipped["canonical_already_in_pool"] += 1
                    continue
                if canonical in canon_for.values():
                    skipped["dup_in_batch"] += 1
                    continue
                canon_for[title] = canonical
                to_annotate.append(canonical)

            annotated = annotate_en_titles(to_annotate, store, subclass, taxon_index)
            for canonical in to_annotate:
                if slots <= 0:
                    break
                if ap.norm_title(canonical) in title_index(pools["en"]["entries"]):
                    skipped["race_already_in_pool"] += 1
                    continue
                meta = annotated.get(canonical) or {
                    "qid": None,
                    "tags": [ap.MISC_TAG],
                    "sensitive": False,
                    "sitelinks": {},
                }
                tags = union_tags(list(meta.get("tags") or []), cat)
                action = add_or_tag_entry(
                    pools,
                    "en",
                    canonical,
                    meta.get("qid"),
                    tags,
                    bool(meta.get("sensitive")),
                    note="popular_pages_enrich",
                )
                if action != "added":
                    skipped["add_failed"] += 1
                    continue
                accepted_new.append(canonical)
                slots -= 1
                current += 1
                prop = propagate_to_other_langs(
                    pools,
                    meta.get("qid"),
                    meta.get("sitelinks") or {},
                    tags,
                    bool(meta.get("sensitive")),
                )
                for lang, act in prop.items():
                    lang_prop[f"{lang}:{act}"] += 1

        report["categories"][cat] = {
            "sources": source_stats,
            "merged_rows": len(ranked),
            "floor_rank": FLOOR_RANK,
            "floor_rank_title": rank_title,
            "floor_rank_daily": rank_daily,
            "floor_daily": round(floor, 2) if floor != float("inf") else None,
            "top20": [{"title": t, "daily": d} for t, d in ranked[:20]],
            "before": before_counts.get(cat, 0),
            "tagged_existing": len(tag_adds),
            "added_new": len(accepted_new),
            "after": count_with_tag(pools["en"]["entries"], cat),
            "skipped": dict(skipped),
            "tagged_titles": tag_adds,
            "added_titles": accepted_new,
            "sitelink_propagation": dict(lang_prop),
        }
        report["added_total_en"] += len(accepted_new)
        report["tagged_total_en"] += len(tag_adds)
        print(
            f"  tagged {len(tag_adds)} + added {len(accepted_new)} "
            f"-> {count_with_tag(pools['en']['entries'], cat)}"
        )

    for lang in LANGS:
        refresh_pool_stats(pools[lang])
    save_pools(pools)
    store.save(ap.CACHE_PATH)

    report["pool_sizes"] = {lang: len(pools[lang]["entries"]) for lang in LANGS}
    report["en_tag_counts"] = pools["en"].get("tag_counts") or {}
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n=== SUMMARY ===")
    print(
        f"EN tagged_existing={report['tagged_total_en']} "
        f"added_new={report['added_total_en']}"
    )
    for cat in CATEGORY_SOURCES:
        c = report["categories"][cat]
        print(
            f"  {cat}: {c['before']} -> {c['after']} "
            f"(+{c['tagged_existing']} tag / +{c['added_new']} new, "
            f"floor {c['floor_daily']})"
        )
    print(f"pool sizes: {report['pool_sizes']}")
    print(f"wrote annotated pools under {ANNOTATED_DIR}")
    print(f"wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
