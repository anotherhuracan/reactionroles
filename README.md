# Country Roles Discord Bot

A production-ready Discord bot built with `discord.py` 2.x that lets members
self-assign a single country role by reacting to flag emojis on
reaction-role panels.

## Features

- **`$rrsetup`** — Creates every missing country role in the server (skips ones that already exist).
- **`$rr 1`** — Creates a **new** page 1 reaction-role panel (20 countries). This can be run an unlimited number of times — every call posts a fresh, independently tracked panel message.
- **`$rr 2`** — Same as above, for page 2 (25 countries). Also unlimited.
- **`$rr refresh`** — Deletes **every** existing panel (all pages, all copies) and sends exactly one fresh panel per page. Member country roles are preserved.
- **`$rr sync`** — Repairs every currently tracked panel: adds any missing reactions and updates the embed if it's out of date, without creating duplicate messages.
- **`$rr delete`** — Deletes **every** tracked panel message across every page and clears `data.json` entirely. Country roles and member role assignments are **never** touched.

### Unlimited panels

Unlike a single-panel-per-page design, this bot tracks panels as a **list**
per page in `data.json`. That means:
- You can run `$rr 1` or `$rr 2` as many times as you want (e.g. to post the
  panel in multiple channels, or repost it further down a channel).
- Every panel that has ever been created stays fully functional — reacting
  on *any* of them assigns/removes roles correctly.
- `$rr sync` walks through and repairs **all** of them.
- `$rr delete` removes **all** of them at once, wiping the tracked list
  clean so you can start fresh with `$rr 1` / `$rr 2`.

### Command Access

Only members holding **at least one** of the following role IDs may use
`$rrsetup` or any `$rr` subcommand:
