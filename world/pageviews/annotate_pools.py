#!/usr/bin/env python3
"""
Annotate pageviews_aggregate_*.json → per-language pool files for the apworld.

- Reads only final_titles_sorted from each aggregate
- Batched Wikidata resolve + shared P279 subclass / P171 taxon walks
- Categorizes each Wikidata QID once; later languages reuse tags/sensitive
  via QID cache and sitelink reverse index (EN processed first)
- Writes pool_annotated_{lang}.json (native title + qid + tags + sensitive)

Tweak SAMPLE_N at the top: 1000 for a dry run, 0 for the full lists.
"""

from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

# --- config ---
HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "annotated"
CACHE_PATH = HERE / "qid_annotation_cache.json"

SAMPLE_N = 0           # 0 = all titles in each aggregate
SEED = 42
SUBCLASS_DEPTH = 6     # P279 subclass walk
TAXON_DEPTH = 16       # P171 parent-taxon walk (deep for dinosaurs etc.)
BATCH = 50
SLEEP_S = 0.05
MAX_RETRIES = 8
CACHE_SAVE_EVERY = 200  # new QIDs classified between disk saves
CACHE_SCHEMA = 5       # bump when classification rules change (invalidates old cache)

UA = "WikipelagoPoolAnnotate/0.1 (https://github.com/Dreskn/Wikipelago-Continued)"
MISC_TAG = "miscellaneous"

# Process English first so other langs can reuse QIDs / sitelinks.
LANG_ORDER_FIRST = ("en",)
# Set to a tuple like ("en",) for a dry run; None = every aggregate language.
LANGS_ENABLED: tuple[str, ...] | None = None

# If P31 expands to these, ignore P31 for categories; use P360/P921 (+ subjects) instead.
WIKI_META_TYPES = {
    "Q13406463",  # Wikimedia list article
    "Q17442446",  # Wikimedia internal item
}

HUMAN = "Q5"
ANIMALIA = "Q729"
TAXON = "Q16521"

SENSITIVE_QIDS: dict[str, set[str]] = {
    "P31": {
        "Q185529", "Q599558", "Q3244962", "Q291",
        "Q17127659", "Q7283", "Q2223653",
        "Q132821", "Q149086", "Q484188", "Q750215",
        "Q47092", "Q365680", "Q7458798",  # sexual misconduct
        "Q83871", "Q11367", "Q844924",
    },
    "P106": {"Q484188"},
    "P136": {"Q185529", "Q599558"},
    "P360": {"Q47092", "Q365680", "Q7458798", "Q185529", "Q291"},
    "P921": {"Q47092", "Q365680", "Q7458798", "Q185529", "Q291"},
}

QID_MAP: dict[str, dict[str, set[str]]] = {
    "famous_people": {"P31": {"Q5"}},
    "politics": {
        "P106": {"Q82955"},
        "P31": {
            "Q7278",      # political party
            "Q40231",     # public election
            "Q7210356",   # political organization
            "Q49773",     # social movement
            "Q11204",     # legislature
            "Q35798",     # executive branch
        },
    },
    "video_games": {
        "P31": {
            "Q7889",      # video game
            "Q7058673",   # video game series
        },
    },
    "movies": {
        "P31": {
            "Q11424",     # film
            "Q24856",     # film series
            "Q196600",    # media franchise
        },
        "P106": {"Q10800557", "Q33999"},
    },
    "tv_shows": {
        "P31": {
            "Q5398426",   # television series
            "Q15416",     # television program
            "Q3464665",   # television series season
        },
        "P106": {"Q10798782"},
    },
    "anime_manga": {"P31": {"Q1107", "Q8274"}, "P136": {"Q1107", "Q8274"}},
    "music": {
        "P31": {
            "Q482994",      # album
            "Q7366",        # song
            "Q215380",      # musical group / band
            "Q134556",      # single
            "Q105543609",   # musical work/composition
            "Q2188189",     # musical work
        },
        "P106": {"Q177220", "Q639669"},
    },
    "sports": {
        "P31": {
            "Q349",         # sport
            "Q16510064",    # sporting event
            "Q13406554",    # sports competition
            "Q27020041",    # sports season
            "Q5389",        # Olympic Games
            "Q1194951",     # national sports team
            "Q12973014",    # sports team
            "Q476028",      # association football club
        },
        "P106": {"Q2066131"},  # athlete
    },
    "science_space": {
        "P31": {
            "Q336",     # science
            "Q333",     # astronomy
            "Q40218",   # spacecraft
            "Q5916",    # spaceflight
            "Q6999",    # astronomical object
            "Q3504248", # planetary system
        },
    },
    "technology": {
        "P31": {
            "Q11016",     # technology
            "Q68",        # computer
            "Q7397",      # software
            "Q35127",     # website
            "Q4830453",   # business / enterprise
            "Q5157182",   # social networking service
        },
    },
    "history": {
        "P31": {
            "Q198",       # war
            "Q178561",    # battle
            "Q13418847",  # historical period
            "Q350604",    # armed conflict
            "Q1247896",   # conflict
        },
    },
    "geography": {
        "P31": {
            "Q6256",      # country
            "Q515",       # city
            "Q486972",    # human settlement
            "Q8502",      # mountain
            "Q23442",     # island
            "Q4022",      # river
            "Q570116",    # geographic region
            "Q107390",    # federated state
            "Q35657",     # state of the United States
            "Q7275",      # state
        }
    },
    "food_cuisine": {"P31": {"Q2095", "Q746549"}},
    "art_literature": {
        "P31": {
            "Q571",       # book
            "Q7725634",   # literary work
            "Q3305213",   # painting
            "Q95074",     # fictional character
        },
        "P106": {"Q36180", "Q1028181"},
    },
    "mythology_folklore": {"P31": {"Q9134", "Q4271324", "Q178885"}},
    "animals": {
        "P31": {
            "Q729",        # animal (Animalia)
            "Q55983715",   # organisms known by a particular common name
        },
    },
    # Intentionally omit Q420 biology / Q11190 medicine (academic fields):
    # Wikidata P279 chains from attacks/events can reach them and false-tag
    # pages like American Airlines Flight 11.
    "biology_medicine": {
        "P31": {
            "Q12136",   # disease
            "Q808",     # virus
            "Q16521",   # taxon
            "Q12140",   # medication
        },
    },
}

WANTED_BY_PROP: dict[str, dict[str, set[str]]] = {}
for _tag, _prop_map in QID_MAP.items():
    for _prop, _qids in _prop_map.items():
        WANTED_BY_PROP.setdefault(_prop, {}).setdefault(_tag, set()).update(_qids)

API_CALLS = 0


def site_for(lang: str) -> str:
    return f"{lang}wiki"


def chunks(items: list, n: int):
    for i in range(0, len(items), n):
        yield items[i : i + n]


def norm_title(title: str) -> str:
    return title.replace("_", " ").strip()


def api_get(url: str) -> dict:
    """GET with 429/5xx retries. Counts toward API_CALLS once per successful response."""
    global API_CALLS
    delay = SLEEP_S
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": UA, "Accept": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            API_CALLS += 1
            time.sleep(SLEEP_S)
            return data
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code in (429, 500, 502, 503, 504) and attempt + 1 < MAX_RETRIES:
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                wait = float(retry_after) if retry_after and str(retry_after).isdigit() else delay
                wait = max(wait, delay)
                print(f"    HTTP {exc.code}, retry in {wait:.1f}s (attempt {attempt + 1}/{MAX_RETRIES})")
                time.sleep(wait)
                delay = min(delay * 2, 60.0)
                continue
            raise
        except Exception as exc:
            last_exc = exc
            if attempt + 1 < MAX_RETRIES:
                print(f"    error {exc!r}, retry in {delay:.1f}s")
                time.sleep(delay)
                delay = min(delay * 2, 60.0)
                continue
            raise
    raise RuntimeError(f"api_get failed: {last_exc}")


def _entity_id_from_datavalue(val: object) -> str | None:
    if isinstance(val, dict) and "id" in val:
        return val["id"]
    return None


def claim_targets(entity: dict, prop: str) -> set[str]:
    out: set[str] = set()
    for snak in (entity.get("claims") or {}).get(prop, []):
        mainsnak = snak.get("mainsnak") or {}
        dv = mainsnak.get("datavalue") or {}
        eid = _entity_id_from_datavalue(dv.get("value"))
        if eid:
            out.add(eid)
    return out


def claim_entity_ids(entity: dict, prop: str) -> set[str]:
    """Main snak entity IDs plus any qualifier entity IDs (e.g. P360 subject person)."""
    out: set[str] = set()
    for snak in (entity.get("claims") or {}).get(prop, []):
        mainsnak = snak.get("mainsnak") or {}
        dv = mainsnak.get("datavalue") or {}
        eid = _entity_id_from_datavalue(dv.get("value"))
        if eid:
            out.add(eid)
        for qsnaks in (snak.get("qualifiers") or {}).values():
            for qs in qsnaks:
                qdv = qs.get("datavalue") or {}
                qid = _entity_id_from_datavalue(qdv.get("value"))
                if qid:
                    out.add(qid)
    return out


def fetch_entities_by_ids(ids: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for chunk in chunks([i for i in ids if i], BATCH):
        params = {
            "action": "wbgetentities",
            "ids": "|".join(chunk),
            "props": "claims",
            "format": "json",
        }
        url = "https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode(params)
        ents = api_get(url).get("entities") or {}
        out.update(ents)
    return out


def sitelinks_map(entity: dict) -> dict[str, str]:
    """site (enwiki) → article title with spaces."""
    out: dict[str, str] = {}
    for site, info in (entity.get("sitelinks") or {}).items():
        title = info.get("title")
        if title:
            out[site] = title
    return out


class ClaimParentIndex:
    """Lazy parent closure for P279 (subclass) or P171 (parent taxon)."""

    def __init__(self, max_depth: int, prop: str, label: str | None = None) -> None:
        self.max_depth = max_depth
        self.prop = prop
        self.label = label or prop
        self.parents: dict[str, set[str]] = {}
        self.closure: dict[str, set[str]] = {}

    def _ensure_parents(self, qids: set[str]) -> None:
        missing = [q for q in qids if q not in self.parents]
        if not missing:
            return
        ents = fetch_entities_by_ids(missing)
        for qid in missing:
            ent = ents.get(qid) or {}
            if ent.get("missing") is not None:
                self.parents[qid] = set()
            else:
                self.parents[qid] = claim_targets(ent, self.prop)
        print(f"    {self.label} parents +{len(missing)} (cached={len(self.parents)})")

    def ancestors(self, qid: str) -> set[str]:
        if qid in self.closure:
            return self.closure[qid]
        found: set[str] = {qid}
        frontier: set[str] = {qid}
        for _ in range(self.max_depth):
            self._ensure_parents(frontier)
            nxt: set[str] = set()
            for q in frontier:
                for parent in self.parents.get(q, ()):
                    if parent not in found:
                        found.add(parent)
                        nxt.add(parent)
            if not nxt:
                break
            frontier = nxt
        self.closure[qid] = found
        return found

    def expands(self, qids: set[str]) -> set[str]:
        out: set[str] = set()
        for q in qids:
            out |= self.ancestors(q)
        return out


# Back-compat alias
SubclassIndex = ClaimParentIndex


def tags_for_expanded(expanded: dict[str, set[str]]) -> set[str]:
    tags: set[str] = set()
    for prop, tag_wanted in WANTED_BY_PROP.items():
        have = expanded.get(prop, set())
        if not have:
            continue
        for tag, wanted in tag_wanted.items():
            if have & wanted:
                tags.add(tag)
    return tags


def is_sensitive(entity: dict, expanded: dict[str, set[str]]) -> bool:
    if claim_targets(entity, "P3461"):
        return True
    for prop, denylist in SENSITIVE_QIDS.items():
        if expanded.get(prop, set()) & denylist:
            return True
    return False


def finalize_tags(tags: set[str]) -> list[str]:
    return sorted(tags) if tags else [MISC_TAG]


def is_human_entity(p31: set[str], expanded_types: set[str]) -> bool:
    """True if this is (or expands to) a human — blocks Animalia bleed via Q5⊂Animalia."""
    return HUMAN in p31 or HUMAN in expanded_types


def is_animal_entity(
    entity: dict,
    p31: set[str],
    expanded_types: set[str],
    taxon_index: ClaimParentIndex,
) -> bool:
    """
    Animal via non-human P31→Animalia / common-name organism, or any entity whose
    P171 parent-taxon chain reaches Animalia (no taxon-type gate — fossil taxa etc.).
    """
    if is_human_entity(p31, expanded_types):
        return False
    if ANIMALIA in expanded_types:
        return True
    parents = claim_targets(entity, "P171")
    if not parents:
        return False
    return ANIMALIA in taxon_index.expands(parents)


def classify_entity(
    entity: dict,
    subclass: ClaimParentIndex,
    taxon_index: ClaimParentIndex,
) -> tuple[list[str], bool]:
    """
    Multi-tag + sensitive for one Wikidata entity.
    Wikimedia list/internal pages: ignore P31 for categories (avoids website→technology);
    tag from P360/P921 subjects (and their P31/P106) instead.
    Entity P279 is merged into type matching (diseases often subclass disease, not instance).
    Taxon pages under Animalia also get animals (via P171 walk); humans never get animals.
    """
    p31 = claim_targets(entity, "P31")
    p106 = claim_targets(entity, "P106")
    p136 = claim_targets(entity, "P136")
    p279 = claim_targets(entity, "P279")
    p360 = claim_entity_ids(entity, "P360")
    p921 = claim_entity_ids(entity, "P921")

    expanded_p31 = subclass.expands(p31) if p31 else set()
    expanded_p279 = subclass.expands(p279) if p279 else set()
    type_expanded = expanded_p31 | expanded_p279
    list_like = bool(expanded_p31 & WIKI_META_TYPES)

    cat_expanded: dict[str, set[str]] = {
        "P106": subclass.expands(p106) if p106 else set(),
        "P136": subclass.expands(p136) if p136 else set(),
        "P360": subclass.expands(p360) if p360 else set(),
        "P921": subclass.expands(p921) if p921 else set(),
    }
    if not list_like:
        # P279 covers concepts modeled as subclasses (e.g. Ebola ⊂ viral disease ⊂ disease).
        cat_expanded["P31"] = type_expanded
    else:
        # Subject entities (list-of / main-subject + qualifiers) drive real categories.
        # Include subject QIDs themselves (human, film, …) — not only their P31/P279 —
        # so list-of-people gets famous_people (and not animals via Q5⊂Animalia alone).
        subjects = p360 | p921
        if subjects:
            sub_ents = fetch_entities_by_ids(list(subjects))
            sub_p31: set[str] = set()
            sub_p106: set[str] = set()
            sub_p279: set[str] = set()
            for sid in subjects:
                sent = sub_ents.get(sid) or {}
                if sent.get("missing") is not None:
                    continue
                sub_p31 |= claim_targets(sent, "P31")
                sub_p106 |= claim_targets(sent, "P106")
                sub_p279 |= claim_targets(sent, "P279")
            type_seeds = subjects | sub_p31 | sub_p279
            cat_expanded["P31"] = subclass.expands(type_seeds)
            if sub_p106:
                cat_expanded["P106"] = cat_expanded.get("P106", set()) | subclass.expands(sub_p106)

    # Sensitive still sees list P31 + topic props (sexual misconduct via P360, etc.)
    sens_expanded = dict(cat_expanded)
    sens_expanded["P31"] = type_expanded | cat_expanded.get("P31", set())
    sens_expanded["P360"] = cat_expanded.get("P360", set())
    sens_expanded["P921"] = cat_expanded.get("P921", set())

    tags = tags_for_expanded(cat_expanded)
    types_for_animal = cat_expanded.get("P31", set()) | type_expanded
    if is_human_entity(p31, types_for_animal):
        tags.discard("animals")
    elif is_animal_entity(entity, p31, types_for_animal, taxon_index):
        tags.add("animals")
    tags_list = finalize_tags(tags)
    sensitive = is_sensitive(entity, sens_expanded)
    return tags_list, sensitive


def discover_aggregates() -> list[tuple[str, Path]]:
    """Return (lang, path) sorted with EN first (optionally filtered by LANGS_ENABLED)."""
    found: dict[str, Path] = {}
    for path in HERE.glob("pageviews_aggregate_*.json"):
        # pageviews_aggregate_en.json → en
        stem = path.stem  # pageviews_aggregate_en
        lang = stem.split("_")[-1]
        found[lang] = path
    if LANGS_ENABLED is not None:
        found = {lang: path for lang, path in found.items() if lang in LANGS_ENABLED}
    ordered: list[tuple[str, Path]] = []
    for lang in LANG_ORDER_FIRST:
        if lang in found:
            ordered.append((lang, found.pop(lang)))
    for lang in sorted(found):
        ordered.append((lang, found[lang]))
    return ordered


def sample_titles(all_titles: list[str], n: int, seed: int) -> list[str]:
    if n <= 0 or n >= len(all_titles):
        return list(all_titles)
    rng = random.Random(seed)
    return rng.sample(all_titles, n)


def fetch_entities_by_titles(
    titles: list[str], site: str
) -> dict[str, tuple[str | None, dict | None]]:
    result: dict[str, tuple[str | None, dict | None]] = {t: (None, None) for t in titles}
    for chunk in chunks(titles, BATCH):
        wired = [t.replace(" ", "_") for t in chunk]
        params = {
            "action": "wbgetentities",
            "sites": site,
            "titles": "|".join(wired),
            "props": "claims|sitelinks",
            "format": "json",
        }
        url = "https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode(params)
        entities = api_get(url).get("entities") or {}
        by_norm: dict[str, tuple[str | None, dict | None]] = {}
        for eid, ent in entities.items():
            if eid.startswith("-") or ent.get("missing") is not None:
                raw = (ent.get("title") or "").replace("_", " ")
                if raw:
                    by_norm[norm_title(raw)] = (None, None)
                continue
            sl = ((ent.get("sitelinks") or {}).get(site) or {}).get("title") or ""
            if sl:
                by_norm[norm_title(sl)] = (eid, ent)
        for t in chunk:
            hit = by_norm.get(norm_title(t))
            if hit is not None:
                result[t] = hit
    return result


def resolve_redirects_batch(titles: list[str], lang: str) -> dict[str, str]:
    out: dict[str, str] = {t: t for t in titles}
    for chunk in chunks(titles, BATCH):
        params = {
            "action": "query",
            "titles": "|".join(chunk),
            "redirects": "1",
            "format": "json",
        }
        url = f"https://{lang}.wikipedia.org/w/api.php?" + urllib.parse.urlencode(params)
        query = api_get(url).get("query") or {}
        alias: dict[str, str] = {}
        for n in query.get("normalized") or []:
            alias[n["from"]] = n["to"]
        for r in query.get("redirects") or []:
            alias[r["from"]] = r["to"]
        for t in chunk:
            cur = t
            seen: set[str] = set()
            while cur in alias and cur not in seen:
                seen.add(cur)
                cur = alias[cur]
            out[t] = cur
    return out


def resolve_titles(
    titles: list[str], lang: str
) -> tuple[dict[str, tuple[str | None, dict | None]], dict[str, str]]:
    """Return title→(qid, ent), title→canonical."""
    site = site_for(lang)
    title_to = fetch_entities_by_titles(titles, site)
    canonical = {t: t for t in titles}
    misses = [t for t, (q, _) in title_to.items() if q is None]
    if misses:
        canonical.update(resolve_redirects_batch(misses, lang))
        miss_canon: dict[str, list[str]] = {}
        for t in misses:
            miss_canon.setdefault(canonical[t], []).append(t)
        uniq = list(miss_canon.keys())
        retry = fetch_entities_by_titles(uniq, site)
        for c, originals in miss_canon.items():
            q, ent = retry.get(c, (None, None))
            for t in originals:
                title_to[t] = (q, ent)
                canonical[t] = c
    return title_to, canonical


class AnnotationStore:
    """
    qid → {tags, sensitive, sitelinks}
    + reverse index: lang → {norm_title → qid}
    """

    def __init__(self) -> None:
        self.by_qid: dict[str, dict] = {}
        self.by_lang_title: dict[str, dict[str, str]] = {}

    def load(self, path: Path) -> None:
        if not path.is_file():
            return
        raw = json.loads(path.read_text(encoding="utf-8"))
        if int(raw.get("schema") or 1) < CACHE_SCHEMA:
            print(
                f"  ignoring stale QID cache {path.name} "
                f"(schema {raw.get('schema', 1)} < {CACHE_SCHEMA})"
            )
            return
        self.by_qid = raw.get("by_qid") or {}
        for qid, row in self.by_qid.items():
            self._index_sitelinks(qid, row.get("sitelinks") or {})
        print(f"  loaded QID cache: {len(self.by_qid)} entities from {path.name}")

    def save(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {"schema": CACHE_SCHEMA, "by_qid": self.by_qid},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def _index_sitelinks(self, qid: str, sitelinks: dict[str, str]) -> None:
        for site, title in sitelinks.items():
            if not site.endswith("wiki"):
                continue
            lang = site[: -len("wiki")]
            self.by_lang_title.setdefault(lang, {})[norm_title(title)] = qid

    def get(self, qid: str) -> dict | None:
        return self.by_qid.get(qid)

    def lookup_title(self, lang: str, title: str) -> str | None:
        return (self.by_lang_title.get(lang) or {}).get(norm_title(title))

    def put(self, qid: str, tags: list[str], sensitive: bool, sitelinks: dict[str, str]) -> None:
        self.by_qid[qid] = {
            "tags": tags,
            "sensitive": sensitive,
            "sitelinks": sitelinks,
        }
        self._index_sitelinks(qid, sitelinks)


def classify_entities(
    entities_by_qid: dict[str, dict],
    subclass: ClaimParentIndex,
    taxon_index: ClaimParentIndex,
    store: AnnotationStore,
) -> int:
    """Classify QIDs not already in store. Returns number newly classified."""
    fresh = {q: e for q, e in entities_by_qid.items() if q not in store.by_qid and e}
    if not fresh:
        return 0
    print(f"  classifying {len(fresh)} new QIDs (subclass + taxon warm)…")
    seeds: set[str] = set()
    subject_ids: set[str] = set()
    taxon_seeds: set[str] = set()
    for ent in fresh.values():
        for prop in ("P31", "P106", "P136", "P279"):
            seeds |= claim_targets(ent, prop)
        subject_ids |= claim_entity_ids(ent, "P360")
        subject_ids |= claim_entity_ids(ent, "P921")
        taxon_seeds |= claim_targets(ent, "P171")
    seeds |= subject_ids
    if subject_ids:
        # Warm subject entities' types too (list-article enrichment).
        sub_ents = fetch_entities_by_ids(list(subject_ids))
        for sent in sub_ents.values():
            if not sent or sent.get("missing") is not None:
                continue
            seeds |= claim_targets(sent, "P31")
            seeds |= claim_targets(sent, "P106")
            seeds |= claim_targets(sent, "P279")
            taxon_seeds |= claim_targets(sent, "P171")
    if seeds:
        subclass.expands(seeds)
        print(f"  subclass ready (closures={len(subclass.closure)})")
    if taxon_seeds:
        taxon_index.expands(taxon_seeds)
        print(f"  taxon ready (closures={len(taxon_index.closure)})")

    n_new = 0
    for qid, ent in fresh.items():
        tags, sensitive = classify_entity(ent, subclass, taxon_index)
        store.put(qid, tags, sensitive, sitelinks_map(ent))
        n_new += 1
        if n_new % CACHE_SAVE_EVERY == 0:
            store.save(CACHE_PATH)
            print(f"  cache checkpoint ({len(store.by_qid)} QIDs)")
    return n_new


def annotate_language(
    lang: str,
    path: Path,
    subclass: ClaimParentIndex,
    taxon_index: ClaimParentIndex,
    store: AnnotationStore,
) -> dict:
    t0 = time.perf_counter()
    api_before = API_CALLS
    raw = json.loads(path.read_text(encoding="utf-8"))
    pool = list(raw["final_titles_sorted"])
    titles = sample_titles(pool, SAMPLE_N, SEED)
    mode = "sample" if SAMPLE_N > 0 and SAMPLE_N < len(pool) else "full"
    print(
        f"\n=== {lang} ({path.name}) {len(titles)}/{len(pool)} titles [{mode}] ==="
    )

    # Reuse QIDs already known via sitelinks from earlier languages (esp. EN).
    title_qid: dict[str, str | None] = {}
    title_canonical: dict[str, str] = {t: t for t in titles}
    need_api: list[str] = []
    reused_sitelink = 0
    for t in titles:
        q = store.lookup_title(lang, t)
        if q:
            title_qid[t] = q
            reused_sitelink += 1
        else:
            need_api.append(t)

    print(f"  sitelink-cache hits={reused_sitelink} need_resolve={len(need_api)}")

    entities_for_classify: dict[str, dict] = {}
    if need_api:
        resolved, canonical = resolve_titles(need_api, lang)
        title_canonical.update(canonical)
        for t in need_api:
            qid, ent = resolved.get(t, (None, None))
            title_qid[t] = qid
            if qid and ent is not None and qid not in store.by_qid:
                entities_for_classify[qid] = ent
            elif qid and ent is not None and qid in store.by_qid:
                # Refresh sitelink index from this entity if useful
                store._index_sitelinks(qid, sitelinks_map(ent))

    newly = classify_entities(entities_for_classify, subclass, taxon_index, store)
    store.save(CACHE_PATH)

    entries = []
    tag_counts: Counter[str] = Counter()
    no_qid = 0
    misc_only = 0
    sensitive_flagged = 0
    reused_qid = 0

    for t in titles:
        qid = title_qid.get(t)
        canonical = title_canonical.get(t, t)
        if not qid:
            no_qid += 1
            misc_only += 1
            tags = [MISC_TAG]
            sensitive = False
            row = {
                "title": t,
                "canonical_title": canonical,
                "qid": None,
                "tags": tags,
                "sensitive": sensitive,
                "note": "no_wikidata",
            }
        else:
            ann = store.get(qid)
            if ann is None:
                # Shouldn't happen; treat as misc
                no_qid += 1
                misc_only += 1
                tags = [MISC_TAG]
                sensitive = False
                row = {
                    "title": t,
                    "canonical_title": canonical,
                    "qid": qid,
                    "tags": tags,
                    "sensitive": sensitive,
                    "note": "missing_annotation",
                }
            else:
                if qid not in entities_for_classify:
                    reused_qid += 1
                tags = list(ann["tags"])
                sensitive = bool(ann["sensitive"])
                if tags == [MISC_TAG]:
                    misc_only += 1
                if sensitive:
                    sensitive_flagged += 1
                row = {
                    "title": t,
                    "canonical_title": canonical,
                    "qid": qid,
                    "tags": tags,
                    "sensitive": sensitive,
                }
                if canonical != t:
                    row["note"] = f"redirected→{canonical!r}"
        for tag in row["tags"]:
            tag_counts[tag] += 1
        entries.append(row)

    elapsed = time.perf_counter() - t0
    out = {
        "lang": lang,
        "site": site_for(lang),
        "source": path.name,
        "mode": mode,
        "sample_n": SAMPLE_N if mode == "sample" else 0,
        "sample_seed": SEED if mode == "sample" else None,
        "pool_size": len(pool),
        "annotated_count": len(entries),
        "elapsed_s": round(elapsed, 2),
        "api_calls_delta": API_CALLS - api_before,
        "sitelink_cache_hits": reused_sitelink,
        "qid_annotations_reused": reused_qid,
        "new_qids_classified": newly,
        "no_qid": no_qid,
        "miscellaneous_only": misc_only,
        "sensitive_flagged": sensitive_flagged,
        "tag_counts": dict(tag_counts.most_common()),
        "entries": entries,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"pool_annotated_{lang}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"  wrote {out_path.name}  elapsed={elapsed:.1f}s  "
        f"apiΔ={API_CALLS - api_before}  new_qids={newly}  "
        f"sitelink_hits={reused_sitelink}  no_qid={no_qid}  sens={sensitive_flagged}"
    )
    print(f"  tag_counts: {dict(tag_counts.most_common())}")
    return out


def main() -> None:
    global API_CALLS
    API_CALLS = 0
    t0 = time.perf_counter()
    aggregates = discover_aggregates()
    if not aggregates:
        raise SystemExit(f"No pageviews_aggregate_*.json under {HERE}")

    print(
        f"Annotating {len(aggregates)} languages from {HERE}\n"
        f"  SAMPLE_N={SAMPLE_N} (0=full) SEED={SEED} batch={BATCH} sleep={SLEEP_S}\n"
        f"  LANGS_ENABLED={LANGS_ENABLED or 'ALL'}\n"
        f"  subclass_depth={SUBCLASS_DEPTH} taxon_depth={TAXON_DEPTH} cache_schema={CACHE_SCHEMA}\n"
        f"  order: {', '.join(lang for lang, _ in aggregates)}"
    )

    store = AnnotationStore()
    store.load(CACHE_PATH)
    subclass = ClaimParentIndex(SUBCLASS_DEPTH, "P279", "subclass")
    taxon_index = ClaimParentIndex(TAXON_DEPTH, "P171", "taxon")

    summaries = []
    for lang, path in aggregates:
        summaries.append(annotate_language(lang, path, subclass, taxon_index, store))

    store.save(CACHE_PATH)
    elapsed = time.perf_counter() - t0
    summary = {
        "elapsed_s": round(elapsed, 2),
        "api_calls": API_CALLS,
        "qid_cache_size": len(store.by_qid),
        "sample_n": SAMPLE_N,
        "languages": [
            {
                "lang": s["lang"],
                "annotated_count": s["annotated_count"],
                "no_qid": s["no_qid"],
                "miscellaneous_only": s["miscellaneous_only"],
                "sensitive_flagged": s["sensitive_flagged"],
                "sitelink_cache_hits": s["sitelink_cache_hits"],
                "new_qids_classified": s["new_qids_classified"],
                "api_calls_delta": s["api_calls_delta"],
            }
            for s in summaries
        ],
    }
    summary_path = OUT_DIR / "annotate_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDone in {elapsed:.1f}s  api_calls={API_CALLS}  qids_cached={len(store.by_qid)}")
    print(f"Summary → {summary_path}")
    print(f"Pools    → {OUT_DIR / 'pool_annotated_*.json'}")


if __name__ == "__main__":
    main()
