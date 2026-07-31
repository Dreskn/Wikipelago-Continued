#!/usr/bin/env python3
"""Export annotated pools → compact JSON for the apworld package."""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ANNOTATED = HERE / "annotated"
OUT_DIR = HERE.parent / "APWorldSource" / "Wikipelago" / "data"


def export_lang(src: Path) -> dict:
    raw = json.loads(src.read_text(encoding="utf-8"))
    seen: set[str] = set()
    entries: list[dict] = []
    for row in raw.get("entries") or []:
        title = (row.get("canonical_title") or row.get("title") or "").strip()
        if not title or title in seen:
            continue
        tags = list(row.get("tags") or [])
        if not tags:
            tags = ["miscellaneous"]
        seen.add(title)
        entries.append(
            {
                "title": title,
                "tags": tags,
                "sensitive": bool(row.get("sensitive")),
            }
        )
    return {
        "lang": raw.get("lang") or src.stem.split("_")[-1],
        "source": src.name,
        "count": len(entries),
        "entries": entries,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    exported = []
    for src in sorted(ANNOTATED.glob("pool_annotated_*.json")):
        payload = export_lang(src)
        lang = payload["lang"]
        out = OUT_DIR / f"pool_{lang}.json"
        out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        exported.append((lang, payload["count"], out.stat().st_size))
        print(f"  {lang}: {payload['count']} titles -> {out} ({out.stat().st_size/1024:.0f} KB)")
    print(f"Exported {len(exported)} language pools to {OUT_DIR}")


if __name__ == "__main__":
    main()
