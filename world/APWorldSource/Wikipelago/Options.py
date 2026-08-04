from dataclasses import dataclass

from Options import Choice, PerGameCommonOptions, Range, Toggle


class CheckCount(Range):
    """Number of Start→Target rounds. Generation still fails if the enabled article pool is too small."""
    display_name = "Round Count"
    range_start = 10
    range_end = 999
    default = 40


class RequiredFragments(Range):
    """Knowledge Fragments needed to reveal and clear the Grand Goal."""
    display_name = "Required Fragments"
    range_start = 1
    range_end = 200
    default = 7


class AdditionalFragmentsInPool(Range):
    """Extra Knowledge Fragments placed in the item pool beyond required_fragments (goal still needs only the required count)."""
    display_name = "Additional Fragments In Pool"
    range_start = 0
    range_end = 200
    default = 2


class StartRoundsUnlocked(Range):
    display_name = "Start Rounds Unlocked"
    range_start = 1
    range_end = 999
    default = 10


class RoundsPerUnlock(Range):
    display_name = "Rounds Per Round Access"
    range_start = 1
    range_end = 999
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


class WikipediaLanguage(Choice):
    """Wikipedia language edition for article titles and page fetches (one per slot)."""
    display_name = "Wikipedia Language"
    option_en = 0
    option_fr = 1
    option_de = 2
    option_es = 3
    option_it = 4
    option_pt = 5
    option_nl = 6
    option_sv = 7
    option_pl = 8
    default = 0


class IncludeVideoGames(Toggle):
    display_name = "Include Video Games"
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


class IncludePolitics(Toggle):
    display_name = "Include Politics"
    default = 1


class IncludeFamousPeople(Toggle):
    display_name = "Include Famous People"
    default = 1


class IncludeMiscellaneous(Toggle):
    """Catch-all pages that matched no other category (or have no Wikidata entity)."""
    display_name = "Include Miscellaneous"
    default = 0


class IncludeAnimals(Toggle):
    display_name = "Include Animals"
    default = 1


class IncludeBiologyMedicine(Toggle):
    display_name = "Include Biology and Medicine"
    default = 1


class IncludeSensitivePages(Toggle):
    """
    When off (default), pages flagged sensitive (porn, terrorism, violent/sexual crime,
    illicit drugs) are excluded even if they match an enabled category.
    When on, those pages may appear if they also match an enabled category.
    """
    display_name = "Include Sensitive Pages"
    default = 0


class GoalArticlePreset(Choice):
    """Deprecated: prefer random_goal_article. Kept for existing YAMLs."""
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
    range_end = 99
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


class ToggleBingoLetterpairs(Toggle):
    """When enabled, add letter-pair bingo board(s) with row/column/diagonal/full-card checks."""
    display_name = "Letter Pair Bingo"
    default = 1


class BingoLetterpairsGrid(Range):
    """Bingo grid size N (N×N cells). N=26 is the full sorted A–Z×A–Z board; smaller sizes are weighted samples."""
    display_name = "Letter Pair Bingo Grid Size"
    range_start = 3
    range_end = 26
    default = 5


class BingoCardsStart(Range):
    """How many letter-pair bingo boards are unlocked from the start (0 = all boards locked behind Progressive Bingo Card)."""
    display_name = "Bingo Cards Start"
    range_start = 0
    range_end = 20
    default = 1


class BingoCardUnlocks(Range):
    """Number of Progressive Bingo Card items in the pool (extra boards beyond Bingo Cards Start)."""
    display_name = "Bingo Card Unlocks"
    range_start = 0
    range_end = 20
    default = 2


class BingoStampUnlocks(Range):
    """Number of Progressive Bingo Stamp items in the pool (each stamps one empty cell on one unlocked board, once per game)."""
    display_name = "Bingo Stamp Unlocks"
    range_start = 0
    range_end = 20
    default = 2


class BackDepthStart(Range):
    """Starting Back depth per round (0 = Back locked until Progressive Back items are found)."""
    display_name = "Back Depth Start"
    range_start = 0
    range_end = 5
    default = 0


class BackDepthUnlocks(Range):
    """Number of Progressive Back items in the pool (each raises per-round Back depth by 1)."""
    display_name = "Back Depth Unlocks"
    range_start = 0
    range_end = 5
    default = 3


class TargetRerollsStart(Range):
    """Starting target rerolls available each round."""
    display_name = "Target Rerolls Start"
    range_start = 0
    range_end = 5
    default = 1


class TargetRerollUnlocks(Range):
    """Number of Progressive Reroll items in the pool (each raises per-round reroll max by 1)."""
    display_name = "Target Reroll Unlocks"
    range_start = 0
    range_end = 5
    default = 2


@dataclass
class WikipelagoOptions(PerGameCommonOptions):
    check_count: CheckCount
    required_fragments: RequiredFragments
    additional_fragments_in_pool: AdditionalFragmentsInPool
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
    wikipedia_language: WikipediaLanguage
    include_video_games: IncludeVideoGames
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
    include_politics: IncludePolitics
    include_famous_people: IncludeFamousPeople
    include_miscellaneous: IncludeMiscellaneous
    include_animals: IncludeAnimals
    include_biology_medicine: IncludeBiologyMedicine
    include_sensitive_pages: IncludeSensitivePages
    goal_article_preset: GoalArticlePreset
    deaths: Deaths
    death_link: DeathLink
    link_bombs: LinkBombs
    link_bomb_density: LinkBombDensity
    trap_count: TrapCount
    trap_type: TrapType
    trap_link: TrapLink
    toggle_bingo_letterpairs: ToggleBingoLetterpairs
    bingo_letterpairs_grid: BingoLetterpairsGrid
    bingo_cards_start: BingoCardsStart
    bingo_card_unlocks: BingoCardUnlocks
    bingo_stamp_unlocks: BingoStampUnlocks
    back_depth_start: BackDepthStart
    back_depth_unlocks: BackDepthUnlocks
    target_rerolls_start: TargetRerollsStart
    target_reroll_unlocks: TargetRerollUnlocks
