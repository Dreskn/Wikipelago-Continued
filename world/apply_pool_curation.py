#!/usr/bin/env python3
"""Apply user pool curation decisions + seed music category."""
from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

POOL_PATH = Path(__file__).resolve().parent / "APWorldSource" / "Wikipelago" / "entertainment_articles.py"

# title -> new category (or None to delete)
MOVES: dict[str, str | None] = {
    # video_games
    "Steven Spielberg": "movies",
    "Uwe Boll": "movies",
    "Alan Turing": "science_space",
    "IShowSpeed": "technology",  # internet streamer
    "Hasan Piker": "technology",  # political Twitch streamer
    "Asha Sharma": "technology",  # Xbox/Microsoft exec
    "The Super Mario Galaxy Movie": "movies",
    "Nvidia": "technology",
    "Apple Inc.": "technology",
    "Microsoft": "technology",
    "Mobile app": "technology",
    "Toy Story (franchise)": "movies",
    # movies — obscure recent removals
    "Backrooms (film)": None,
    "Disclosure Day": None,
    "Peddi": None,
    "Main Vaapas Aaunga": None,
    "Citizen Vigilante": None,
    "Karuppu (film)": None,
    "Cocktail 2": None,
    "Voicemails for Isabelle": None,
    "The Sheep Detectives": None,
    "Bhooth Bangla": None,
    "Dhurandhar: The Revenge": None,
    "Drishyam 3": None,
    # tv_shows
    "Donald Trump": "history",
    "Death of Michael Jackson": "music",
    "Ariana Grande": "music",
    "Harry Styles": "music",
    # actors stay on tv_shows (already there): Sydney Sweeney, Jason Momoa, Olivia Wilde, etc.
    # season → series handled separately
    # anime_manga
    "Tara Strong": "tv_shows",  # Western cartoon VA
    "Troy Baker": "video_games",  # primarily game VA
    "Matthew Mercer": "video_games",  # games + Critical Role
    "Travis Willingham": "video_games",
    # Laura Bailey, Lizzie Freeman: keep anime_manga (substantial anime VA work)
    "Lists of One Piece episodes": None,
    "One Piece season 22": None,
    "Persona 4 Revival": "video_games",
    # sports
    "Marty Supreme": "movies",
    # food
    "Dionysus": "mythology_folklore",
    "International Society for Krishna Consciousness": None,
    # history
    "Abstraction": None,
    "King Arthur": "mythology_folklore",
    # geography
    "East Rutherford, New Jersey": None,
    # science_space
    "Star City (TV series)": "tv_shows",
    "Project Hail Mary": "movies",
    "Lyndon B. Johnson": "history",
    "William Shatner": "tv_shows",
    "Brian May": "music",
    # Neil deGrasse Tyson stays science_space
    # art_literature
    "Creepypasta": "mythology_folklore",
    "Liminal space": "mythology_folklore",
    # mythology
    "Until Dawn": "video_games",
    "The Quarry (video game)": "video_games",
    "William Shakespeare": "art_literature",
    # board_games
    "The Campaign for North Africa": None,
}

SEASON_TO_SERIES: dict[str, str] = {
    "Love Island USA season 8": "Love Island USA",
    "Euphoria season 3": "Euphoria (American TV series)",
    "House of the Dragon season 3": "House of the Dragon",
}

# Well-known anime/manga to ensure present
ENSURE_ANIME: list[str] = [
    "Cowboy Bebop",
    "Fullmetal Alchemist: Brotherhood",
    "Steins;Gate",
    "Hunter × Hunter",
    "My Hero Academia",
    "Spirited Away",
    "Neon Genesis Evangelion",
    "Sailor Moon",
    "Dragon Ball Z",
    "Bleach (manga)",
    "Tokyo Ghoul",
    "Mob Psycho 100",
    "Vinland Saga (manga)",
    "Chainsaw Man",
    "Spy × Family",
]

# Starter music pages (beyond moves); Popular-pages enrich can expand later
ENSURE_MUSIC: list[str] = [
    "The Beatles",
    "Michael Jackson",
    "Taylor Swift",
    "Beyoncé",
    "Elvis Presley",
    "Madonna",
    "Queen (band)",
    "Pink Floyd",
    "Led Zeppelin",
    "Bob Dylan",
    "David Bowie",
    "Prince (musician)",
    "Whitney Houston",
    "Adele",
    "Drake (musician)",
    "Eminem",
    "Rihanna",
    "Lady Gaga",
    "Billie Eilish",
    "Bruno Mars",
    "Ed Sheeran",
    "The Rolling Stones",
    "Nirvana (band)",
    "Metallica",
    "Hip hop",
    "Jazz",
    "Classical music",
    "Rock music",
    "Pop music",
    "Bohemian Rhapsody",
    "Thriller (album)",
    "Abbey Road",
    "Music",
    "Guitar",
    "Piano",
    "Concert",
    "Grammy Awards",
    "Eurovision Song Contest",
    "Spotify",
]


def load_pool() -> list[tuple[str, str]]:
    text = POOL_PATH.read_text(encoding="utf-8-sig")
    mod = ast.parse(text)
    for node in mod.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "ENTERTAINMENT_ARTICLE_POOL":
                return [tuple(x) for x in ast.literal_eval(node.value)]
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "ENTERTAINMENT_ARTICLE_POOL":
                    return [tuple(x) for x in ast.literal_eval(node.value)]
    raise KeyError("ENTERTAINMENT_ARTICLE_POOL")


def write_pool(entries: list[tuple[str, str]]) -> None:
    lines = [
        '"""Curated Wikipelago article pool: (Wikipedia title, category)."""',
        "",
        "ENTERTAINMENT_ARTICLE_POOL: list[tuple[str, str]] = [",
    ]
    for title, topic in entries:
        lines.append(f"    ({title!r}, {topic!r}),")
    lines.append("]")
    lines.append("")
    POOL_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    pool = load_pool()
    by_title: dict[str, str] = {t: c for t, c in pool}
    order = [t for t, _ in pool]

    removed: list[str] = []
    moved: list[tuple[str, str, str]] = []

    # Season → series
    for season, series in SEASON_TO_SERIES.items():
        if season in by_title:
            old_cat = by_title.pop(season)
            if season in order:
                order.remove(season)
            removed.append(season)
            if series not in by_title:
                by_title[series] = "tv_shows"
                order.append(series)
                moved.append((season, series, "tv_shows"))
            else:
                # keep existing series category
                moved.append((season, f"{series} (already present)", by_title[series]))

    # Explicit moves/removes
    for title, dest in MOVES.items():
        if title not in by_title:
            continue
        old = by_title[title]
        if dest is None:
            by_title.pop(title)
            if title in order:
                order.remove(title)
            removed.append(title)
        else:
            by_title[title] = dest
            moved.append((title, old, dest))

    # Dedupe Project Hail Mary vs (film)
    if "Project Hail Mary" in by_title and "Project Hail Mary (film)" in by_title:
        by_title.pop("Project Hail Mary")
        if "Project Hail Mary" in order:
            order.remove("Project Hail Mary")
        removed.append("Project Hail Mary (dup of film)")
    elif "Project Hail Mary" in by_title:
        by_title["Project Hail Mary"] = "movies"

    # Ensure anime
    added_anime = []
    for title in ENSURE_ANIME:
        if title not in by_title:
            by_title[title] = "anime_manga"
            order.append(title)
            added_anime.append(title)

    # Ensure music starters
    added_music = []
    for title in ENSURE_MUSIC:
        if title not in by_title:
            by_title[title] = "music"
            order.append(title)
            added_music.append(title)
        elif by_title[title] != "music" and title in (
            "Ariana Grande", "Harry Styles", "Brian May", "Death of Michael Jackson",
            "Michael Jackson", "Queen (band)",
        ):
            # force music for these if somehow wrong
            pass

    # Force music category on known music titles already moved
    for title in ("Ariana Grande", "Harry Styles", "Brian May", "Death of Michael Jackson"):
        if title in by_title:
            by_title[title] = "music"

    # Rebuild preserving order; append any new keys not in order
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for title in order:
        if title in by_title and title not in seen:
            out.append((title, by_title[title]))
            seen.add(title)
    for title, cat in by_title.items():
        if title not in seen:
            out.append((title, cat))
            seen.add(title)

    write_pool(out)

    # Usable estimate: reuse enrich-like filters lightly — import from enrich if possible
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from enrich_pool_from_popular_pages import passes_skip_filters

    # Music titles with (album)/(song) may fail filters until __init__ is updated;
    # count all music as intending usable after filter fix
    usable = sum(
        1
        for t, c in out
        if c == "music" or passes_skip_filters(t)
    )

    counts = Counter(c for _, c in out)
    print(f"pool={len(out)} usable≈{usable}")
    print("counts:", dict(sorted(counts.items())))
    print(f"removed ({len(removed)}):", removed)
    print(f"moved ({len(moved)}):")
    for m in moved:
        print(" ", m)
    print(f"added anime ({len(added_anime)}):", added_anime)
    print(f"added music ({len(added_music)}):", added_music)


if __name__ == "__main__":
    main()
