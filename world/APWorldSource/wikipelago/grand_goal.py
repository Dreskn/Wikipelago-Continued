"""Closed-question Grand Goal bank (language-native questions)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .article_pool import SUPPORTED_LANGS

DATA_DIR = Path(__file__).resolve().parent / "data" / "grand_goal"


def _docs_bank_path(lang: str) -> Path | None:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "docs" / "grand-goal" / "bank" / f"{lang}.json"
        if candidate.is_file():
            return candidate
    return None


def _read_bank_json(lang: str) -> str:
    try:
        from importlib.resources import files

        return (
            files(__package__)
            .joinpath("data", "grand_goal", f"{lang}.json")
            .read_text(encoding="utf-8")
        )
    except Exception:
        pass

    packaged = DATA_DIR / f"{lang}.json"
    if packaged.is_file():
        return packaged.read_text(encoding="utf-8")

    docs_path = _docs_bank_path(lang)
    if docs_path is not None:
        return docs_path.read_text(encoding="utf-8")

    raise FileNotFoundError(
        f"Missing Grand Goal question bank for language '{lang}'. "
        "Expected data/grand_goal/{lang}.json in the apworld, or "
        "docs/grand-goal/bank/{lang}.json in the repo."
    )


@lru_cache(maxsize=None)
def load_grand_goal_cards(lang: str = "en") -> list[dict[str, Any]]:
    code = (lang or "en").strip().lower()
    if code not in SUPPORTED_LANGS:
        raise ValueError(
            f"Unsupported wikipedia_language '{lang}'. "
            f"Supported: {', '.join(SUPPORTED_LANGS)}"
        )
    payload = json.loads(_read_bank_json(code))
    cards: list[dict[str, Any]] = []
    for raw in payload.get("cards") or []:
        question = str(raw.get("question") or "").strip()
        title = str(raw.get("answer_title") or "").strip()
        if not question or not title:
            continue
        if str(raw.get("status") or "").strip().lower() == "rejected":
            continue
        cards.append(
            {
                "qid": raw.get("qid") or None,
                "answer_title": title,
                "question": question,
                "tags": [str(tag) for tag in (raw.get("tags") or []) if tag],
            }
        )
    return cards


def card_for_title(lang: str, title: str) -> dict[str, Any] | None:
    want = (title or "").strip().lower()
    if not want:
        return None
    for card in load_grand_goal_cards(lang):
        if card["answer_title"].lower() == want:
            return card
    return None


def pick_grand_goal_card(
    rng: Any,
    lang: str,
    selected_topics: set[str],
    pool_titles: list[str],
) -> dict[str, Any] | None:
    """Pick a bank card, preferring answers already in the filtered article pool."""
    cards = load_grand_goal_cards(lang)
    if not cards:
        return None
    pool_set = set(pool_titles)
    in_pool = [card for card in cards if card["answer_title"] in pool_set]
    if selected_topics:
        tagged = [
            card
            for card in in_pool
            if selected_topics.intersection(card.get("tags") or ())
        ]
    else:
        tagged = in_pool
    bucket = tagged or in_pool or cards
    return rng.choice(bucket)
