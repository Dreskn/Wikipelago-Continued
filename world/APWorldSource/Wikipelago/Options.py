from dataclasses import dataclass

from Options import Choice, PerGameCommonOptions, Range, Toggle


class CheckCount(Range):
    """Number of Start→Target rounds. Hard-capped by current article-pool size."""
    display_name = "Round Count"
    range_start = 10
    # Generation needs ~2 unique titles per round (strict no-repeat).
    # With all categories enabled the usable pool supports at most this many rounds.
    range_end = 793
    default = 25


class RequiredFragments(Range):
    display_name = "Required Fragments"
    range_start = 1
    range_end = 793
    default = 5


class StartRoundsUnlocked(Range):
    display_name = "Start Rounds Unlocked"
    range_start = 1
    range_end = 100
    default = 10


class RoundsPerUnlock(Range):
    display_name = "Rounds Per Round Access"
    range_start = 1
    range_end = 25
    default = 5


class RandomGoalArticle(Toggle):
    """When enabled, the Grand Goal article is chosen randomly from enabled categories."""
    display_name = "Random Goal Article"
    default = 1


class Searchsanity(Toggle):
    display_name = "Searchsanity"
    default = 0


class Scrollsanity(Toggle):
    display_name = "Scrollsanity"
    default = 0


class RandomizeTables(Toggle):
    """When enabled, Wikipedia tables stay hidden until Table Lens is received."""
    display_name = "Randomize Tables"
    default = 0


class RandomizePictures(Toggle):
    """When enabled, Wikipedia images/galleries stay hidden until Picture Lens is received."""
    display_name = "Randomize Pictures"
    default = 0


class RandomizeIncipit(Toggle):
    """When enabled, the lead/intro section stays hidden until Lead Lens is received."""
    display_name = "Randomize Incipit"
    default = 0


class RandomizeInfoboxes(Toggle):
    """When enabled, infoboxes stay hidden until Infobox Lens is received."""
    display_name = "Randomize Infoboxes"
    default = 0


class RandomizeToc(Toggle):
    """When enabled, the table of contents stays hidden until Contents Lens is received."""
    display_name = "Randomize Table of Contents"
    default = 0


class RandomizeNavboxes(Toggle):
    """When enabled, navboxes and See also hubs stay hidden until Navbox Lens is received."""
    display_name = "Randomize Navboxes"
    default = 0


class RandomizeHatnotes(Toggle):
    """When enabled, hatnotes stay hidden until Hatnote Lens is received."""
    display_name = "Randomize Hatnotes"
    default = 0


class RandomizeReferences(Toggle):
    """When enabled, footnotes/references stay hidden until Reference Lens is received."""
    display_name = "Randomize References"
    default = 0


class SearchStartingLetters(Choice):
    display_name = "Search Starting Letters"
    option_none = 0
    option_all_vowels = 1
    option_etaoi = 2
    option_raise = 3
    default = 0


class IncludeVideoGames(Toggle):
    display_name = "Include Video Games"
    default = 1


class IncludeBoardGames(Toggle):
    display_name = "Include Board Games"
    default = 1


class IncludeMovies(Toggle):
    display_name = "Include Movies"
    default = 1


class IncludeTVShows(Toggle):
    display_name = "Include TV Shows"
    default = 1


class IncludeAnimeManga(Toggle):
    display_name = "Include Anime and Manga"
    default = 1


class IncludeSports(Toggle):
    display_name = "Include Sports"
    default = 1


class IncludeScienceSpace(Toggle):
    display_name = "Include Science and Space"
    default = 1


class IncludeTechnology(Toggle):
    display_name = "Include Technology and Internet"
    default = 1


class IncludeHistory(Toggle):
    display_name = "Include History"
    default = 1


class IncludeGeography(Toggle):
    display_name = "Include Geography and Landmarks"
    default = 1


class IncludeFoodCuisine(Toggle):
    display_name = "Include Food and Cuisine"
    default = 1


class IncludeArtLiterature(Toggle):
    display_name = "Include Art and Literature"
    default = 1


class IncludeMythologyFolklore(Toggle):
    display_name = "Include Mythology and Folklore"
    default = 1


class IncludeMusic(Toggle):
    display_name = "Include Music"
    default = 1


class GoalArticlePreset(Choice):
    display_name = "Goal Article Preset (used when random goal is off)"
    option_minecraft = 0
    option_the_legend_of_zelda = 1
    option_dark_souls = 2
    option_elden_ring = 3
    option_super_mario_bros = 4
    option_pokemon_red_and_blue = 5
    option_chess = 6
    option_catan = 7
    option_the_dark_knight = 8
    option_star_wars_film = 9
    option_lord_of_the_rings_fellowship = 10
    option_the_matrix = 11
    option_avatar_the_last_airbender = 12
    option_breaking_bad = 13
    option_stranger_things = 14
    option_game_of_thrones = 15
    option_the_simpsons = 16
    option_spongebob_squarepants = 17
    option_super_smash_bros_ultimate = 18
    option_halo_combat_evolved = 19
    default = 2


class Deaths(Toggle):
    """When enabled, revisiting a page already visited this round causes a death (random Wikipedia page)."""
    display_name = "Deaths"
    default = 0


class DeathLink(Toggle):
    """When enabled, join Archipelago DeathLink (send and receive)."""
    display_name = "Death Link"
    default = 0


class LinkBombs(Toggle):
    """When enabled (and Deaths is on), random links on each page may be bombs that cause a death."""
    display_name = "Link Bombs"
    default = 0


class LinkBombDensity(Choice):
    """How many bomb links to try to place per page (capped at half the eligible links). Requires Deaths and Link Bombs."""
    display_name = "Link Bomb Density"
    option_few = 0
    option_more = 1
    option_insane = 2
    default = 0


class TrapCount(Range):
    """Number of trap items (Foggy Links / Missing Links) added to the pool before Footnote filler."""
    display_name = "Trap Count"
    range_start = 0
    range_end = 793
    default = 0


class TrapType(Choice):
    """Which trap items to generate and accept from Trap Link."""
    display_name = "Trap Type"
    option_both = 0
    option_only_foggy_links = 1
    option_only_missing_links = 2
    default = 0


class TrapLink(Toggle):
    """When enabled, share traps with other Trap Link players (send and receive). Independent of Trap Count."""
    display_name = "Trap Link"
    default = 0


@dataclass
class WikipelagoOptions(PerGameCommonOptions):
    check_count: CheckCount
    required_fragments: RequiredFragments
    start_rounds_unlocked: StartRoundsUnlocked
    rounds_per_unlock: RoundsPerUnlock
    random_goal_article: RandomGoalArticle
    searchsanity: Searchsanity
    scrollsanity: Scrollsanity
    randomize_tables: RandomizeTables
    randomize_pictures: RandomizePictures
    randomize_incipit: RandomizeIncipit
    randomize_infoboxes: RandomizeInfoboxes
    randomize_toc: RandomizeToc
    randomize_navboxes: RandomizeNavboxes
    randomize_hatnotes: RandomizeHatnotes
    randomize_references: RandomizeReferences
    search_starting_letters: SearchStartingLetters
    include_video_games: IncludeVideoGames
    include_board_games: IncludeBoardGames
    include_movies: IncludeMovies
    include_tv_shows: IncludeTVShows
    include_anime_manga: IncludeAnimeManga
    include_sports: IncludeSports
    include_science_space: IncludeScienceSpace
    include_technology: IncludeTechnology
    include_history: IncludeHistory
    include_geography: IncludeGeography
    include_food_cuisine: IncludeFoodCuisine
    include_art_literature: IncludeArtLiterature
    include_mythology_folklore: IncludeMythologyFolklore
    include_music: IncludeMusic
    goal_article_preset: GoalArticlePreset
    deaths: Deaths
    death_link: DeathLink
    link_bombs: LinkBombs
    link_bomb_density: LinkBombDensity
    trap_count: TrapCount
    trap_type: TrapType
    trap_link: TrapLink
