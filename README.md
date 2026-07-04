# Country Roles Discord Bot

A production-ready Discord bot built with `discord.py` 2.x that lets members
self-assign a single country role by reacting to flag emojis on
reaction-role panels.

## Features

- **`$help`** — Full command reference embed, available to everyone.
- **`$rrsetup`** — Creates every missing country role in the server (skips ones that already exist).
- **`$rr 1` / `$rr 2` / `$rr 3`** — Creates a **new** reaction-role panel for that page. Can be run an unlimited number of times — every call posts a fresh, independently tracked panel message.
- **`$rr refresh`** — Deletes **every** existing panel (all pages, all copies) and sends exactly one fresh panel per page. Member country roles are preserved.
- **`$rr sync`** — Repairs every currently tracked panel: adds any missing reactions and updates the embed if it's out of date, without creating duplicate messages.
- **`$rr delete`** — Deletes **every** tracked panel message across every page and clears `data.json` entirely. Country roles and member role assignments are **never** touched.
- **`$rrcount`** — Shows how many panels currently exist per page.
- **`$rrstats`** — Shows how many members currently hold each country role, sorted by popularity.

### Countries (70 total across 3 pages)

**Page 1** — United States, Canada, Mexico, Brazil, Argentina, United Kingdom, Ireland, France, Germany, Italy, Spain, Netherlands, Belgium, Switzerland, Austria, Sweden, Norway, Denmark, Finland, Poland.

**Page 2** — Czech Republic, Portugal, Russia, Ukraine, Turkey, India, Pakistan, Bangladesh, Nepal, China, Japan, South Korea, Philippines, Vietnam, Thailand, Indonesia, Malaysia, Singapore, Australia, New Zealand, South Africa, Egypt, Nigeria, Saudi Arabia, United Arab Emirates.

**Page 3 (new)** — Serbia, Israel, Belarus, Croatia, Greece, Romania, Bulgaria, Hungary, Slovakia, Slovenia, Iceland, Latvia, Lithuania, Estonia, Georgia, Armenia, Azerbaijan, Iraq, Iran, Jordan, Lebanon, Kenya, Morocco, Colombia, Chile.

### Unlimited panels

Panels are tracked as a **list** per page in `data.json`, so:
- You can run `$rr 1`, `$rr 2`, or `$rr 3` as many times as you want (e.g. to post in multiple channels).
- Every panel ever created stays fully functional — reacting on *any* of them assigns/removes roles correctly.
- `$rr sync` repairs **all** of them at once.
- `$rr delete` removes **all** of them at once, wiping the tracked list clean.

### Command Access

Only members holding **at least one** of the following role IDs may use
`$rrsetup`, any `$rr` subcommand, `$rrcount`, or `$rrstats`:
