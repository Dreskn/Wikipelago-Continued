import argparse
import json
import random
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

API = "https://en.wikipedia.org/w/api.php"
ROOT = Path(__file__).resolve().parent / "APWorldSource" / "wikipelago"
OUT_PATH = ROOT / "article_pool.json"
STATE_PATH = ROOT / "article_pool_state.json"

TOPIC_CATEGORIES: list[str] = [
    "Category:Video games",
    "Category:Esports games",
    "Category:Board games",
    "Category:Computer games",
    "Category:Game engines",
    "Category:Programming languages",
    "Category:Software",
    "Category:Internet culture",
    "Category:Websites",
    "Category:Artificial intelligence",
    "Category:Companies",
    "Category:Economics",
    "Category:Finance",
    "Category:Cities",
    "Category:Countries",
    "Category:Geography",
    "Category:Rivers",
    "Category:Mountains",
    "Category:Architecture",
    "Category:Transportation",
    "Category:Spaceflight",
    "Category:Astronomy",
    "Category:Physics",
    "Category:Chemistry",
    "Category:Biology",
    "Category:Mathematics",
    "Category:Medicine",
    "Category:Engineering",
    "Category:History",
    "Category:Ancient history",
    "Category:Wars",
    "Category:Political history",
    "Category:Philosophy",
    "Category:Religion",
    "Category:Mythology",
    "Category:Literature",
    "Category:Novels",
    "Category:Poetry",
    "Category:Films",
    "Category:Television",
    "Category:Actors",
    "Category:Directors",
    "Category:Music",
    "Category:Albums",
    "Category:Songs",
    "Category:Musicians",
    "Category:Sports",
    "Category:Olympic Games",
    "Category:Association football",
    "Category:Basketball",
    "Category:Baseball",
    "Category:Food and drink",
    "Category:Cuisine",
    "Category:Animals",
    "Category:Plants",
    "Category:Weather",
    "Category:Natural disasters",
    "Category:Universities and colleges",
    "Category:Education",
    "Category:Law",
]

BLOCK_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^\W+$"),
    re.compile(r"\(disambiguation\)$", re.IGNORECASE),
    re.compile(r"^List of ", re.IGNORECASE),
    re.compile(r"^Index of ", re.IGNORECASE),
    re.compile(r"^Category:", re.IGNORECASE),
    re.compile(r"^File:", re.IGNORECASE),
    re.compile(r"^Template:", re.IGNORECASE),
    re.compile(r"^Portal:", re.IGNORECASE),
    re.compile(r"^Talk:", re.IGNORECASE),
    re.compile(r"^Help:", re.IGNORECASE),
    re.compile(r"^Special:", re.IGNORECASE),
    re.compile(r"^Wikipedia:", re.IGNORECASE),
]


def api_get(params: dict[str, Any], timeout: int = 60) -> dict[str, Any]:
    query = urllib.parse.urlencode(params)
    url = f"{API}?{query}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "WikipelagoPoolBuilder/1.0 (https://github.com/Skrumptily69/Wikipelago; contact: wiki@local)",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def good_title(title: str) -> bool:
    t = title.strip()
    if not t:
        return False
    if len(t) < 3 or len(t) > 120:
        return False
    if "$" in t:
        return False
    if not re.search(r"[A-Za-z]", t):
        return False
    if t[0] in '"\'!@#$%^&*()[]{}<>?/\\|`~':
        return False
    for pat in BLOCK_PATTERNS:
        if pat.search(t):
            return False
    return True


def fetch_category_chunk(category: str, cmcontinue: str | None) -> tuple[list[str], str | None]:
    params: dict[str, Any] = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": category,
        "cmnamespace": 0,
        "cmtype": "page",
        "cmlimit": 500,
        "format": "json",
    }
    if cmcontinue:
        params["cmcontinue"] = cmcontinue

    payload = api_get(params)
    members = payload.get("query", {}).get("categorymembers", [])
    titles = [str(m.get("title", "")).strip() for m in members if m.get("title")]
    token = payload.get("continue", {}).get("cmcontinue")
    return titles, token


def fetch_random_chunk(limit: int = 500) -> list[str]:
    payload = api_get(
        {
            "action": "query",
            "list": "random",
            "rnnamespace": 0,
            "rnlimit": max(1, min(500, limit)),
            "format": "json",
        }
    )
    pages = payload.get("query", {}).get("random", [])
    return [str(p.get("title", "")).strip() for p in pages if p.get("title")]


def fetch_allpages_chunk(apcontinue: str | None) -> tuple[list[str], str | None]:
    params: dict[str, Any] = {
        "action": "query",
        "list": "allpages",
        "apnamespace": 0,
        "apfilterredir": "nonredirects",
        "aplimit": 500,
        "format": "json",
    }
    if apcontinue:
        params["apcontinue"] = apcontinue

    payload = api_get(params)
    pages = payload.get("query", {}).get("allpages", [])
    titles = [str(p.get("title", "")).strip() for p in pages if p.get("title")]
    token = payload.get("continue", {}).get("apcontinue")
    return titles, token


def load_existing() -> list[str]:
    if not OUT_PATH.exists():
        return []
    try:
        data = json.loads(OUT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return [str(x).strip() for x in data if isinstance(x, str) and good_title(str(x))]


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {}
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_state(titles: list[str], state: dict[str, Any]) -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(titles, ensure_ascii=False, indent=2), encoding="utf-8")
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def build_pool(target_count: int, keep_existing: bool, random_share: float, seed: int) -> list[str]:
    rng = random.Random(seed)

    titles = load_existing() if keep_existing else []
    seen = set(titles)

    state = load_state()
    category_tokens: dict[str, str | None] = state.get("category_tokens", {}) if isinstance(state.get("category_tokens"), dict) else {}
    allpages_token: str | None = state.get("allpages_token") if isinstance(state.get("allpages_token"), str) else None

    print(f"Starting with {len(titles)} titles")

    random_share = max(0.0, min(1.0, random_share))

    topic_index = 0
    stalls = 0
    last_saved_count = len(titles)
    had_error = False

    while len(titles) < target_count and stalls < 800:
        added_this_cycle = 0

        category = TOPIC_CATEGORIES[topic_index % len(TOPIC_CATEGORIES)]
        topic_index += 1
        token = category_tokens.get(category)
        try:
            chunk, next_token = fetch_category_chunk(category, token)
            category_tokens[category] = next_token
            for title in chunk:
                if not good_title(title) or title in seen:
                    continue
                seen.add(title)
                titles.append(title)
                added_this_cycle += 1
                if len(titles) >= target_count:
                    break
        except Exception as exc:
            if not had_error:
                print(f"Category fetch error ({category}): {exc}")
                had_error = True

        if len(titles) >= target_count:
            break

        want_random = (added_this_cycle == 0) or (rng.random() < random_share)
        if want_random:
            try:
                rand_chunk = fetch_random_chunk(500)
                for title in rand_chunk:
                    if not good_title(title) or title in seen:
                        continue
                    seen.add(title)
                    titles.append(title)
                    added_this_cycle += 1
                    if len(titles) >= target_count:
                        break
            except Exception:
                pass

        if added_this_cycle == 0:
            try:
                ap_chunk, next_ap = fetch_allpages_chunk(allpages_token)
                allpages_token = next_ap
                for title in ap_chunk:
                    if not good_title(title) or title in seen:
                        continue
                    seen.add(title)
                    titles.append(title)
                    added_this_cycle += 1
                    if len(titles) >= target_count:
                        break
            except Exception:
                pass

        if added_this_cycle == 0:
            stalls += 1
        else:
            stalls = 0

        if len(titles) - last_saved_count >= 1000:
            save_state(titles, {"category_tokens": category_tokens, "allpages_token": allpages_token})
            last_saved_count = len(titles)
            print(f"Progress: {len(titles)} titles")

        time.sleep(0.03)

    rng.shuffle(titles)
    save_state(titles, {"category_tokens": category_tokens, "allpages_token": allpages_token})
    return titles


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a broad and diverse Wikipelago article pool")
    parser.add_argument("--target-count", type=int, default=5000)
    parser.add_argument("--replace", action="store_true", help="ignore existing pool and rebuild from scratch")
    parser.add_argument("--random-share", type=float, default=0.35, help="fraction of cycles that also include random-page chunks")
    parser.add_argument("--seed", type=int, default=1337)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    target_count = max(100, args.target_count)
    titles = build_pool(
        target_count=target_count,
        keep_existing=not args.replace,
        random_share=args.random_share,
        seed=args.seed,
    )
    print(f"Saved {len(titles)} article titles to {OUT_PATH}")


if __name__ == "__main__":
    main()

