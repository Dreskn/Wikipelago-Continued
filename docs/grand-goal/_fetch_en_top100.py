"""One-shot: top 100 EN pool titles by all-time pageviews + Wikipedia leads."""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGG = ROOT / "world" / "pageviews" / "pageviews_aggregate_en.json"
POOL = ROOT / "world" / "APWorldSource" / "wikipelago" / "data" / "pool_en.json"
ANN = ROOT / "world" / "pageviews" / "annotated" / "pool_annotated_en.json"
OUT = Path(__file__).with_name("questions-en-top100-source.json")

UA = "WikipelagoGrandGoalDraft/0.1 (https://github.com/Dreskn/Wikipelago-Continued)"
API = "https://en.wikipedia.org/w/api.php"

BANNED_TITLE_KEYWORDS = (
    "rifle", "pistol", "shotgun", "revolver", "machine gun", "submachine gun",
    "discography", "chemistry", "chemical", "compound", "acid", "molecule",
    "molecular", "atom", "isotope", "reaction", "periodic table",
    "organic chemistry", "inorganic chemistry",
)
BANNED_TITLE_SUFFIXES = (
    "(programming language)", "(operating system)", "(software)", "(computer)",
)
SKIP_EXACT = {
    "404.php",
    "Main Page",
    ".xxx",
    "XXXX",
    "XHamster",
    "Pornhub",
    "XVideos",
    "XNxx",
}
SKIP_PREFIXES = (
    "list of ", "outline of ", "timeline of ", "index of ",
    "category:", "template:", "help:", "portal:", "wikipedia:",
    "file:", "special:", "draft:",
)


def looks_usable(title: str) -> bool:
    lowered = title.lower().strip()
    if title in SKIP_EXACT or lowered in {s.lower() for s in SKIP_EXACT}:
        return False
    if lowered.startswith(SKIP_PREFIXES):
        return False
    if any(keyword in lowered for keyword in BANNED_TITLE_KEYWORDS):
        return False
    if any(lowered.endswith(suffix) for suffix in BANNED_TITLE_SUFFIXES):
        return False
    if any(ch in title for ch in ('"', "$", "%", "@", "#")):
        return False
    if title.count(",") > 2:
        return False
    if re.search(r"\(disambiguation|magazine|journal\)$", lowered):
        return False
    if len(title.split()) > 12:
        return False
    if len(title) < 3 or len(title) > 120:
        return False
    return True


def wiki_get(params: dict) -> dict:
    q = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{API}?{q}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_extracts(titles: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for i in range(0, len(titles), 20):
        batch = titles[i : i + 20]
        data = wiki_get(
            {
                "action": "query",
                "format": "json",
                "prop": "extracts",
                "exintro": 1,
                "explaintext": 1,
                "exlimit": 20,
                "redirects": 1,
                "titles": "|".join(batch),
            }
        )
        query = data.get("query") or {}
        normalized = {n["from"]: n["to"] for n in query.get("normalized") or []}
        redirected = {n["from"]: n["to"] for n in query.get("redirects") or []}
        by_title: dict[str, dict] = {}
        for page in (query.get("pages") or {}).values():
            by_title[page.get("title") or ""] = page
        for original in batch:
            current = normalized.get(original, original)
            current = redirected.get(current, current)
            page = by_title.get(current) or {}
            extract = (page.get("extract") or "").strip()
            if len(extract) > 1400:
                cut = extract[:1400]
                extract = cut.rsplit(" ", 1)[0] + "…"
            out[original] = extract
        print(f"  extracts {i + 1}-{i + len(batch)}")
        time.sleep(0.25)
    return out


def main() -> None:
    agg = json.loads(AGG.read_text(encoding="utf-8"))
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    ann = json.loads(ANN.read_text(encoding="utf-8"))
    pool_by_title = {e["title"]: e for e in pool["entries"]}
    sensitive: dict[str, bool] = {}
    for entry in ann["entries"]:
        title = (entry.get("canonical_title") or entry.get("title") or "").strip()
        if title:
            sensitive[title] = bool(entry.get("sensitive"))

    picked: list[dict] = []
    skipped: list[dict] = []
    for row in agg["top_by_sum"]:
        title = row["title"].replace("_", " ")
        reason = None
        if title not in pool_by_title:
            reason = "not in pool"
        elif pool_by_title[title].get("sensitive") or sensitive.get(title):
            reason = "sensitive"
        elif not looks_usable(title):
            reason = "filtered"
        if reason:
            if len(skipped) < 50:
                skipped.append({"title": title, "reason": reason, "views": row["views_summed_from_monthly_tops"]})
            continue
        picked.append(
            {
                "rank": len(picked) + 1,
                "title": title,
                "views_summed_from_monthly_tops": row["views_summed_from_monthly_tops"],
                "tags": list(pool_by_title[title].get("tags") or []),
            }
        )
        if len(picked) >= 100:
            break

    print(f"Picked {len(picked)} titles, fetching leads…")
    extracts = fetch_extracts([p["title"] for p in picked])
    for item in picked:
        item["lead"] = extracts.get(item["title"] or "") or ""

    payload = {
        "lang": "en",
        "source_rank": "pageviews_aggregate_en.json top_by_sum",
        "pool": "pool_en.json",
        "count": len(picked),
        "skipped_examples": skipped,
        "entries": picked,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
