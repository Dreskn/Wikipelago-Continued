#!/usr/bin/env python3
"""Blocked wiki-namespace helpers must match the web client and stay out of pools.
Also checks the usable-title filter (whole-word keywords, list pages in the 9 wikis)."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
POOL_MOD_PATH = ROOT / "APWorldSource" / "wikipelago" / "article_pool.py"
WEB_APP_PATH = ROOT.parent / "web" / "app.js"
DATA_DIR = ROOT / "APWorldSource" / "wikipelago" / "data"

CASES = (
    ("Template:Pornography", True),
    ("Wikipedia:De kroeg", True),
    ("Wikipédia:Accueil", True),
    ("Plik:Example.png", True),
    ("Fichier:Example.png", True),
    ("Datei:Example.png", True),
    ("Vorlage:Foo", True),
    ("Sjabloon:Foo", True),
    ("Szablon:Foo", True),
    ("Portail:Foo", True),
    ("Catégorie:Foo", True),
    ("Modèle:Foo", True),
    ("Portal:COVID-19", True),
    ("Wikipedia", False),
    ("Minecraft", False),
    ("Star Wars: Episode IV – A New Hope", False),
    ("C++", False),
)

# is_usable_title: whole-word keyword filter and "List of ..." pages in all 9 wikis.
USABLE_CASES = (
    ("Grey's Anatomy", True),
    ("Sex Pistols", True),
    ("Atomic Blonde", True),
    ("Atomium", True),
    ("Lake Placid", True),
    ("Acidente nuclear de Chernobil", True),
    ("André Silva (futbolista nacido en 1995)", True),
    ("Lijst Pim Fortuyn", True),
    ("Lista Clinton", True),
    ("Lista Polaków, którzy zginęli w Himalajach i Karakorum", False),
    ("Periodic table", False),
    ("David Bowie discography", False),
    ("Acid", False),
    ("List of James Bond films", False),
    ("Liste des papes", False),
    ("Liste d'éclipses solaires", False),
    ("Liste der Päpste", False),
    ("Liste von Erdbeben in Deutschland", False),
    ("Anexo:Papas", False),
    ("Lista dei papi", False),
    ("Lista de Pokémon", False),
    ("Elenco de Vale Tudo", False),
    ("Lijst van Disneypersonages", False),
    ("Lista över Disneyfilmer", False),
    ("Lista odcinków serialu Przyjaciele", False),
    ("Benutzer:Plenz/OSM for Wiki/languages", False),
    ("Mall:Sveriges största tätorter", False),
)


def _load_pool_mod():
    spec = importlib.util.spec_from_file_location("wikipelago_article_pool", POOL_MOD_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {POOL_MOD_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _js_blocked_namespaces(text: str) -> set[str]:
    start = text.index("const BLOCKED_WIKI_NAMESPACES = new Set([")
    end = text.index("]);", start)
    chunk = text[start:end]
    return set(re.findall(r'"([^"]+)"', chunk))


def main() -> int:
    mod = _load_pool_mod()
    failures: list[str] = []

    js_set = _js_blocked_namespaces(WEB_APP_PATH.read_text(encoding="utf-8"))
    py_set = set(mod.BLOCKED_WIKI_NAMESPACES)
    if js_set != py_set:
        only_js = sorted(js_set - py_set)
        only_py = sorted(py_set - js_set)
        failures.append(
            "BLOCKED_WIKI_NAMESPACES drift between web/app.js and article_pool.py "
            f"(js-only={only_js!r} py-only={only_py!r})"
        )

    for title, expected in CASES:
        got = bool(mod.is_blocked_wiki_title(title))
        if got != expected:
            failures.append(
                f"is_blocked_wiki_title({title!r}) expected {expected}, got {got}"
            )

    for title, expected in USABLE_CASES:
        got = bool(mod.is_usable_title(title))
        if got != expected:
            failures.append(f"is_usable_title({title!r}) expected {expected}, got {got}")

    # Per-wiki keyword exceptions: kept in their own wiki only.
    for title, lang in (("Rosa Chemical", "it"), ("Acid (youtuber)", "nl"), ("Pistol", "pl")):
        if not mod.is_usable_title(title, lang):
            failures.append(f"is_usable_title({title!r}, {lang!r}) should keep the exception")
        if mod.is_usable_title(title, "en"):
            failures.append(f"is_usable_title({title!r}, 'en') should still drop it")

    for lang in mod.SUPPORTED_LANGS:
        path = DATA_DIR / f"pool_{lang}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        blocked = [
            str(entry.get("title") or "")
            for entry in (payload.get("entries") or [])
            if mod.is_blocked_wiki_title(str(entry.get("title") or ""))
        ]
        if blocked:
            sample = ", ".join(blocked[:8])
            extra = "" if len(blocked) <= 8 else f" (+{len(blocked) - 8} more)"
            failures.append(
                f"pool_{lang}.json still has {len(blocked)} blocked namespace title(s): "
                f"{sample}{extra}"
            )

    if failures:
        for line in failures:
            print(f"FAIL: {line}", file=sys.stderr)
        return 1
    print("PASS: blocked wiki-namespace helpers match the client; pools are clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
