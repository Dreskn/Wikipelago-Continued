"""Build docs/grand-goal/bank/{lang}.json for every supported wiki language."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from _bank_common import (  # noqa: E402
    BANK_DIR,
    LANGS,
    RULE,
    SCHEMA_VERSION,
    TAGS,
    fetch_extracts,
    select_union,
)
from _build_review_md import QUESTIONS  # noqa: E402
from _build_union_md import EXTRA  # noqa: E402

TOP100_SRC = HERE / "questions-en-top100-source.json"
TRANSLATIONS_DIR = HERE / "bank" / "translations"

# Pages that entered the EN union after adult titles were dropped from selection.
BANK_EXTRA: dict[str, dict[str, str]] = {
    "HTTP cookie": {
        "question": "Which small piece of data, introduced in 1994 by a Netscape engineer, does a website store on a visitor's computer so the site can remember state between requests?",
        "fact": "Lou Montulli / Netscape, 1994; client-side state between HTTP requests.",
    },
    "Tuberculosis": {
        "question": "Which infectious disease, historically called consumption, is caused by Mycobacterium tuberculosis and usually attacks the lungs?",
        "fact": "Mycobacterium tuberculosis; historically consumption; typically pulmonary.",
    },
}


def en_questions_by_title() -> dict[str, dict[str, str]]:
    old = json.loads(TOP100_SRC.read_text(encoding="utf-8"))
    by_title: dict[str, dict[str, str]] = {}
    for index, entry in enumerate(old["entries"]):
        by_title[entry["title"]] = QUESTIONS[index]
    by_title.update(EXTRA)
    by_title.update(BANK_EXTRA)
    return by_title


def apply_en_questions(payload: dict, by_title: dict[str, dict[str, str]]) -> None:
    missing: list[str] = []
    for card in payload["cards"]:
        title = card["answer_title"]
        q = by_title.get(title)
        if not q:
            missing.append(title)
            continue
        card["question"] = q["question"]
        card["lead_fact"] = q["fact"]
        card["question_en"] = q["question"]
        card["lead_fact_en"] = q["fact"]
        card["question_source"] = "en-hand"
        card["status"] = "draft"
    if missing:
        raise SystemExit("Missing EN questions for: " + "; ".join(missing))


def index_en_by_qid(en_payload: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for card in en_payload["cards"]:
        qid = card.get("qid")
        if qid:
            out[qid] = card
    return out


def apply_translations(payload: dict, en_by_qid: dict[str, dict]) -> None:
    lang = payload["lang"]
    trans_path = TRANSLATIONS_DIR / f"{lang}.json"
    trans: dict[str, dict] = {}
    if trans_path.is_file():
        trans = json.loads(trans_path.read_text(encoding="utf-8"))

    for card in payload["cards"]:
        qid = card.get("qid")
        en = en_by_qid.get(qid) if qid else None
        if en:
            card["question_en"] = en.get("question")
            card["lead_fact_en"] = en.get("lead_fact")
        row = trans.get(qid) if qid else None
        if not row and card.get("answer_title"):
            row = trans.get(card["answer_title"])
        if row and row.get("question"):
            card["question"] = row["question"]
            card["lead_fact"] = row.get("lead_fact") or card.get("lead_fact")
            card["question_source"] = row.get("source") or (
                "translated-from-en" if en else "native-lead"
            )
            card["status"] = row.get("status") or "draft"
            if row.get("notes"):
                card["notes"] = row["notes"]
        elif en and not card.get("question"):
            card["question_source"] = "missing-translation"
            card["status"] = "needs_translation"
        elif not card.get("question"):
            card["question_source"] = "missing-native"
            card["status"] = "needs_native"


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_manifest(payloads: dict[str, dict]) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "purpose": (
            "Closed-question Grand Goal bank. At generate time, pick one card for the "
            "player's wiki language. Victory is still landing on answer_title; the "
            "question is what the client shows instead of the title."
        ),
        "rule": RULE,
        "pool_tags": list(TAGS),
        "languages": list(LANGS),
        "stable_id": "qid",
        "generated_on": date.today().isoformat(),
        "files": {lang: f"{lang}.json" for lang in LANGS},
        "counts": {lang: payload["count"] for lang, payload in payloads.items()},
        "card_fields": {
            "qid": "Wikidata id. Stable across languages; preferred lookup key.",
            "answer_title": "Exact Wikipedia title on this language wiki (the Victory page).",
            "answer_url": "Convenience link; do not use as an id.",
            "question": "Closed question in this wiki's language. Must not name the answer.",
            "lead_fact": "The lead detail the question was built from (authoring / review).",
            "lead": "Truncated plain-text Wikipedia lead at bank-build time.",
            "question_en": "English source question when this QID is also in the EN bank.",
            "lead_fact_en": "English lead-fact companion to question_en.",
            "tags": "Pool tags from pool_{lang}.json (noisy; do not treat as ground truth).",
            "via": "Why the page is in the bank: 'overall' and/or pool tag names.",
            "overall_rank": "1–100 if this page is in the usable top 100; else null.",
            "category_ranks": "Rank within each tag's usable top 10 that selected it.",
            "views_summed_from_monthly_tops": "From pageviews_aggregate_{lang}.json.",
            "sensitive": "Copied from the pool; bank selection already drops sensitive pages.",
            "status": "draft | needs_translation | needs_native | accepted | rejected.",
            "question_source": "en-hand | translated-from-en | native-lead | missing-*.",
            "notes": "Hand-review notes.",
        },
        "usage": {
            "pick": "Filter cards where question is non-empty and status is not rejected.",
            "victory": "Compare the landed page title to answer_title (after redirects).",
            "cross_lang": "Join on qid when the same entity exists in several banks.",
        },
    }


def merge_existing() -> None:
    """Apply translation files onto already-built bank JSON (keeps leads)."""
    en = json.loads((BANK_DIR / "en.json").read_text(encoding="utf-8"))
    en_by_qid = index_en_by_qid(en)
    payloads: dict[str, dict] = {"en": en}
    for lang in LANGS:
        if lang == "en":
            continue
        path = BANK_DIR / f"{lang}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        apply_translations(payload, en_by_qid)
        write_json(path, payload)
        filled = sum(1 for card in payload["cards"] if card.get("question"))
        print(f"merged {lang}: {filled}/{payload['count']} questions")
        payloads[lang] = payload
    write_json(BANK_DIR / "manifest.json", build_manifest(payloads))
    print(f"Wrote {BANK_DIR / 'manifest.json'}")


def main() -> None:
    if "--merge-only" in sys.argv:
        merge_existing()
        return
    fetch_leads = "--no-leads" not in sys.argv
    BANK_DIR.mkdir(parents=True, exist_ok=True)
    by_title = en_questions_by_title()
    payloads: dict[str, dict] = {}

    print("Selecting unions…")
    for lang in LANGS:
        payload = select_union(lang)
        print(f"  {lang}: {payload['count']} cards")
        payloads[lang] = payload

    apply_en_questions(payloads["en"], by_title)
    en_by_qid = index_en_by_qid(payloads["en"])

    if fetch_leads:
        print("Fetching leads…")
        for lang, payload in payloads.items():
            titles = [card["answer_title"] for card in payload["cards"]]
            extracts = fetch_extracts(lang, titles)
            for card in payload["cards"]:
                card["lead"] = extracts.get(card["answer_title"] or "") or ""

    for lang, payload in payloads.items():
        if lang != "en":
            apply_translations(payload, en_by_qid)
        write_json(BANK_DIR / f"{lang}.json", payload)
        print(f"Wrote {BANK_DIR / f'{lang}.json'}")

    manifest = build_manifest(payloads)
    write_json(BANK_DIR / "manifest.json", manifest)
    print(f"Wrote {BANK_DIR / 'manifest.json'}")
    en_qids = {card["qid"] for card in payloads["en"]["cards"] if card.get("qid")}
    print("Overlap with EN qids:")
    for lang, payload in payloads.items():
        qids = {card["qid"] for card in payload["cards"] if card.get("qid")}
        shared = len(qids & en_qids)
        unique = len(qids - en_qids)
        filled = sum(1 for card in payload["cards"] if card.get("question"))
        print(f"  {lang}: cards={payload['count']} shared_qid={shared} lang_only={unique} with_question={filled}")


if __name__ == "__main__":
    main()
