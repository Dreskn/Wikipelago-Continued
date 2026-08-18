"""Load multi-tag article pools shipped under data/pool_{lang}.json."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
SUPPORTED_LANGS = ("en", "fr", "de", "es", "it", "pt", "nl", "sv", "pl")

# Keep in sync with web/app.js BLOCKED_WIKI_NAMESPACES.
# Matching uses the title segment before the first ":" (same as wikiNamespace()).
BLOCKED_WIKI_NAMESPACES: frozenset[str] = frozenset(
    {
        # English / canonical
        "file",
        "image",
        "category",
        "help",
        "template",
        "special",
        "portal",
        "portal talk",
        "talk",
        "user",
        "user talk",
        "wikipedia",
        "wp",
        "project",
        "module",
        "book",
        "draft",
        "mediawiki",
        "timedtext",
        "event",
        # French
        "spécial",
        "discussion",
        "discuter",
        "utilisateur",
        "utilisatrice",
        "discussion utilisateur",
        "discussion utilisatrice",
        "wikipédia",
        "fichier",
        "modèle",
        "aide",
        "catégorie",
        "portail",
        "discussion portail",
        "projet",
        "référence",
        # German
        "spezial",
        "diskussion",
        "benutzer",
        "benutzerin",
        "benutzer diskussion",
        "benutzerin diskussion",
        "bd",
        "datei",
        "bild",
        "vorlage",
        "hilfe",
        "kategorie",
        "portal diskussion",
        "pd",
        # Spanish
        "especial",
        "discusión",
        "usuario",
        "usuaria",
        "usuario discusión",
        "usuaria discusión",
        "archivo",
        "imagen",
        "plantilla",
        "ayuda",
        "categoría",
        "portal discusión",
        # Italian
        "speciale",
        "discussione",
        "utente",
        "discussioni utente",
        "immagine",
        "aiuto",
        "categoria",
        "portale",
        "discussioni portale",
        # Portuguese
        "especial",
        "discussão",
        "usuário(a)",
        "usuário",
        "usuária",
        "utilizador",
        "utilizador(a)",
        "utilizadora",
        "usuário(a) discussão",
        "usuário discussão",
        "usuária discussão",
        "utilizador discussão",
        "utilizador(a) discussão",
        "utilizadora discussão",
        "wikipédia",
        "ficheiro",
        "arquivo",
        "imagem",
        "predefinição",
        "ajuda",
        "categoria",
        "portal discussão",
        "discussão portal",
        # Dutch
        "speciaal",
        "overleg",
        "gebruiker",
        "overleg gebruiker",
        "bestand",
        "afbeelding",
        "sjabloon",
        "categorie",
        "portaal",
        "overleg portaal",
        # Swedish
        "användare",
        "användardiskussion",
        "fil",
        "mall",
        "hjälp",
        "kategori",
        "portaldiskussion",
        # Polish
        "specjalna",
        "dyskusja",
        "wikipedysta",
        "wikipedystka",
        "dyskusja wikipedysty",
        "dyskusja wikipedystki",
        "plik",
        "grafika",
        "szablon",
        "pomoc",
        "kategoria",
        "dyskusja portalu",
    }
)


def wiki_namespace(title: str) -> str:
    """Return the lowercase prefix before the first colon, or '' if none."""
    if ":" not in str(title or ""):
        return ""
    return title.split(":", 1)[0].lower()


def is_blocked_wiki_title(title: str) -> bool:
    """True when the title is a non-article wiki namespace the client refuses to open."""
    ns = wiki_namespace(title)
    return bool(ns) and ns in BLOCKED_WIKI_NAMESPACES


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
        if e.get("title") and not is_blocked_wiki_title(str(e["title"]))
    ]


def drop_blocked_from_pool_file(path: Path) -> dict[str, int]:
    """Rewrite pool JSON, dropping non-article namespace titles. Returns stats."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload.get("entries") or []
    before = len(entries)
    kept = [
        entry
        for entry in entries
        if not is_blocked_wiki_title(str(entry.get("title") or ""))
    ]
    removed = before - len(kept)
    if removed:
        payload["entries"] = kept
        payload["count"] = len(kept)
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return {"before": before, "after": len(kept), "removed": removed}
