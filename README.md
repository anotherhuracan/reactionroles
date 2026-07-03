# Country Roles Discord Bot

A production-ready Discord bot built with `discord.py` 2.x that lets members
self-assign a single country role by reacting to flag emojis on
reaction-role panels.

## Features

- **`$rrsetup`** — Creates every missing country role in the server (skips ones that already exist).
- **`$rr 1`** — Creates the page 1 reaction-role panel (20 countries). If it already exists, edits it in place. If it was deleted, sends a new one and updates the saved message ID.
- **`$rr 2`** — Same as above, for page 2 (25 countries).
- **`$rr refresh`** — Deletes existing panels and sends fresh ones, re-adding all reactions. Member country roles are preserved.
- **`$rr sync`** — Repairs panels: adds any missing reactions and updates the embed if it's out of date, without creating duplicate messages.
- **`$rr delete`** — Deletes only the panel messages and clears them from `data.json`. Country roles and member role assignments are **never** touched.

### Role logic

- Each member may only hold **one** country role at a time.
- Reacting with a new country flag removes all other country roles from the member, assigns the new one, and removes the member's reaction from their previous country flag (across both pages) so the panel always reflects their current role.
- Removing a reaction removes the corresponding role.
- Bot reactions are always ignored.

### Persistence

All panel message IDs and channel IDs are stored in `data.json`. On restart
(e.g. after a Railway redeploy), the bot reloads this file and verifies each
panel is still reachable, so everything keeps working without manual
intervention.

## Project Structure
