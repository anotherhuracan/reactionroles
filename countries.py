"""
Country and flag emoji definitions for the Country Roles bot.

Countries are split into two pages, each containing roughly 20 entries.
Each entry maps a country name to its corresponding Unicode flag emoji.
"""

from typing import Dict, List

# Page 1: Americas + Europe (part 1)
PAGE_1: Dict[str, str] = {
    "United States": "🇺🇸",
    "Canada": "🇨🇦",
    "Mexico": "🇲🇽",
    "Brazil": "🇧🇷",
    "Argentina": "🇦🇷",
    "United Kingdom": "🇬🇧",
    "Ireland": "🇮🇪",
    "France": "🇫🇷",
    "Germany": "🇩🇪",
    "Italy": "🇮🇹",
    "Spain": "🇪🇸",
    "Netherlands": "🇳🇱",
    "Belgium": "🇧🇪",
    "Switzerland": "🇨🇭",
    "Austria": "🇦🇹",
    "Sweden": "🇸🇪",
    "Norway": "🇳🇴",
    "Denmark": "🇩🇰",
    "Finland": "🇫🇮",
    "Poland": "🇵🇱",
}

# Page 2: Europe (part 2) + Asia + Oceania + Africa + Middle East
PAGE_2: Dict[str, str] = {
    "Czech Republic": "🇨🇿",
    "Portugal": "🇵🇹",
    "Russia": "🇷🇺",
    "Ukraine": "🇺🇦",
    "Turkey": "🇹🇷",
    "India": "🇮🇳",
    "Pakistan": "🇵🇰",
    "Bangladesh": "🇧🇩",
    "Nepal": "🇳🇵",
    "China": "🇨🇳",
    "Japan": "🇯🇵",
    "South Korea": "🇰🇷",
    "Philippines": "🇵🇭",
    "Vietnam": "🇻🇳",
    "Thailand": "🇹🇭",
    "Indonesia": "🇮🇩",
    "Malaysia": "🇲🇾",
    "Singapore": "🇸🇬",
    "Australia": "🇦🇺",
    "New Zealand": "🇳🇿",
    "South Africa": "🇿🇦",
    "Egypt": "🇪🇬",
    "Nigeria": "🇳🇬",
    "Saudi Arabia": "🇸🇦",
    "United Arab Emirates": "🇦🇪",
}

# All pages combined, indexed by page number (1-based) for easy lookup.
PAGES: Dict[int, Dict[str, str]] = {
    1: PAGE_1,
    2: PAGE_2,
}

# Flattened mapping of emoji -> country name, built once at import time.
EMOJI_TO_COUNTRY: Dict[str, str] = {}
for _page in PAGES.values():
    for _country, _emoji in _page.items():
        EMOJI_TO_COUNTRY[_emoji] = _country

# Flattened mapping of country name -> emoji.
COUNTRY_TO_EMOJI: Dict[str, str] = {
    country: emoji for emoji, country in EMOJI_TO_COUNTRY.items()
}

# All country names across all pages (used for role creation / validation).
ALL_COUNTRIES: List[str] = list(EMOJI_TO_COUNTRY.values())


def get_page(page_number: int) -> Dict[str, str]:
    """Return the country->emoji mapping for a given page number.

    Raises:
        KeyError: if the page number does not exist.
    """
    return PAGES[page_number]


def is_country_emoji(emoji: str) -> bool:
    """Check whether the given emoji corresponds to a tracked country."""
    return emoji in EMOJI_TO_COUNTRY


def country_from_emoji(emoji: str) -> str | None:
    """Return the country name associated with an emoji, or None."""
    return EMOJI_TO_COUNTRY.get(emoji)


def emoji_from_country(country: str) -> str | None:
    """Return the emoji associated with a country name, or None."""
    return COUNTRY_TO_EMOJI.get(country)
