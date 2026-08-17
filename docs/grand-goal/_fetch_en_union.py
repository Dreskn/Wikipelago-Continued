"""Select EN pool union: top 100 overall ∪ top 10 per tag, then fetch leads."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _fetch_en_top100 import (  # noqa: E402
    AGG,
    ANN,
    POOL,
    fetch_extracts,
    looks_usable,
)

OUT = HERE / "questions-en-union-source.json"

TAGS = (
    "video_games",
    "movies",
    "tv_shows",
    "anime_manga",
    "sports",
    "science_space",
    "technology",
    "history",
    "geography",
    "food_cuisine",
    "art_literature",
    "mythology_folklore",
    "music",
    "politics",
    "famous_people",
    "miscellaneous",
    "animals",
    "biology_medicine",
)


def main() -> None:
    agg = json.loads(AGG.read_text(encoding="utf-8"))
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    ann = json.loads(ANN.read_text(encoding="utf-8"))
    sensitive = {
        (e.get("canonical_title") or e.get("title") or "").strip(): bool(e.get("sensitive"))
        for e in ann["entries"]
        if (e.get("canonical_title") or e.get("title") or "").strip()
    }
    views = {row["title"].replace("_", " "): row["views_summed_from_monthly_tops"] for row in agg["top_by_sum"]}

    usable: list[dict] = []
    for entry in pool["entries"]:
        title = entry["title"]
        if entry.get("sensitive") or sensitive.get(title):
            continue
        if not looks_usable(title):
            continue
        usable.append(
            {
                "title": title,
                "tags": list(entry.get("tags") or []),
                "views": int(views.get(title) or 0),
            }
        )
    usable.sort(key=lambda row: (-row["views"], row["title"].lower()))

    via: dict[str, set[str]] = {row["title"]: set() for row in usable}
    overall = usable[:100]
    for rank, row in enumerate(overall, start=1):
        via[row["title"]].add("overall")
        row["overall_rank"] = rank

    per_tag: dict[str, list[str]] = {}
    for tag in TAGS:
        tagged = [row for row in usable if tag in row["tags"]]
        top = tagged[:10]
        per_tag[tag] = [row["title"] for row in top]
        for rank, row in enumerate(top, start=1):
            via[row["title"]].add(tag)

    picked_titles: list[str] = []
    seen: set[str] = set()
    # Overall first (keep that order), then remaining category-only pages by views.
    for row in overall:
        if row["title"] not in seen:
            picked_titles.append(row["title"])
            seen.add(row["title"])
    extra = [row for row in usable if via[row["title"]] - {"overall"} and row["title"] not in seen]
    extra.sort(key=lambda row: (-row["views"], row["title"].lower()))
    for row in extra:
        picked_titles.append(row["title"])
        seen.add(row["title"])

    by_title = {row["title"]: row for row in usable}
    entries = []
    for title in picked_titles:
        row = by_title[title]
        buckets = sorted(via[title], key=lambda name: (name != "overall", name))
        entries.append(
            {
                "title": title,
                "views_summed_from_monthly_tops": row["views"],
                "tags": row["tags"],
                "via": buckets,
                "in_overall_top100": "overall" in via[title],
            }
        )

    print(f"usable={len(usable)} union={len(entries)} overall={len(overall)}")
    for tag in TAGS:
        print(f"  {tag:22} top10={len(per_tag[tag])}")

    print("Fetching leads…")
    extracts = fetch_extracts(picked_titles)
    for item in entries:
        item["lead"] = extracts.get(item["title"] or "") or ""

    payload = {
        "lang": "en",
        "rule": "top 100 overall ∪ top 10 per pool tag",
        "pool": "pool_en.json",
        "count": len(entries),
        "per_tag_top10": per_tag,
        "entries": entries,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
