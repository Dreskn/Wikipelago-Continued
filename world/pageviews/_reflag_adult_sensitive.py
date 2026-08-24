#!/usr/bin/env python3
"""Re-flag shipped pools after adult-topic denylist / entity-QID sensitive fix."""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from annotate_pools import (  # noqa: E402
    ADULT_TOPIC_QIDS,
    UA,
)

ANNOTATED = HERE / "annotated"
POOL_DIR = HERE.parent / "APWorldSource" / "wikipelago" / "data"
SPARQL = "https://query.wikidata.org/sparql"


def sparql_adult_qids() -> set[str]:
    values = " ".join(f"wd:{qid}" for qid in sorted(ADULT_TOPIC_QIDS))
    query = f"""
    SELECT DISTINCT ?item WHERE {{
      VALUES ?bad {{ {values} }}
      ?item wdt:P31|wdt:P279|wdt:P136|wdt:P360|wdt:P921 ?bad .
    }}
    """
    url = SPARQL + "?" + urllib.parse.urlencode({"query": query, "format": "json"})
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/sparql-results+json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    out: set[str] = set()
    for row in data.get("results", {}).get("bindings", []):
        uri = (row.get("item") or {}).get("value") or ""
        qid = uri.rsplit("/", 1)[-1]
        if qid.startswith("Q"):
            out.add(qid)
    return out


def write_json_like(path: Path, payload: dict, original: bytes) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if original.endswith(b"\r\n"):
        text = text.replace("\n", "\r\n") + "\r\n"
    elif original.endswith(b"\n"):
        text = text + "\n"
    elif b"\r\n" in original[:4000]:
        text = text.replace("\n", "\r\n")
    path.write_bytes(text.encode("utf-8"))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    concepts = set(ADULT_TOPIC_QIDS)
    print(f"concept denylist qids: {len(concepts)}")
    print("SPARQL adult claim matches…")
    related = sparql_adult_qids()
    print(f"SPARQL adult-related items: {len(related)}")
    want = set(concepts) | related
    want |= set(ADULT_TOPIC_QIDS)

    # Pass 1: annotated files (have QIDs). Collect titles to flag in compact pools.
    titles_by_lang: dict[str, set[str]] = {}
    for src in sorted(ANNOTATED.glob("pool_annotated_*.json")):
        lang = src.stem.rsplit("_", 1)[-1]
        original = src.read_bytes()
        raw = json.loads(original.decode("utf-8"))
        newly: list[tuple[str, str]] = []
        titles: set[str] = set()
        for entry in raw.get("entries") or []:
            qid = (entry.get("qid") or "").strip()
            title = (entry.get("canonical_title") or entry.get("title") or "").strip()
            if not qid or qid not in want:
                continue
            titles.add(title)
            if not entry.get("sensitive"):
                entry["sensitive"] = True
                newly.append((qid, title))
        if newly:
            raw["sensitive_flagged"] = int(raw.get("sensitive_flagged") or 0) + len(newly)
            write_json_like(src, raw, original)
        titles_by_lang[lang] = titles
        print(f"  annotated {lang}: +{len(newly)} (pool titles {len(titles)})")
        for qid, title in newly:
            print(f"    {qid}  {title}")

    for lang, titles in titles_by_lang.items():
        pool_path = POOL_DIR / f"pool_{lang}.json"
        if not pool_path.is_file() or not titles:
            continue
        original = pool_path.read_bytes()
        raw = json.loads(original.decode("utf-8"))
        n = 0
        for entry in raw.get("entries") or []:
            title = (entry.get("title") or "").strip()
            if title in titles and not entry.get("sensitive"):
                entry["sensitive"] = True
                n += 1
        if n:
            write_json_like(pool_path, raw, original)
        print(f"  pool {lang}: +{n}")


if __name__ == "__main__":
    main()
