"""Shared Grand Goal bank selection: top 100 overall ∪ top 10 per pool tag."""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PAGEVIEWS = ROOT / "world" / "pageviews"
POOL_DIR = ROOT / "world" / "APWorldSource" / "wikipelago" / "data"
ANN_DIR = PAGEVIEWS / "annotated"
BANK_DIR = HERE / "bank"

LANGS = ("en", "fr", "de", "es", "it", "pt", "nl", "sv", "pl")

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

UA = "WikipelagoGrandGoalBank/0.1 (https://github.com/Dreskn/Wikipelago-Continued)"
SCHEMA_VERSION = 1
RULE = "top 100 overall ∪ top 10 per pool tag"

# Keep adult concept pages out of the bank even if a given branch's pool
# has not been re-flagged yet (entity QID, not the noisy pool tag).
SKIP_QIDS = {
    "Q1361427",  # sexual roleplay
    "Q2211650",  # sadomasochism
    "Q83372",    # sadism and masochism (legacy item)
    "Q185529",   # pornographic film
    "Q291",      # pornography
    "Q190845",   # BDSM
    "Q5873",     # sexual intercourse
    "Q8401",     # fellatio
    "Q164654",   # penile-vaginal intercourse
    "Q7675376",  # group sex
    "Q3007273",  # Plompzakken
}

SKIP_EXACT = {
    "404.php",
    "Main Page",
    "Accueil",
    "Wikipedia:Hauptseite",
    "Wikipedia:Portada",
    "Pagina principale",
    "Wikipédia:Página principal",
    "Hoofdpagina",
    "Portal:Huvudsida",
    "Wikipedia:Strona główna",
    ".xxx",
    "XXXX",
    "XHamster",
    "Pornhub",
    "XVideos",
    "XNxx",
    "Xnxx",
}

NS_PREFIXES = (
    "category:", "catégorie:", "kategorie:", "categoría:", "categoria:",
    "categorie:", "kategoria:",
    "template:", "modèle:", "vorlage:", "plantilla:", "sjabloon:", "szablon:",
    "help:", "aide:", "hilfe:", "ayuda:", "aiuto:", "ajuda:", "pomoc:",
    "portal:", "portail:", "portale:", "portaal:",
    "wikipedia:", "wikipédia:",
    "file:", "fichier:", "datei:", "archivo:", "ficheiro:", "bild:", "plik:",
    "special:", "spécial:", "spezial:", "especial:", "speciale:", "speciaal:",
    "specjalna:", "draft:", "brouillon:", "anexo:", "mediawiki:",
)

LIST_PREFIXES = (
    "list of ", "outline of ", "timeline of ", "index of ",
    "liste des ", "liste de ", "liste d'", "liste d’", "liste du ", "liste der ",
    "liste von ", "liste des",
    "lista de ", "lista das ", "lista di ", "lista delle ", "lista dei ",
    "lijst van ", "lijst der ",
    "lista över ",
)

DISAMBIG_RE = re.compile(
    r"\((disambiguation|homonymie|begriffsklärung|desambiguación|"
    r"disambigua|desambiguação|doorverwijspagina|olika betydelser|"
    r"ujednoznacznienie|magazine|journal)\)$",
    re.I,
)

BANNED_TITLE_KEYWORDS = (
    "rifle", "pistol", "shotgun", "revolver", "machine gun", "submachine gun",
    "discography", "chemistry", "chemical", "compound", "acid", "molecule",
    "molecular", "atom", "isotope", "reaction", "periodic table",
    "organic chemistry", "inorganic chemistry",
)


def looks_usable(title: str) -> bool:
    lowered = title.lower().strip()
    if title in SKIP_EXACT or lowered in {s.lower() for s in SKIP_EXACT}:
        return False
    if "?" in title or "sp?cial:" in lowered or "special:search" in lowered:
        return False
    if lowered.startswith(("special:", "spécial:", "spezial:", "especial:", "speciale:", "speciaal:", "specjalna:")):
        return False
    if any(lowered.startswith(prefix) for prefix in NS_PREFIXES):
        return False
    if any(lowered.startswith(prefix) for prefix in LIST_PREFIXES):
        return False
    if any(keyword in lowered for keyword in BANNED_TITLE_KEYWORDS):
        return False
    if any(ch in title for ch in ('"', "$", "%", "@", "#")):
        return False
    if title.count(",") > 2:
        return False
    if DISAMBIG_RE.search(lowered):
        return False
    if len(title.split()) > 12:
        return False
    if len(title) < 3 or len(title) > 120:
        return False
    return True


def wiki_url(lang: str, title: str) -> str:
    return f"https://{lang}.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))


def load_pool(lang: str) -> dict:
    return json.loads((POOL_DIR / f"pool_{lang}.json").read_text(encoding="utf-8"))


def load_annotated(lang: str) -> dict:
    return json.loads((ANN_DIR / f"pool_annotated_{lang}.json").read_text(encoding="utf-8"))


def load_aggregate(lang: str) -> dict:
    return json.loads((PAGEVIEWS / f"pageviews_aggregate_{lang}.json").read_text(encoding="utf-8"))


def annotated_by_title(ann: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for entry in ann.get("entries") or []:
        title = (entry.get("canonical_title") or entry.get("title") or "").strip()
        if title and title not in out:
            out[title] = entry
    return out


def fetch_extracts(lang: str, titles: list[str]) -> dict[str, str]:
    api = f"https://{lang}.wikipedia.org/w/api.php"
    out: dict[str, str] = {}
    for i in range(0, len(titles), 20):
        batch = titles[i : i + 20]
        params = {
            "action": "query",
            "format": "json",
            "prop": "extracts",
            "exintro": 1,
            "explaintext": 1,
            "exlimit": 20,
            "redirects": 1,
            "titles": "|".join(batch),
        }
        url = api + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        query = data.get("query") or {}
        normalized = {n["from"]: n["to"] for n in query.get("normalized") or []}
        redirected = {n["from"]: n["to"] for n in query.get("redirects") or []}
        by_title = {page.get("title") or "": page for page in (query.get("pages") or {}).values()}
        for original in batch:
            current = normalized.get(original, original)
            current = redirected.get(current, current)
            page = by_title.get(current) or {}
            extract = (page.get("extract") or "").strip()
            if len(extract) > 900:
                cut = extract[:900]
                extract = cut.rsplit(" ", 1)[0] + "…"
            out[original] = extract
        print(f"  {lang} extracts {i + 1}-{i + len(batch)}")
        time.sleep(0.2)
    return out


def select_union(lang: str) -> dict:
    pool = load_pool(lang)
    ann = load_annotated(lang)
    agg = load_aggregate(lang)
    ann_map = annotated_by_title(ann)
    views = {
        row["title"].replace("_", " "): int(row["views_summed_from_monthly_tops"])
        for row in agg.get("top_by_sum") or []
    }

    usable: list[dict] = []
    for entry in pool.get("entries") or []:
        title = (entry.get("title") or "").strip()
        meta = ann_map.get(title) or {}
        qid = (meta.get("qid") or "").strip()
        if entry.get("sensitive") or meta.get("sensitive"):
            continue
        if qid in SKIP_QIDS:
            continue
        if not looks_usable(title):
            continue
        usable.append(
            {
                "title": title,
                "qid": qid or None,
                "tags": list(entry.get("tags") or []),
                "views": int(views.get(title) or 0),
                "sensitive": False,
            }
        )
    usable.sort(key=lambda row: (-row["views"], row["title"].lower()))

    via: dict[str, set[str]] = {row["title"]: set() for row in usable}
    overall_rank: dict[str, int] = {}
    overall = usable[:100]
    for rank, row in enumerate(overall, start=1):
        via[row["title"]].add("overall")
        overall_rank[row["title"]] = rank

    category_ranks: dict[str, dict[str, int]] = {}
    per_tag: dict[str, list[dict]] = {}
    for tag in TAGS:
        tagged = [row for row in usable if tag in row["tags"]]
        top = tagged[:10]
        per_tag[tag] = [{"qid": row["qid"], "title": row["title"]} for row in top]
        for rank, row in enumerate(top, start=1):
            via[row["title"]].add(tag)
            category_ranks.setdefault(row["title"], {})[tag] = rank

    picked: list[dict] = []
    seen: set[str] = set()
    for row in overall:
        if row["title"] not in seen:
            picked.append(row)
            seen.add(row["title"])
    extra = [row for row in usable if via[row["title"]] - {"overall"} and row["title"] not in seen]
    extra.sort(key=lambda row: (-row["views"], row["title"].lower()))
    for row in extra:
        picked.append(row)
        seen.add(row["title"])

    cards = []
    for row in picked:
        title = row["title"]
        buckets = sorted(via[title], key=lambda name: (name != "overall", name))
        cards.append(
            {
                "qid": row["qid"],
                "answer_title": title,
                "answer_url": wiki_url(lang, title),
                "question": None,
                "lead_fact": None,
                "lead": None,
                "question_en": None,
                "lead_fact_en": None,
                "tags": row["tags"],
                "via": buckets,
                "overall_rank": overall_rank.get(title),
                "category_ranks": category_ranks.get(title) or {},
                "views_summed_from_monthly_tops": row["views"],
                "sensitive": bool(row.get("sensitive")),
                "question_source": None,
                "notes": "",
            }
        )

    return {
        "lang": lang,
        "wiki": f"{lang}wiki",
        "schema_version": SCHEMA_VERSION,
        "rule": RULE,
        "count": len(cards),
        "per_tag_top10": per_tag,
        "cards": cards,
    }
