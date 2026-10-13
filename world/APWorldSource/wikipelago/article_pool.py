"""Load multi-tag article pools shipped under data/pool_{lang}.json, and the title rules
generate uses on them (no Archipelago imports, so tools can load this file by path)."""

from __future__ import annotations

import json
import re
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


# Matched as whole words, case-insensitive: "Acid", "Periodic table" and "David Bowie
# discography" are dropped; Grey's Anatomy, Sex Pistols, Atomic Blonde, Lake Placid,
# "Acidente nuclear de Chernobil" and "(futbolista nacido en 1995)" are not.
BANNED_TITLE_KEYWORDS: tuple[str, ...] = (
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

BANNED_TITLE_SUFFIXES: tuple[str, ...] = (
    "(programming language)",
    "(operating system)",
    "(software)",
    "(computer)",
)

_BANNED_TITLE_WORDS_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(keyword) for keyword in BANNED_TITLE_KEYWORDS) + r")\b",
    re.IGNORECASE,
)

# "List of ..." style pages in the 9 wikis (lowercase prefixes).
LIST_PAGE_PREFIXES: tuple[str, ...] = (
    "list of ",
    "lists of ",
    "outline of ",
    "timeline of ",
    "index of ",
    "anexo:",  # es list namespace
    "lista polaków",  # pl "List of Poles who ..." (the capital P hides it from the rule below)
)

# These words start a list page when the next word is lowercase or a number: "Liste des",
# "Liste d'", "Liste von", "Liste der", "Lista de", "Lista di", "Lista över", "Lijst van",
# "Lista odcinków", "Elenco de", "Wykaz ras", "Chronologie des". Named lists and parties
# keep their capital and stay ("Lijst Pim Fortuyn", "Lista Clinton", "Lista Macierewicza").
LIST_PAGE_WORDS: frozenset[str] = frozenset(
    {
        "liste",
        "lista",
        "lijst",
        "elenco",
        "wykaz",
        "chronologie",
        "cronologia",
        "cronología",
        "kalendarium",
    }
)


def is_list_page_title(title: str) -> bool:
    """True for "List of ..." style pages in any of the 9 wikis."""
    stripped = str(title or "").strip()
    if stripped.lower().startswith(LIST_PAGE_PREFIXES):
        return True
    first, _, rest = stripped.partition(" ")
    return first.lower() in LIST_PAGE_WORDS and bool(rest) and (rest[0].islower() or rest[0].isdigit())


# Pages a keyword rule drops by mistake, per wiki: a rapper, a YouTuber, a Polish gold coin.
KEYWORD_EXCEPTIONS: dict[str, frozenset[str]] = {
    "it": frozenset({"Rosa Chemical"}),
    "nl": frozenset({"Acid (youtuber)"}),
    "pl": frozenset({"Pistol"}),
}


def has_banned_title_word(title: str, lang: str = "") -> bool:
    """True when the title has a weapon / chemistry / discography keyword as a whole word."""
    if title in KEYWORD_EXCEPTIONS.get(lang, ()):
        return False
    return bool(_BANNED_TITLE_WORDS_RE.search(str(title or "")))


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


def looks_common_knowledge(title: str, lang: str = "") -> bool:
    if is_blocked_wiki_title(title):
        return False
    lowered = title.lower().strip()
    if is_list_page_title(title):
        return False
    if has_banned_title_word(title, lang):
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
    return True


def is_usable_title(title: str, lang: str = "") -> bool:
    """Titles generate may pick as a Start / Target (the practice mode uses the same rule)."""
    return is_reasonable_title(title) and looks_common_knowledge(title, lang)


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
