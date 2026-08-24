from BaseClasses import Region

from .Locations import MAX_BRANCHES, MAX_BRANCH_LENGTH, branch_location_name, location_table
from .letter_pairs import bingo_location_names


def create_regions(world: "WikipelagoWorld") -> None:
    menu = Region("Menu", world.player, world.multiworld)
    game = Region("Wikipelago", world.player, world.multiworld)

    menu.connect(game)

    round_count = world.options.check_count.value
    for index in range(1, round_count + 1):
        name = f"Round {index} Complete"
        data = location_table[name]
        game.add_locations({name: data.code}, world.location_class)

    game.add_locations({"Grand Goal": location_table["Grand Goal"].code}, world.location_class)

    if world.options.toggle_bingo_letterpairs.value:
        grid_size = world.options.bingo_letterpairs_grid.value
        board_count = world._bingo_board_count()
        bingo_locs: dict[str, int] = {}
        for board in range(1, board_count + 1):
            for name in bingo_location_names(grid_size, board):
                bingo_locs[name] = location_table[name].code
        game.add_locations(bingo_locs, world.location_class)

    branch_count = max(0, min(int(world.options.branch_count.value), MAX_BRANCHES))
    branch_length = max(1, min(int(world.options.branch_length.value), MAX_BRANCH_LENGTH))
    extra_regions: list[Region] = []
    if branch_count > 0:
        for branch in range(1, branch_count + 1):
            branch_region = Region(f"Branch {branch}", world.player, world.multiworld)
            branch_locs: dict[str, int] = {}
            for round_index in range(1, branch_length + 1):
                name = branch_location_name(branch, round_index)
                branch_locs[name] = location_table[name].code
            branch_region.add_locations(branch_locs, world.location_class)
            game.connect(branch_region, f"To Branch {branch}")
            extra_regions.append(branch_region)

    world.multiworld.regions.extend([menu, game, *extra_regions])
