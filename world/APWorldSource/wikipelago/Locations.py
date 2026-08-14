from dataclasses import dataclass


@dataclass(frozen=True)
class WikipelagoLocationData:
    code: int


LOCATION_OFFSET = 1_880_000
MAX_ROUNDS = 999
# After Grand Goal: per-board bingo lines (20 rows + 20 cols + 2 diags + full).
BINGO_LP_OFFSET = LOCATION_OFFSET + MAX_ROUNDS + 2
MAX_BINGO_GRID = 20
MAX_BINGO_BOARDS = 40
BINGO_BOARD_STRIDE = 2 * MAX_BINGO_GRID + 3  # 43
# Side-path rounds (after bingo id block ~1_882_720).
BRANCH_LOCATION_OFFSET = 1_890_000
MAX_BRANCHES = 8
MAX_BRANCH_LENGTH = 20


def _bingo_line_index(kind: str, index: int = 0) -> int:
    if kind == "row":
        return index - 1
    if kind == "col":
        return MAX_BINGO_GRID + index - 1
    if kind == "diag":
        return 2 * MAX_BINGO_GRID
    if kind == "anti":
        return 2 * MAX_BINGO_GRID + 1
    if kind == "full":
        return 2 * MAX_BINGO_GRID + 2
    raise ValueError(f"Unknown bingo line kind: {kind}")


def bingo_location_code(board: int, kind: str, index: int = 0) -> int:
    return BINGO_LP_OFFSET + (board - 1) * BINGO_BOARD_STRIDE + _bingo_line_index(kind, index)


def branch_location_name(branch_index: int, round_index: int) -> str:
    """1-based branch and round in the location name."""
    return f"Branch {branch_index} Round {round_index} Complete"


def branch_location_code(branch_index: int, round_index: int) -> int:
    """branch_index and round_index are 1-based."""
    return BRANCH_LOCATION_OFFSET + (branch_index - 1) * MAX_BRANCH_LENGTH + round_index


location_table: dict[str, WikipelagoLocationData] = {
    **{
        f"Round {index} Complete": WikipelagoLocationData(LOCATION_OFFSET + index)
        for index in range(1, MAX_ROUNDS + 1)
    },
    "Grand Goal": WikipelagoLocationData(LOCATION_OFFSET + MAX_ROUNDS + 1),
    **{
        branch_location_name(branch, round_index): WikipelagoLocationData(
            branch_location_code(branch, round_index)
        )
        for branch in range(1, MAX_BRANCHES + 1)
        for round_index in range(1, MAX_BRANCH_LENGTH + 1)
    },
}

for board in range(1, MAX_BINGO_BOARDS + 1):
    for index in range(1, MAX_BINGO_GRID + 1):
        location_table[f"Letter Pair Bingo - Board {board} Row {index}"] = WikipelagoLocationData(
            bingo_location_code(board, "row", index)
        )
        location_table[f"Letter Pair Bingo - Board {board} Column {index}"] = WikipelagoLocationData(
            bingo_location_code(board, "col", index)
        )
    location_table[f"Letter Pair Bingo - Board {board} Diagonal"] = WikipelagoLocationData(
        bingo_location_code(board, "diag")
    )
    location_table[f"Letter Pair Bingo - Board {board} Anti-Diagonal"] = WikipelagoLocationData(
        bingo_location_code(board, "anti")
    )
    location_table[f"Letter Pair Bingo - Board {board} Full Card"] = WikipelagoLocationData(
        bingo_location_code(board, "full")
    )
