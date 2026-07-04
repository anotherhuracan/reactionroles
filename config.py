"""
Configuration module for the Country Roles Discord bot.

Loads sensitive/environment-specific values from environment variables
and defines global constants used across the bot.
"""

import os
from typing import List

# --- Bot Configuration ---

# Discord bot token, read from environment variable (set this on Railway).
DISCORD_TOKEN: str = os.environ.get("DISCORD_TOKEN", "")

# Command prefix for the bot.
COMMAND_PREFIX: str = "$"

# Path to the JSON file used for persistence.
DATA_FILE: str = "data.json"

# Embed color (Discord blurple-ish / can be customized).
EMBED_COLOR: int = 0x3498DB

# Embed footer text.
EMBED_FOOTER: str = "Removing your reaction removes your role."

# Embed title.
EMBED_TITLE: str = "🌍 Country Roles"

# Embed description.
EMBED_DESCRIPTION: str = (
    "React below to choose your country.\n"
    "You may only have **ONE** country role.\n\n"
)

# --- Permission Configuration ---

# Only members holding at least one of these role IDs may use the
# management commands ($rrsetup, $rr 1/2/3/refresh/sync/delete, $rrstats,
# $rrcount).
ALLOWED_ROLE_IDS: List[int] = [
    1522583335740637294,
    1502474199179071598,
    1502826874022269008,
    1502720083544510624,
]
