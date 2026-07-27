from BaseClasses import Region

from .Locations import location_table
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
        bingo_locs = {
            name: location_table[name].code
            for name in bingo_location_names(grid_size)
        }
        game.add_locations(bingo_locs, world.location_class)

    world.multiworld.regions.extend([menu, game])
