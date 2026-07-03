# config.py

import os

# ==============================
# Discord
# ==============================

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError(
        "No DISCORD_TOKEN environment variable found.\n"
        "Set it in Railway Variables before starting the bot."
    )

PREFIX = "$"

# ==============================
# Bot Settings
# ==============================

EMBED_COLOR = 0x5865F2  # Discord blurple

EMBED_TITLE = "🌍 Country Roles"

EMBED_DESCRIPTION = (
    "React with the flag below to receive your country role.\n\n"
    "• You can only have **one** country role at a time.\n"
    "• Removing your reaction removes your role."
)

# File used to save reaction-role messages
DATA_FILE = "data.json"

# Whether to automatically create missing roles
AUTO_CREATE_ROLES = True

# Log basic events to the console
LOG_EVENTS = True
