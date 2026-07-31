from __future__ import annotations


def caliber_key(value: str) -> str:
    """Return a punctuation-insensitive key for EFT/API caliber identifiers."""
    return "".join(character for character in value.casefold() if character.isalnum())


_DISPLAY_NAMES = {
    "9x18pm": "9x18 PM",
    "9x19para": "9x19",
    "9x21": "9x21",
    "9x33r": ".357 Magnum",
    "1143x23acp": ".45 ACP",
    "46x30": "4.6x30",
    "57x28": "5.7x28",
    "545x39": "5.45x39",
    "556x45": "5.56x45",
    "762x25tt": "7.62x25 TT",
    "762x35": ".300 BLK",
    "762x39": "7.62x39",
    "762x51": "7.62x51",
    "762x54r": "7.62x54R",
    "127x55": "12.7x55",
    "127x108": "12.7x108",
    "366tkm": ".366 TKM",
    "12g": "12 gauge",
    "20g": "20 gauge",
    "23x75": "23x75",
    "26x75": "26x75",
    "30x29": "30x29",
    "40x46": "40x46",
    "40ru": "40mm RU",
}


def display_caliber(value: str) -> str:
    cleaned = (
        value.removeprefix("Caliber").replace("NATO", "").replace("mm", "").strip()
    )
    return _DISPLAY_NAMES.get(caliber_key(cleaned), cleaned)


def caliber_matches(value: str, selected: str) -> bool:
    if not selected:
        return True
    value_key = caliber_key(value)
    selected_key = caliber_key(selected)
    if selected_key in {"1270", "12g", "12gauge"}:
        return value_key in {"1270", "1276", "12g", "12gauge"}
    return value_key == selected_key
