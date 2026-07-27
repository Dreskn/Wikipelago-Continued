from __future__ import annotations

import re
from typing import Any

from BaseClasses import Item, Location
from worlds.AutoWorld import WebWorld, World
from worlds.generic.Rules import set_rule

from .Items import TRAP_ITEM_NAMES, item_table
from .Locations import location_table
from .Options import WikipelagoOptions
from .Regions import create_regions
from .entertainment_articles import ENTERTAINMENT_ARTICLE_POOL
from .letter_pairs import (
    bingo_location_count,
    bingo_slot_location_ids,
    build_letter_pair_bingo_board,
)

# Explicit category tags from the curated pool (preferred over keyword inference).
ARTICLE_TOPIC_BY_TITLE: dict[str, str] = {
    title: topic for title, topic in ENTERTAINMENT_ARTICLE_POOL
}

BANNED_TITLE_KEYWORDS: tuple[str, ...] = (
    "rifle",
    "pistol",
    "shotgun",
    "revolver",
    "machine gun",
    "submachine gun",
    # Avoid bare "gun"/"song"/"album" — false-positives and music pages.
    # Music (song)/(album)/(single) pages are allowed; other junk still blocked below.
    "discography",
    "president",
    "prime minister",
    "king of",
    "queen of",
    "emperor",
    "sultan",
    "chancellor",
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

BANNED_EXACT_TITLES: set[str] = {
    "George Washington",
    "Abraham Lincoln",
    "Theodore Roosevelt",
    "Franklin D. Roosevelt",
    "John F. Kennedy",
    "Winston Churchill",
    "Napoleon",
    "Julius Caesar",
    "Cleopatra",
    "Genghis Khan",
    "Alexander the Great",
}

TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "video_games": (
        "video game", "minecraft", "fortnite", "roblox", "legend of zelda", "Pokémon", "dark souls",
        "elden ring", "halo", "mario", "baldur's gate", "stardew valley", "hollow knight", "celeste",
        "among us", "tetris", "call of duty", "resident evil", "final fantasy", "metroid", "portal",
        "god of war", "mass effect", "bioshock", "terraria", "balatro", "slay the spire",
    ),
    "board_games": (
        "board game", "card game", "chess", "checkers", "catan", "monopoly", "mahjong", "scrabble",
        "go (game)", "dungeons & dragons", "risk (game)", "ticket to ride (board game)",
        "carcassonne (board game)",
    ),
    "movies": (
        "(film)", " film", "movie", "star wars", "the dark knight", "the matrix", "lord of the rings",
        "avengers", "jurassic park", "toy story", "inception", "interstellar", "dune", "oppenheimer",
        "barbie", "gladiator", "titanic", "moana", "frozen", "coco",
    ),
    "tv_shows": (
        "(tv series)", "television series", "tv series", "television show", "breaking bad",
        "stranger things", "game of thrones", "the simpsons", "spongebob", "avatar: the last airbender",
        "friends", "the office", "better call saul", "bluey", "arcane", "house of the dragon",
        "community", "futurama", "gilmore girls", "glee", "hannibal", "heartstopper", "mr. robot",
        "ozark", "scrubs", "suits", "supernatural", "the good place", "the x-files",
    ),
    "anime_manga": (
        "anime", "manga", "naruto", "one piece", "dragon ball", "attack on titan", "death note",
        "demon slayer", "jujutsu kaisen", "my hero academia", "fullmetal alchemist", "bleach",
    ),
    "sports": (
        "football", "basketball", "baseball", "soccer", "tennis", "olympic", "fifa", "nba", "nfl",
        "champions league", "world cup", "formula one", "golf", "cricket", "wwe", "super bowl",
        "wimbledon", "tour de france",
    ),
    "science_space": (
        "astronomy", "planet", "galaxy", "black hole", "physics", "biology", "mathematics",
        "space telescope", "apollo", "mars", "milky way", "quantum", "relativity", "dna", "fossil",
        "solar system", "international space station",
    ),
    "technology": (
        "internet", "computer", "software", "website", "youtube", "google", "wikipedia", "smartphone",
        "artificial intelligence", "virtual reality", "social media", "web browser", "operating system",
        "world wide web", "openai", "mozilla firefox", "google chrome", "microsoft edge",
    ),
    "history": (
        # Avoid bare "war" — false-positives game titles (Warcraft, Gears of War, etc.).
        "ancient", "history of", "renaissance", "industrial revolution", "middle ages",
        "roman empire", "world war", "cold war", "silk road", "black death", "moon landing",
        "ancient egypt", "ancient greece",
    ),
    "geography": (
        "mountain", "river", "desert", "ocean", "national park", "country", "continent",
        "waterfall", "island", "volcano", "forest", "landmark", "amazon rainforest", "mount everest",
        "eiffel tower", "taj mahal",
    ),
    "food_cuisine": (
        # Avoid short substrings "dish"/"tea"/"sushi" — false-positives Dishonored, Steam, Tsushima.
        "cuisine", "food", "pizza", "pasta", "burger", "taco", "ramen",
        "chocolate", "coffee", "ice cream", "sandwich",
    ),
    "art_literature": (
        "novel", "book", "author", "poetry", "painting", "sculpture", "museum", "theater",
        "literature", "shakespeare", "mona lisa", "van gogh", "picasso", "harry potter",
        "the hobbit", "pride and prejudice",
    ),
    "mythology_folklore": (
        # Avoid short substrings like "legend"/"dragon"/"myth"/"vampire" — they false-positive
        # game/show titles (League of Legends, Dragon Age, Age of Mythology, etc.).
        "mythology", "folklore", "greek god", "norse", "werewolf", "mermaid",
        "odin", "zeus", "athena",
    ),
    "music": (
        "musician", "singer", "rapper", "composer", "orchestra", "symphony",
        "grammy", "billboard", "album", "discography", "hip hop", "jazz",
        "rock music", "pop music", "classical music", "the beatles", "taylor swift",
    ),
}

EXACT_TITLE_TOPICS: dict[str, str] = {
    "super bowl": "sports",
    "the matrix": "movies",
    "breaking bad": "tv_shows",
    "stranger things": "tv_shows",
    "friends": "tv_shows",
    "spongebob squarepants": "tv_shows",
    "the simpsons": "tv_shows",
    "game of thrones": "tv_shows",
    "avatar: the last airbender": "tv_shows",
    "bluey": "tv_shows",
    "naruto": "anime_manga",
    "one piece": "anime_manga",
    "death note": "anime_manga",
    "attack on titan": "anime_manga",
    "chess": "board_games",
    "checkers": "board_games",
    "catan": "board_games",
    "go": "board_games",
    "minecraft": "video_games",
    "fortnite": "video_games",
    "roblox": "video_games",
    "dark souls": "video_games",
    "elden ring": "video_games",
    "halo: combat evolved": "video_games",
    "wikipedia": "technology",
    "google": "technology",
    "youtube": "technology",
}

SEARCH_STARTING_LETTERS: dict[int, set[str]] = {
    0: set(),
    1: {"A", "E", "I", "O", "U"},
    2: {"E", "T", "A", "O", "I"},
    3: {"R", "A", "I", "S", "E"},
}

SCROLL_SPEED_UPGRADES = 5


def _preset_goal_name(option_value: int) -> str:
    mapping = {
        0: "Minecraft",
        1: "The Legend of Zelda",
        2: "Dark Souls",
        3: "Elden Ring",
        4: "Super Mario Bros.",
        5: "Pokémon Red and Blue",
        6: "Chess",
        7: "Catan",
        8: "The Dark Knight",
        9: "Star Wars (film)",
        10: "The Lord of the Rings: The Fellowship of the Ring",
        11: "The Matrix",
        12: "Avatar: The Last Airbender",
        13: "Breaking Bad",
        14: "Stranger Things",
        15: "Game of Thrones",
        16: "The Simpsons",
        17: "SpongeBob SquarePants",
        18: "Super Smash Bros. Ultimate",
        19: "Halo: Combat Evolved",
    }
    return mapping.get(option_value, "Minecraft")


def _preset_goal_topic(option_value: int) -> str:
    mapping = {
        0: "video_games",
        1: "video_games",
        2: "video_games",
        3: "video_games",
        4: "video_games",
        5: "video_games",
        6: "board_games",
        7: "board_games",
        8: "movies",
        9: "movies",
        10: "movies",
        11: "movies",
        12: "tv_shows",
        13: "tv_shows",
        14: "tv_shows",
        15: "tv_shows",
        16: "tv_shows",
        17: "tv_shows",
        18: "video_games",
        19: "video_games",
    }
    return mapping.get(option_value, "video_games")


class WikipelagoWeb(WebWorld):
    theme = "stone"


class WikipelagoItem(Item):
    game = "Wikipelago"


class WikipelagoLocation(Location):
    game = "Wikipelago"


class WikipelagoWorld(World):
    game = "Wikipelago"
    web = WikipelagoWeb()

    options_dataclass = WikipelagoOptions
    options: WikipelagoOptions

    item_name_to_id = {name: data.code for name, data in item_table.items()}
    location_name_to_id = {name: data.code for name, data in location_table.items()}
    item_name_groups = {
        "Traps": set(TRAP_ITEM_NAMES),
    }

    item_class = WikipelagoItem
    location_class = WikipelagoLocation

    round_pairs: list[dict[str, str]]
    goal_article: str
    reroll_pool: list[str]
    bingo_letterpairs_board: list[list[str]]

    def _bingo_enabled(self) -> bool:
        return bool(self.options.toggle_bingo_letterpairs.value)

    def _bingo_grid_size(self) -> int:
        return int(self.options.bingo_letterpairs_grid.value) if self._bingo_enabled() else 0

    def _bingo_check_count(self) -> int:
        grid_size = self._bingo_grid_size()
        return bingo_location_count(grid_size) if grid_size else 0

    @staticmethod
    def _is_reasonable_title(title: str) -> bool:
        if len(title) < 3 or len(title) > 120:
            return False
        if "$" in title:
            return False
        if not re.search(r"[A-Za-z]", title):
            return False
        if re.search(r"^[^A-Za-z0-9]+$", title):
            return False
        return True

    @staticmethod
    def _looks_common_knowledge(title: str) -> bool:
        lowered = title.lower().strip()
        if title in BANNED_EXACT_TITLES:
            return False
        if lowered.startswith(("list of ", "outline of ", "timeline of ", "index of ", "category:", "template:", "help:", "portal:")):
            return False
        if any(keyword in lowered for keyword in BANNED_TITLE_KEYWORDS):
            return False
        if any(lowered.endswith(suffix) for suffix in BANNED_TITLE_SUFFIXES):
            return False
        if any(ch in title for ch in ('"', "$", "%", "@", "#")):
            return False
        # Colons are normal in Wikipedia titles (e.g. "The Elder Scrolls V: Skyrim").
        # Namespace-style titles are already rejected by the startswith checks above.
        if title.count(",") > 1:
            return False
        if re.search(r"^\d", title):
            return False
        # Allow music disambiguators; still block pure disambiguation/magazine/journal pages.
        if re.search(r"\(disambiguation|magazine|journal\)$", lowered):
            return False
        if len(title.split()) > 6:
            return False
        if re.search(r"[A-Za-z].*\d.*\d.*\d", title):
            return False
        return True

    def _infer_topic(self, title: str) -> str | None:
        # Prefer explicit pool tags; fall back to heuristics for presets.
        tagged = ARTICLE_TOPIC_BY_TITLE.get(title)
        if tagged:
            return tagged
        lowered = title.lower().strip()
        exact_match = EXACT_TITLE_TOPICS.get(lowered)
        if exact_match:
            return exact_match
        if "(film)" in lowered:
            return "movies"
        if "(tv series)" in lowered or "television series" in lowered:
            return "tv_shows"
        if "(video game)" in lowered:
            return "video_games"
        if "(board game)" in lowered:
            return "board_games"
        if re.search(r"\((song|album|single|band|musician|rapper|singer)\)$", lowered):
            return "music"
        for topic, keywords in TOPIC_KEYWORDS.items():
            if any(keyword in lowered for keyword in keywords):
                return topic
        return None

    def _selected_topics(self) -> set[str]:
        selected: set[str] = set()
        if self.options.include_video_games.value:
            selected.add("video_games")
        if self.options.include_board_games.value:
            selected.add("board_games")
        if self.options.include_movies.value:
            selected.add("movies")
        if self.options.include_tv_shows.value:
            selected.add("tv_shows")
        if self.options.include_anime_manga.value:
            selected.add("anime_manga")
        if self.options.include_sports.value:
            selected.add("sports")
        if self.options.include_science_space.value:
            selected.add("science_space")
        if self.options.include_technology.value:
            selected.add("technology")
        if self.options.include_history.value:
            selected.add("history")
        if self.options.include_geography.value:
            selected.add("geography")
        if self.options.include_food_cuisine.value:
            selected.add("food_cuisine")
        if self.options.include_art_literature.value:
            selected.add("art_literature")
        if self.options.include_mythology_folklore.value:
            selected.add("mythology_folklore")
        if self.options.include_music.value:
            selected.add("music")
        return selected

    def _filter_pool_by_topics(self, pool: list[str], selected_topics: set[str]) -> list[str]:
        return [title for title in pool if self._infer_topic(title) in selected_topics]

    def _search_starting_letters(self) -> set[str]:
        return set(SEARCH_STARTING_LETTERS.get(self.options.search_starting_letters.value, set()))

    def _display_unlock_items(self) -> list[str]:
        unlocks: list[str] = []
        if self.options.randomize_tables.value:
            unlocks.append("Table Lens")
        if self.options.randomize_pictures.value:
            unlocks.append("Picture Lens")
        if self.options.randomize_incipit.value:
            unlocks.append("Lead Lens")
        if self.options.randomize_infoboxes.value:
            unlocks.append("Infobox Lens")
        if self.options.randomize_toc.value:
            unlocks.append("Contents Lens")
        if self.options.randomize_navboxes.value:
            unlocks.append("Navbox Lens")
        if self.options.randomize_hatnotes.value:
            unlocks.append("Hatnote Lens")
        if self.options.randomize_references.value:
            unlocks.append("Reference Lens")
        return unlocks

    def generate_early(self) -> None:
        round_count = self.options.check_count.value
        selected_topics = self._selected_topics()
        if not selected_topics:
            raise Exception(
                "Wikipelago requires at least one enabled category. "
                "Enable one or more category toggles in your YAML (games/movies/shows/anime/sports/science/tech/history/geography/food/art/mythology/music)."
            )

        pool = list(dict.fromkeys(title for title, _topic in ENTERTAINMENT_ARTICLE_POOL))
        filtered_pool = [
            title for title in pool
            if self._is_reasonable_title(title)
            and self._looks_common_knowledge(title)
            and self._infer_topic(title) is not None
        ]
        filtered_pool = self._filter_pool_by_topics(filtered_pool, selected_topics)

        # Unique titles: one random opening start + one target per round (last = goal).
        needed_total = max(2, round_count + 1)
        max_rounds_for_pool = max(0, len(filtered_pool) - 1)
        if len(filtered_pool) < needed_total:
            raise Exception(
                "Wikipelago cannot generate this seed: "
                f"check_count={round_count} needs at least {needed_total} unique usable articles, "
                f"but the enabled categories only provide {len(filtered_pool)} "
                f"(supports at most {max_rounds_for_pool} rounds). "
                "Lower check_count or enable more article categories."
            )

        if self.options.random_goal_article.value:
            self.goal_article = self.random.choice(filtered_pool)
        else:
            goal_preset_value = self.options.goal_article_preset.value
            self.goal_article = _preset_goal_name(goal_preset_value)
            goal_topic = _preset_goal_topic(goal_preset_value)
            if goal_topic not in selected_topics:
                raise Exception(
                    "Wikipelago goal article preset category is disabled. "
                    f"Goal '{self.goal_article}' is in category '{goal_topic}'. "
                    "Enable that category or set random_goal_article: true."
                )
            if self.goal_article not in filtered_pool:
                filtered_pool.append(self.goal_article)

        remaining = [title for title in filtered_pool if title != self.goal_article]
        # First-round opening start + non-goal targets (later rounds continue from prior target).
        needed_from_remaining = round_count
        if len(remaining) < needed_from_remaining:
            raise Exception(
                "Wikipelago cannot generate this seed: "
                f"check_count={round_count} needs {needed_from_remaining + 1} unique usable articles "
                f"(including the goal), but only {len(remaining) + 1} are available after filtering. "
                "Lower check_count or enable more article categories."
            )

        picks = self.random.sample(remaining, needed_from_remaining)
        first_start = picks[0]
        non_final_targets = picks[1:]
        targets = non_final_targets + [self.goal_article]
        starts = [first_start, *targets[:-1]]
        self.round_pairs = [
            {"start": start, "target": target}
            for start, target in zip(starts, targets)
        ]
        used_titles = {first_start, *targets}
        # Leftover titles for client-side target rerolls (same filtered category pool).
        self.reroll_pool = [title for title in filtered_pool if title not in used_titles]

        if self._bingo_enabled():
            self.bingo_letterpairs_board = build_letter_pair_bingo_board(
                self.random, self._bingo_grid_size()
            )
        else:
            self.bingo_letterpairs_board = []

    def create_regions(self) -> None:
        create_regions(self)

    def create_item(self, name: str) -> WikipelagoItem:
        data = item_table[name]
        return self.item_class(name, data.classification, data.code, self.player)

    def create_items(self) -> None:
        round_count = self.options.check_count.value
        bingo_count = self._bingo_check_count()
        free_locations = round_count + bingo_count
        required_fragments = min(self.options.required_fragments.value, round_count)
        start_unlocked = min(self.options.start_rounds_unlocked.value, round_count)
        per_unlock = max(1, self.options.rounds_per_unlock.value)
        early_open = start_unlocked
        round_access_count = max(0, (round_count - early_open + per_unlock - 1) // per_unlock)
        search_letters_needed = 26 - len(self._search_starting_letters()) if self.options.searchsanity.value else 0
        scroll_upgrades_needed = SCROLL_SPEED_UPGRADES if self.options.scrollsanity.value else 0
        display_unlocks = self._display_unlock_items()
        trap_count = int(self.options.trap_count.value)

        mandatory_items = (
            required_fragments
            + 3
            + round_access_count
            + search_letters_needed
            + scroll_upgrades_needed
            + len(display_unlocks)
            + trap_count
        )
        if mandatory_items > free_locations:
            raise Exception(
                "Wikipelago item math invalid: required progression items exceed free locations. "
                f"mandatory={mandatory_items}, free_locations={free_locations} "
                f"(rounds={round_count}, bingo={bingo_count}). "
                "Lower required_fragments, trap_count, reduce sanity/display unlock load, or lower round access pressure "
                "(increase start_rounds_unlocked / rounds_per_unlock)."
            )

        pool: list[WikipelagoItem] = []
        for _ in range(required_fragments):
            pool.append(self.create_item("Knowledge Fragment"))
        pool.append(self.create_item("Back Button"))
        pool.append(self.create_item("Wiki Compass"))
        pool.append(self.create_item("Ctrl+F Lens"))
        if self.options.scrollsanity.value:
            for _ in range(SCROLL_SPEED_UPGRADES):
                pool.append(self.create_item("Progressive Scroll Speed"))
        if self.options.searchsanity.value:
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                if letter not in self._search_starting_letters():
                    pool.append(self.create_item(f"Search Letter {letter}"))
        for unlock_name in display_unlocks:
            pool.append(self.create_item(unlock_name))
        for _ in range(round_access_count):
            pool.append(self.create_item("Round Access"))
        for trap_name in self._trap_item_names(trap_count):
            pool.append(self.create_item(trap_name))
        while len(pool) < free_locations:
            pool.append(self.create_item("Footnote"))

        self.multiworld.itempool.extend(pool)
        grand_goal = self.multiworld.get_location("Grand Goal", self.player)
        grand_goal.place_locked_item(self.create_item("Victory"))

    def _trap_item_names(self, trap_count: int) -> list[str]:
        if trap_count <= 0:
            return []
        trap_type = int(self.options.trap_type.value)
        if trap_type == 1:
            return ["Foggy Links"] * trap_count
        if trap_type == 2:
            return ["Missing Links"] * trap_count
        names: list[str] = []
        for _ in range(trap_count):
            names.append(self.random.choice(["Foggy Links", "Missing Links"]))
        return names

    def set_rules(self) -> None:
        round_count = self.options.check_count.value
        required_fragments = min(self.options.required_fragments.value, round_count)
        start_unlocked = min(self.options.start_rounds_unlocked.value, round_count)
        per_unlock = max(1, self.options.rounds_per_unlock.value)
        early_open = start_unlocked

        goal_location = self.multiworld.get_location("Grand Goal", self.player)
        set_rule(
            goal_location,
            lambda state, frag_need=required_fragments: state.has("Knowledge Fragment", self.player, frag_need),
        )

        for round_index in range(1, round_count + 1):
            location = self.multiworld.get_location(f"Round {round_index} Complete", self.player)
            extra_rounds = max(0, round_index - early_open)
            needed_round_access = (extra_rounds + per_unlock - 1) // per_unlock
            set_rule(
                location,
                lambda state, need=needed_round_access: state.has("Round Access", self.player, need),
            )

        self.multiworld.completion_condition[self.player] = lambda state: state.has("Victory", self.player)

    def fill_slot_data(self) -> dict[str, Any]:
        round_count = self.options.check_count.value
        required_fragments = min(self.options.required_fragments.value, round_count)
        start_unlocked = min(self.options.start_rounds_unlocked.value, round_count)
        per_unlock = max(1, self.options.rounds_per_unlock.value)
        round_location_ids = [
            self.location_name_to_id[f"Round {index} Complete"]
            for index in range(1, round_count + 1)
        ]
        bingo_enabled = self._bingo_enabled()
        bingo_grid = self._bingo_grid_size()
        bingo_board = list(getattr(self, "bingo_letterpairs_board", []) or [])
        location_ids: dict[str, Any] = {
            "rounds": round_location_ids,
            "grand_goal": self.location_name_to_id["Grand Goal"],
        }
        if bingo_enabled:
            location_ids["bingo_letterpairs"] = bingo_slot_location_ids(
                self.location_name_to_id, bingo_grid
            )

        return {
            "check_count": round_count,
            "required_fragments": required_fragments,
            "start_rounds_unlocked": start_unlocked,
            "rounds_per_unlock": per_unlock,
            "goal_article": self.goal_article,
            "round_pairs": self.round_pairs,
            "reroll_pool": list(getattr(self, "reroll_pool", [])),
            "searchsanity": bool(self.options.searchsanity.value),
            "scrollsanity": bool(self.options.scrollsanity.value),
            "scroll_speed_upgrades": SCROLL_SPEED_UPGRADES,
            "search_starting_letters": sorted(self._search_starting_letters()),
            "randomize_tables": bool(self.options.randomize_tables.value),
            "randomize_pictures": bool(self.options.randomize_pictures.value),
            "randomize_incipit": bool(self.options.randomize_incipit.value),
            "randomize_infoboxes": bool(self.options.randomize_infoboxes.value),
            "randomize_toc": bool(self.options.randomize_toc.value),
            "randomize_navboxes": bool(self.options.randomize_navboxes.value),
            "randomize_hatnotes": bool(self.options.randomize_hatnotes.value),
            "randomize_references": bool(self.options.randomize_references.value),
            "deaths": bool(self.options.deaths.value),
            "death_link": bool(self.options.death_link.value),
            "link_bombs": bool(self.options.link_bombs.value),
            "link_bomb_density": int(self.options.link_bomb_density.value),
            "trap_count": int(self.options.trap_count.value),
            "trap_type": int(self.options.trap_type.value),
            "trap_link": bool(self.options.trap_link.value),
            "bingo_letterpairs": bingo_enabled,
            "bingo_letterpairs_grid": bingo_grid if bingo_enabled else 0,
            "bingo_letterpairs_board": bingo_board if bingo_enabled else [],
            "location_ids": location_ids,
            "item_ids": {name: data.code for name, data in item_table.items()},
        }






