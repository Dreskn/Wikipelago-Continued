"""Load multi-tag article pools shipped under data/pool_{lang}.json."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
SUPPORTED_LANGS = ("en", "fr", "de", "es", "it", "pt", "nl", "sv", "pl")


def _read_pool_json(code: str) -> str:
    """Read pool JSON from the package (zip/apworld) or filesystem checkout."""
    try:
        from importlib.resources import files

        return (
            files(__package__)
            .joinpath("data", f"pool_{code}.json")
            .read_text(encoding="utf-8")
        )
    except Exception:
        pass

    path = DATA_DIR / f"pool_{code}.json"
    if path.is_file():
        return path.read_text(encoding="utf-8")

    raise FileNotFoundError(
        f"Missing article pool for language '{code}'. "
        "Rebuild with world/build_apworld.ps1 and reinstall "
        f"wikipelago.apworld (expected package resource data/pool_{code}.json)."
    )


@lru_cache(maxsize=None)
def load_article_pool(lang: str = "en") -> list[dict]:
    """Return list of {title, tags, sensitive} for the given wiki language."""
    code = (lang or "en").strip().lower()
    if code not in SUPPORTED_LANGS:
        raise ValueError(
            f"Unsupported wikipedia_language '{lang}'. "
            f"Supported: {', '.join(SUPPORTED_LANGS)}"
        )
    payload = json.loads(_read_pool_json(code))
    entries = payload.get("entries") or []
    return [
        {
            "title": str(e["title"]),
            "tags": list(e.get("tags") or ["miscellaneous"]),
            "sensitive": bool(e.get("sensitive")),
        }
        for e in entries
        if e.get("title")
    ]
