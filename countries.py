# countries.py

COUNTRY_PAGES = {
    1: {
        "🇺🇸": "United States",
        "🇨🇦": "Canada",
        "🇲🇽": "Mexico",
        "🇧🇷": "Brazil",
        "🇦🇷": "Argentina",
        "🇬🇧": "United Kingdom",
        "🇫🇷": "France",
        "🇩🇪": "Germany",
        "🇮🇹": "Italy",
        "🇪🇸": "Spain",
        "🇳🇱": "Netherlands",
        "🇧🇪": "Belgium",
        "🇨🇭": "Switzerland",
        "🇦🇹": "Austria",
        "🇸🇪": "Sweden",
        "🇳🇴": "Norway",
        "🇩🇰": "Denmark",
        "🇫🇮": "Finland",
        "🇵🇱": "Poland",
        "🇨🇿": "Czech Republic",
    },

    2: {
        "🇷🇺": "Russia",
        "🇺🇦": "Ukraine",
        "🇹🇷": "Turkey",
        "🇮🇳": "India",
        "🇵🇰": "Pakistan",
        "🇧🇩": "Bangladesh",
        "🇳🇵": "Nepal",
        "🇨🇳": "China",
        "🇯🇵": "Japan",
        "🇰🇷": "South Korea",
        "🇵🇭": "Philippines",
        "🇻🇳": "Vietnam",
        "🇹🇭": "Thailand",
        "🇮🇩": "Indonesia",
        "🇲🇾": "Malaysia",
        "🇸🇬": "Singapore",
        "🇦🇺": "Australia",
        "🇳🇿": "New Zealand",
        "🇿🇦": "South Africa",
        "🇦🇪": "United Arab Emirates",
    }
}

# Every country role in one list
ALL_COUNTRIES = {}

for page in COUNTRY_PAGES.values():
    ALL_COUNTRIES.update(page)
