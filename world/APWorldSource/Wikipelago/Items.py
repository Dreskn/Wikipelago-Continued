from dataclasses import dataclass

from BaseClasses import ItemClassification


@dataclass(frozen=True)
class WikipelagoItemData:
    code: int
    classification: ItemClassification


ITEM_OFFSET = 1_870_000

item_table: dict[str, WikipelagoItemData] = {
    "Knowledge Fragment": WikipelagoItemData(ITEM_OFFSET + 1, ItemClassification.progression),
    "Back Button": WikipelagoItemData(ITEM_OFFSET + 2, ItemClassification.useful),
    "Wiki Compass": WikipelagoItemData(ITEM_OFFSET + 3, ItemClassification.useful),
    "Ctrl+F Lens": WikipelagoItemData(ITEM_OFFSET + 4, ItemClassification.useful),
    "Footnote": WikipelagoItemData(ITEM_OFFSET + 6, ItemClassification.filler),
    "Round Access": WikipelagoItemData(ITEM_OFFSET + 7, ItemClassification.progression),
    "Progressive Scroll Speed": WikipelagoItemData(ITEM_OFFSET + 8, ItemClassification.useful),
    "Table Lens": WikipelagoItemData(ITEM_OFFSET + 9, ItemClassification.useful),
    "Picture Lens": WikipelagoItemData(ITEM_OFFSET + 10, ItemClassification.useful),
    "Lead Lens": WikipelagoItemData(ITEM_OFFSET + 11, ItemClassification.useful),
    "Infobox Lens": WikipelagoItemData(ITEM_OFFSET + 12, ItemClassification.useful),
    "Contents Lens": WikipelagoItemData(ITEM_OFFSET + 13, ItemClassification.useful),
    "Navbox Lens": WikipelagoItemData(ITEM_OFFSET + 14, ItemClassification.useful),
    "Hatnote Lens": WikipelagoItemData(ITEM_OFFSET + 15, ItemClassification.useful),
    "Reference Lens": WikipelagoItemData(ITEM_OFFSET + 16, ItemClassification.useful),
    "Foggy Links": WikipelagoItemData(ITEM_OFFSET + 46, ItemClassification.trap),
    "Missing Links": WikipelagoItemData(ITEM_OFFSET + 47, ItemClassification.trap),
}

for index, letter in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", start=20):
    item_table[f"Search Letter {letter}"] = WikipelagoItemData(ITEM_OFFSET + index, ItemClassification.useful)

TRAP_ITEM_NAMES: tuple[str, ...] = ("Foggy Links", "Missing Links")
