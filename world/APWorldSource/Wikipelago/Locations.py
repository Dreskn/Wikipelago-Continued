from dataclasses import dataclass


@dataclass(frozen=True)
class WikipelagoLocationData:
    code: int


LOCATION_OFFSET = 1_880_000
MAX_ROUNDS = 5000
# After Grand Goal: 26 rows + 26 cols + diagonal + anti-diagonal + full card.
BINGO_LP_OFFSET = LOCATION_OFFSET + MAX_ROUNDS + 2
MAX_BINGO_GRID = 26

location_table: dict[str, WikipelagoLocationData] = {
    **{
        f"Round {index} Complete": WikipelagoLocationData(LOCATION_OFFSET + index)
        for index in range(1, MAX_ROUNDS + 1)
    },
    "Grand Goal": WikipelagoLocationData(LOCATION_OFFSET + MAX_ROUNDS + 1),
    **{
        f"Letter Pair Bingo - Row {index}": WikipelagoLocationData(BINGO_LP_OFFSET + index - 1)
        for index in range(1, MAX_BINGO_GRID + 1)
    },
    **{
        f"Letter Pair Bingo - Column {index}": WikipelagoLocationData(
            BINGO_LP_OFFSET + MAX_BINGO_GRID + index - 1
        )
        for index in range(1, MAX_BINGO_GRID + 1)
    },
    "Letter Pair Bingo - Diagonal": WikipelagoLocationData(BINGO_LP_OFFSET + 2 * MAX_BINGO_GRID),
    "Letter Pair Bingo - Anti-Diagonal": WikipelagoLocationData(
        BINGO_LP_OFFSET + 2 * MAX_BINGO_GRID + 1
    ),
    "Letter Pair Bingo - Full Card": WikipelagoLocationData(BINGO_LP_OFFSET + 2 * MAX_BINGO_GRID + 2),
}
