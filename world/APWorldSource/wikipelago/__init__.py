from __future__ import annotations

import re
from typing import Any

from BaseClasses import Item, ItemClassification, Location
from worlds.AutoWorld import WebWorld, World
from worlds.generic.Rules import set_rule

from .Items import TRAP_ITEM_NAMES, item_table
from .Locations import MAX_BINGO_BOARDS, MAX_BRANCHES, MAX_BRANCH_LENGTH, branch_location_name, location_table
from .Options import WikipelagoOptions
from .Regions import create_regions
from .article_pool import SUPPORTED_LANGS, load_article_pool
from .grand_goal import pick_grand_goal_card
from .letter_pairs import (
    bingo_location_count,
    bingo_location_names,
    bingo_slot_location_ids_by_board,
    build_letter_pair_bingo_board,
)

WIKIPEDIA_LANG_BY_OPTION: dict[int, str] = {
    0: "en",
    1: "fr",
    2: "de",
    3: "es",
    4: "it",
    5: "pt",
    6: "nl",
    7: "sv",
    8: "pl",
}

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

TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "video_games": (
        "video game", "minecraft", "fortnite", "roblox", "legend of zelda", "Pokémon", "dark souls",
        "elden ring", "halo", "mario", "baldur's gate", "stardew valley", "hollow knight", "celeste",
        "among us", "tetris", "call of duty", "resident evil", "final fantasy", "metroid", "portal",
        "god of war", "mass effect", "bioshock", "terraria", "balatro", "slay the spire",
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
    "chess": "miscellaneous",
    "checkers": "miscellaneous",
    "catan": "miscellaneous",
    "go": "miscellaneous",
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
    goal_question: str
    goal_qid: str | None
    reroll_pool: list[str]
    bingo_letterpairs_boards: list[list[list[str]]]
    crossroads: list[dict[str, int]]
    branches: list[dict[str, Any]]

    def _bingo_enabled(self) -> bool:
        return bool(self.options.toggle_bingo_letterpairs.value)

    def _bingo_grid_size(self) -> int:
        return int(self.options.bingo_letterpairs_grid.value) if self._bingo_enabled() else 0

    def _bingo_cards_start(self) -> int:
        if not self._bingo_enabled():
            return 0
        return max(0, int(self.options.bingo_cards_start.value))

    def _bingo_card_unlocks(self) -> int:
        if not self._bingo_enabled():
            return 0
        return max(0, int(self.options.bingo_card_unlocks.value))

    def _bingo_stamp_unlocks(self) -> int:
        if not self._bingo_enabled():
            return 0
        return max(0, int(self.options.bingo_stamp_unlocks.value))

    def _bingo_board_count(self) -> int:
        if not self._bingo_enabled():
            return 0
        total = self._bingo_cards_start() + self._bingo_card_unlocks()
        if total <= 0:
            raise Exception(
                "Wikipelago bingo is enabled but no boards are available: "
                "bingo_cards_start and bingo_card_unlocks are both 0. "
                "Set bingo_cards_start >= 1, add bingo_card_unlocks, or disable toggle_bingo_letterpairs."
            )
        if total > MAX_BINGO_BOARDS:
            raise Exception(
                "Wikipelago bingo board count exceeds datapackage limit: "
                f"bingo_cards_start + bingo_card_unlocks = {total}, max={MAX_BINGO_BOARDS}."
            )
        return total

    def _bingo_check_count(self) -> int:
        grid_size = self._bingo_grid_size()
        if not grid_size:
            return 0
        return bingo_location_count(grid_size) * self._bingo_board_count()

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
        if lowered.startswith(("list of ", "outline of ", "timeline of ", "index of ", "category:", "template:", "help:", "portal:", "wikipedia:")):
            return False
        if any(keyword in lowered for keyword in BANNED_TITLE_KEYWORDS):
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

    def _wikipedia_language(self) -> str:
        return WIKIPEDIA_LANG_BY_OPTION.get(int(self.options.wikipedia_language.value), "en")

    def _infer_topic(self, title: str) -> str | None:
        """Fallback topic for goal presets not found in the annotated pool."""
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
        if re.search(r"\((song|album|single|band|musician|rapper|singer)\)$", lowered):
            return "music"
        for topic, keywords in TOPIC_KEYWORDS.items():
            if any(keyword in lowered for keyword in keywords):
                return topic
        return "miscellaneous"

    def _selected_topics(self) -> set[str]:
        selected: set[str] = set()
        if self.options.include_video_games.value:
            selected.add("video_games")
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
        if self.options.include_politics.value:
            selected.add("politics")
        if self.options.include_famous_people.value:
            selected.add("famous_people")
        if self.options.include_miscellaneous.value:
            selected.add("miscellaneous")
        if self.options.include_animals.value:
            selected.add("animals")
        if self.options.include_biology_medicine.value:
            selected.add("biology_medicine")
        return selected

    def _entry_matches(self, entry: dict, selected_topics: set[str], include_sensitive: bool) -> bool:
        tags = set(entry.get("tags") or ())
        if not (tags & selected_topics):
            return False
        if entry.get("sensitive") and not include_sensitive:
            return False
        return True

    def _search_starting_letters(self) -> set[str]:
        return set(SEARCH_STARTING_LETTERS.get(self.options.search_starting_letters.value, set()))

    def _branch_count(self) -> int:
        return max(0, min(int(self.options.branch_count.value), MAX_BRANCHES))

    def _branch_length(self) -> int:
        return max(1, min(int(self.options.branch_length.value), MAX_BRANCH_LENGTH))

    def _additional_branch_keys(self) -> int:
        if self._branch_count() <= 0:
            return 0
        return max(0, int(self.options.additional_branch_keys.value))

    def _branch_key_count(self) -> int:
        if self._branch_count() <= 0:
            return 0
        return self._branch_count() + self._additional_branch_keys()

    def _branch_location_count(self) -> int:
        return self._branch_count() * self._branch_length()

    def _round_access_needed(self, round_index: int) -> int:
        round_count = self.options.check_count.value
        start_unlocked = min(self.options.start_rounds_unlocked.value, round_count)
        per_unlock = max(1, self.options.rounds_per_unlock.value)
        extra_rounds = max(0, round_index - start_unlocked)
        return (extra_rounds + per_unlock - 1) // per_unlock

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
                "Enable one or more include_* toggles in your YAML."
            )

        lang = self._wikipedia_language()
        if lang not in SUPPORTED_LANGS:
            raise Exception(f"Wikipelago unsupported wikipedia_language: {lang}")
        include_sensitive = bool(self.options.include_sensitive_pages.value)
        article_entries = load_article_pool(lang)
        sensitive_titles = {
            str(entry.get("title") or "").strip()
            for entry in article_entries
            if entry.get("sensitive")
        }
        filtered_entries = [
            entry
            for entry in article_entries
            if self._is_reasonable_title(entry["title"])
            and self._looks_common_knowledge(entry["title"])
            and self._entry_matches(entry, selected_topics, include_sensitive)
        ]
        # Preserve order, drop dupes.
        title_to_tags: dict[str, set[str]] = {}
        filtered_pool: list[str] = []
        for entry in filtered_entries:
            title = entry["title"]
            if title in title_to_tags:
                title_to_tags[title].update(entry.get("tags") or ())
                continue
            title_to_tags[title] = set(entry.get("tags") or ())
            filtered_pool.append(title)

        branch_count = self._branch_count()
        branch_length = self._branch_length()
        if branch_count > 0 and round_count < 2:
            raise Exception(
                "Wikipelago cannot generate branches: check_count must be at least 2 "
                f"(got {round_count}) so a crossroad can be placed after round 1."
            )
        eligible_crossroads = max(0, round_count - 1)
        if branch_count > eligible_crossroads:
            raise Exception(
                "Wikipelago cannot generate this seed: "
                f"branch_count={branch_count} needs {branch_count} main-road crossroads "
                f"(rounds 2..{round_count}), but only {eligible_crossroads} eligible rounds exist. "
                "Lower branch_count or raise check_count."
            )

        # Unique titles: opening start + one target per round + Grand Goal + branch_length per branch.
        extra_branch_titles = branch_count * branch_length
        needed_total = max(3, round_count + 2 + extra_branch_titles)
        max_rounds_for_pool = max(0, len(filtered_pool) - 2 - extra_branch_titles)
        if len(filtered_pool) < needed_total:
            raise Exception(
                "Wikipelago cannot generate this seed: "
                f"check_count={round_count} and branch_count={branch_count} "
                f"(length {branch_length}) need at least {needed_total} unique usable articles "
                f"(including a Grand Goal distinct from round targets), "
                f"but the enabled categories only provide {len(filtered_pool)} "
                f"(supports at most {max_rounds_for_pool} main rounds at this branch setting). "
                "Lower check_count / branch_count / branch_length or enable more article categories."
            )

        self.goal_question = ""
        self.goal_qid = None
        lang = self._wikipedia_language()
        # random_goal_article / goal_article_preset are kept so old YAMLs still
        # parse; generate always picks from this wiki language's goal pool.
        try:
            card = pick_grand_goal_card(
                self.random,
                lang,
                selected_topics,
                filtered_pool,
                include_sensitive=include_sensitive,
                sensitive_titles=sensitive_titles,
            )
        except FileNotFoundError:
            card = None
        if card:
            self.goal_article = card["answer_title"]
            self.goal_question = card["question"]
            self.goal_qid = card.get("qid")
        else:
            self.goal_article = self.random.choice(filtered_pool)
        if self.goal_article not in filtered_pool:
            filtered_pool.append(self.goal_article)

        remaining = [title for title in filtered_pool if title != self.goal_article]
        # Opening start + one target per round + branch_length extra titles per branch.
        needed_from_remaining = round_count + 1 + extra_branch_titles
        if len(remaining) < needed_from_remaining:
            raise Exception(
                "Wikipelago cannot generate this seed: "
                f"check_count={round_count} and branches need {needed_from_remaining + 1} unique usable articles "
                f"(including a Grand Goal distinct from round targets), "
                f"but only {len(remaining) + 1} are available after filtering. "
                "Lower check_count / branch_count or enable more article categories."
            )

        picks = self.random.sample(remaining, round_count + 1)
        first_start = picks[0]
        targets = picks[1:]
        starts = [first_start, *targets[:-1]]
        self.round_pairs = [
            {"start": start, "target": target}
            for start, target in zip(starts, targets)
        ]
        used_titles = {first_start, *targets, self.goal_article}

        self.crossroads = []
        self.branches = []
        if branch_count > 0:
            eligible_rounds = list(range(2, round_count + 1))
            chosen_rounds = sorted(self.random.sample(eligible_rounds, branch_count))
            leftover = [title for title in remaining if title not in used_titles]
            for branch_id, main_round in enumerate(chosen_rounds):
                fork = self.round_pairs[main_round - 1]["target"]
                tagged_pools: dict[str, list[str]] = {tag: [] for tag in selected_topics}
                for title in leftover:
                    for tag in title_to_tags.get(title, ()):
                        if tag in tagged_pools:
                            tagged_pools[tag].append(title)
                viable = [tag for tag, titles in tagged_pools.items() if len(titles) >= branch_length]
                if viable:
                    theme_tag = self.random.choice(viable)
                    theme_titles = tagged_pools[theme_tag]
                else:
                    theme_tag = self.random.choice(sorted(selected_topics))
                    theme_titles = leftover
                if len(theme_titles) < branch_length:
                    raise Exception(
                        "Wikipelago cannot generate this seed: "
                        f"not enough leftover articles for branch {branch_id + 1} "
                        f"(need {branch_length}, have {len(theme_titles)}). "
                        "Lower branch_count / branch_length or enable more article categories."
                    )
                branch_targets = self.random.sample(theme_titles, branch_length)
                branch_starts = [fork, *branch_targets[:-1]]
                pairs = [
                    {"start": start, "target": target}
                    for start, target in zip(branch_starts, branch_targets)
                ]
                used_titles.update(branch_targets)
                leftover = [title for title in leftover if title not in used_titles]
                self.crossroads.append({"main_round": main_round, "branch_id": branch_id})
                self.branches.append({
                    "id": branch_id,
                    "theme_tag": theme_tag,
                    "pairs": pairs,
                })

        # Leftover titles for client-side target rerolls (same filtered category pool).
        self.reroll_pool = [title for title in filtered_pool if title not in used_titles]

        if self._bingo_enabled():
            grid_size = self._bingo_grid_size()
            board_count = self._bingo_board_count()
            wiki_lang = self._wikipedia_language()
            self.bingo_letterpairs_boards = [
                build_letter_pair_bingo_board(self.random, grid_size, wiki_lang)
                for _ in range(board_count)
            ]
        else:
            self.bingo_letterpairs_boards = []

    def create_regions(self) -> None:
        create_regions(self)

    def create_item(self, name: str) -> WikipelagoItem:
        data = item_table[name]
        return self.item_class(name, data.classification, data.code, self.player)

    def create_event(self, name: str) -> WikipelagoItem:
        # Generation-only: no datapackage id, never shuffled or sent as a real item.
        return self.item_class(name, ItemClassification.progression, None, self.player)

    def create_items(self) -> None:
        round_count = self.options.check_count.value
        bingo_count = self._bingo_check_count()
        branch_loc_count = self._branch_location_count()
        free_locations = round_count + bingo_count + branch_loc_count
        required_fragments = min(self.options.required_fragments.value, round_count)
        additional_fragments = max(0, int(self.options.additional_fragments_in_pool.value))
        fragment_pool_count = required_fragments + additional_fragments
        start_unlocked = min(self.options.start_rounds_unlocked.value, round_count)
        per_unlock = max(1, self.options.rounds_per_unlock.value)
        early_open = start_unlocked
        round_access_count = max(0, (round_count - early_open + per_unlock - 1) // per_unlock)
        search_letters_needed = 26 - len(self._search_starting_letters()) if self.options.searchsanity.value else 0
        scroll_upgrades_needed = SCROLL_SPEED_UPGRADES if self.options.scrollsanity.value else 0
        display_unlocks = self._display_unlock_items()
        trap_count = int(self.options.trap_count.value)
        back_unlocks = max(0, int(self.options.back_depth_unlocks.value))
        reroll_unlocks = max(0, int(self.options.target_reroll_unlocks.value))
        bingo_card_unlocks = self._bingo_card_unlocks()
        bingo_stamp_unlocks = self._bingo_stamp_unlocks()
        branch_keys = self._branch_key_count()

        mandatory_items = (
            fragment_pool_count
            + 2  # Wiki Compass + Ctrl+F Lens
            + back_unlocks
            + reroll_unlocks
            + bingo_card_unlocks
            + bingo_stamp_unlocks
            + round_access_count
            + branch_keys
            + search_letters_needed
            + scroll_upgrades_needed
            + len(display_unlocks)
            + trap_count
        )
        if mandatory_items > free_locations:
            raise Exception(
                "Wikipelago item math invalid: required progression items exceed free locations. "
                f"mandatory={mandatory_items}, free_locations={free_locations} "
                f"(rounds={round_count}, bingo={bingo_count}, branch_rounds={branch_loc_count}). "
                "Lower required_fragments, additional_fragments_in_pool, trap_count, unlock counts, "
                "reduce sanity/display unlock load, lower round access pressure "
                "(increase start_rounds_unlocked / rounds_per_unlock), or reduce branch_count / additional_branch_keys."
            )

        pool: list[WikipelagoItem] = []
        for _ in range(fragment_pool_count):
            pool.append(self.create_item("Knowledge Fragment"))
        for _ in range(back_unlocks):
            pool.append(self.create_item("Progressive Back"))
        pool.append(self.create_item("Wiki Compass"))
        pool.append(self.create_item("Ctrl+F Lens"))
        for _ in range(reroll_unlocks):
            pool.append(self.create_item("Progressive Reroll"))
        for _ in range(bingo_card_unlocks):
            pool.append(self.create_item("Progressive Bingo Card"))
        for _ in range(bingo_stamp_unlocks):
            pool.append(self.create_item("Progressive Bingo Stamp"))
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
        for _ in range(branch_keys):
            pool.append(self.create_item("Branch Key"))
        for trap_name in self._trap_item_names(trap_count):
            pool.append(self.create_item(trap_name))
        while len(pool) < free_locations:
            pool.append(self.create_item("Footnote"))

        self.multiworld.itempool.extend(pool)
        # Grand Goal is checkable (real location id) so it must hold a real item code for hosting.
        # Victory stays locked / unshuffled — nothing useful for the multiworld; clearing goal still
        # completes the slot via the bridge CLIENT_GOAL. Remaining checks follow room release settings.
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
        if trap_type == 3:
            return ["Wrong Wiki"] * trap_count
        names: list[str] = []
        for _ in range(trap_count):
            names.append(self.random.choice(["Foggy Links", "Missing Links", "Wrong Wiki"]))
        return names

    def set_rules(self) -> None:
        round_count = self.options.check_count.value
        required_fragments = min(self.options.required_fragments.value, round_count)

        goal_location = self.multiworld.get_location("Grand Goal", self.player)
        set_rule(
            goal_location,
            lambda state, frag_need=required_fragments: state.has("Knowledge Fragment", self.player, frag_need),
        )

        for round_index in range(1, round_count + 1):
            location = self.multiworld.get_location(f"Round {round_index} Complete", self.player)
            needed_round_access = self._round_access_needed(round_index)
            set_rule(
                location,
                lambda state, need=needed_round_access: state.has("Round Access", self.player, need),
            )

        if self._bingo_enabled():
            grid_size = self._bingo_grid_size()
            cards_start = self._bingo_cards_start()
            for board in range(1, self._bingo_board_count() + 1):
                need_cards = max(0, board - cards_start)
                for name in bingo_location_names(grid_size, board):
                    location = self.multiworld.get_location(name, self.player)
                    if need_cards <= 0:
                        continue
                    set_rule(
                        location,
                        lambda state, need=need_cards: state.has(
                            "Progressive Bingo Card", self.player, need
                        ),
                    )

        branch_count = self._branch_count()
        if branch_count > 0:
            # branch_id is assigned in main_round order in generate_early, matching
            # client FIFO: Branch N needs N keys and the Round Access of its crossroad.
            crossroad_round_by_branch = {
                int(cr["branch_id"]) + 1: int(cr["main_round"])
                for cr in (getattr(self, "crossroads", None) or [])
            }
            for branch in range(1, branch_count + 1):
                keys_needed = branch
                main_round = crossroad_round_by_branch.get(branch)
                need_ra = self._round_access_needed(main_round) if main_round else 0
                entrance = self.multiworld.get_entrance(f"To Branch {branch}", self.player)
                set_rule(
                    entrance,
                    lambda state, need_keys=keys_needed, need_ra=need_ra: (
                        state.has("Branch Key", self.player, need_keys)
                        and (need_ra <= 0 or state.has("Round Access", self.player, need_ra))
                    ),
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
        bingo_boards = list(getattr(self, "bingo_letterpairs_boards", []) or [])
        bingo_cards_start = self._bingo_cards_start()
        bingo_card_unlocks = self._bingo_card_unlocks()
        bingo_stamp_unlocks = self._bingo_stamp_unlocks()
        back_depth_start = max(0, int(self.options.back_depth_start.value))
        back_depth_unlocks = max(0, int(self.options.back_depth_unlocks.value))
        target_rerolls_start = max(0, int(self.options.target_rerolls_start.value))
        target_reroll_unlocks = max(0, int(self.options.target_reroll_unlocks.value))
        location_ids: dict[str, Any] = {
            "rounds": round_location_ids,
            "grand_goal": self.location_name_to_id["Grand Goal"],
        }
        if bingo_enabled:
            location_ids["bingo_letterpairs"] = bingo_slot_location_ids_by_board(
                self.location_name_to_id, bingo_grid, len(bingo_boards)
            )
        branch_count = self._branch_count()
        branch_length = self._branch_length()
        if branch_count > 0:
            location_ids["branches"] = [
                [
                    self.location_name_to_id[branch_location_name(branch, round_index)]
                    for round_index in range(1, branch_length + 1)
                ]
                for branch in range(1, branch_count + 1)
            ]

        return {
            "check_count": round_count,
            "required_fragments": required_fragments,
            "start_rounds_unlocked": start_unlocked,
            "rounds_per_unlock": per_unlock,
            "wikipedia_language": self._wikipedia_language(),
            "goal_article": self.goal_article,
            "goal_question": self.goal_question,
            "goal_qid": self.goal_qid,
            "round_pairs": self.round_pairs,
            "crossroads": list(getattr(self, "crossroads", []) or []),
            "branches": list(getattr(self, "branches", []) or []),
            "branch_count": self._branch_count(),
            "branch_length": self._branch_length() if self._branch_count() else 0,
            "additional_branch_keys": self._additional_branch_keys(),
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
            "bingo_letterpairs_boards": bingo_boards if bingo_enabled else [],
            "bingo_cards_start": bingo_cards_start if bingo_enabled else 0,
            "bingo_card_unlocks": bingo_card_unlocks if bingo_enabled else 0,
            "bingo_stamp_unlocks": bingo_stamp_unlocks if bingo_enabled else 0,
            "back_depth_start": back_depth_start,
            "back_depth_unlocks": back_depth_unlocks,
            "target_rerolls_start": target_rerolls_start,
            "target_reroll_unlocks": target_reroll_unlocks,
            "location_ids": location_ids,
            "item_ids": {name: data.code for name, data in item_table.items()},
        }






