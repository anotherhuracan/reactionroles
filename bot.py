"""
Country Roles Discord Bot
==========================

A production-ready Discord bot that lets members self-assign a single
country role via reaction-role panels.

Features:
    - $rrsetup        : Create all missing country roles.
    - $rr 1 / 2 / 3    : Create a NEW reaction-role panel for that page.
                         Panels can be created an unlimited number of times;
                         each invocation posts a brand-new message and tracks
                         it independently.
    - $rr refresh     : Delete ALL existing panels (every page) and send one
                         fresh panel per page. Member country roles are kept.
    - $rr sync        : Repair every tracked panel (missing reactions /
                         outdated embed) without creating duplicates.
    - $rr delete      : Delete ALL reaction-role panel messages across every
                         page and clear them from data.json.
    - $rrstats        : Show how many members hold each country role.
    - $rrcount        : Show how many panels currently exist per page.
    - $help           : Show a full command reference embed.

Persistence:
    Message IDs and channel IDs for every panel are stored in data.json
    so the bot can recover its state after a restart (e.g. on Railway).

Author: Generated for production Railway deployment.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional

import discord
from discord.ext import commands

import config
import countries

# --------------------------------------------------------------------------
# Logging configuration
# --------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("country-roles")


# --------------------------------------------------------------------------
# Data persistence helpers
# --------------------------------------------------------------------------

class DataStore:
    """Handles reading/writing the JSON persistence file.

    Structure of data.json:
    {
        "panels": {
            "1": [
                {"channel_id": int, "message_id": int},
                {"channel_id": int, "message_id": int}
            ],
            "2": [...],
            "3": [...]
        }
    }

    Each page maps to a LIST of panels, allowing an unlimited number of
    panel messages to be created and tracked for that page.
    """

    def __init__(self, path: str) -> None:
        self.path = path
        self._lock = asyncio.Lock()
        self.data: Dict[str, Any] = self._default_data()

    @staticmethod
    def _default_data() -> Dict[str, Any]:
        """Build a default data structure with an empty list per page."""
        return {"panels": {str(p): [] for p in countries.PAGES.keys()}}

    def load(self) -> None:
        """Load data from disk, creating a default file if missing/corrupt."""
        if not os.path.exists(self.path):
            logger.info("No data file found at %s, creating a new one.", self.path)
            self.data = self._default_data()
            self._save_sync()
            return

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if not isinstance(loaded, dict) or "panels" not in loaded:
                raise ValueError("Malformed data.json structure")

            panels = loaded.get("panels", {})
            # Normalize legacy format (single dict per page) into list format.
            for page_key, value in list(panels.items()):
                if isinstance(value, dict):
                    panels[page_key] = [value]
                elif isinstance(value, list):
                    panels[page_key] = value
                else:
                    panels[page_key] = []

            # Ensure every known page has at least an empty list entry.
            for page_number in countries.PAGES.keys():
                panels.setdefault(str(page_number), [])

            loaded["panels"] = panels
            self.data = loaded
            logger.info("Loaded data.json successfully.")
        except (json.JSONDecodeError, ValueError, OSError) as exc:
            logger.error("Failed to load data.json (%s). Starting fresh.", exc)
            self.data = self._default_data()
            self._save_sync()

    def _save_sync(self) -> None:
        """Synchronous save used only during initial load/creation."""
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4)
        except OSError as exc:
            logger.error("Failed to write data.json: %s", exc)

    async def save(self) -> None:
        """Persist current data to disk safely (async-locked)."""
        async with self._lock:
            try:
                with open(self.path, "w", encoding="utf-8") as f:
                    json.dump(self.data, f, indent=4)
            except OSError as exc:
                logger.error("Failed to write data.json: %s", exc)

    def get_panels(self, page: int) -> List[Dict[str, int]]:
        """Return the list of stored panels for a page."""
        return self.data.get("panels", {}).get(str(page), [])

    async def add_panel(self, page: int, channel_id: int, message_id: int) -> None:
        """Append a new panel entry for a page and persist to disk."""
        self.data.setdefault("panels", {}).setdefault(str(page), []).append(
            {"channel_id": channel_id, "message_id": message_id}
        )
        await self.save()

    async def remove_panel(self, page: int, message_id: int) -> None:
        """Remove a single panel entry (by message_id) and persist to disk."""
        panels = self.data.setdefault("panels", {}).setdefault(str(page), [])
        self.data["panels"][str(page)] = [
            p for p in panels if p.get("message_id") != message_id
        ]
        await self.save()

    async def clear_all_panels(self) -> None:
        """Remove every tracked panel across all pages and persist to disk."""
        self.data["panels"] = {str(p): [] for p in countries.PAGES.keys()}
        await self.save()

    def all_panels(self) -> Dict[str, List[Dict[str, int]]]:
        """Return all stored panels, keyed by page string."""
        return self.data.get("panels", {})


store = DataStore(config.DATA_FILE)


# --------------------------------------------------------------------------
# Bot setup
# --------------------------------------------------------------------------

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.reactions = True

bot = commands.Bot(command_prefix=config.COMMAND_PREFIX, intents=intents, help_command=None)


# --------------------------------------------------------------------------
# Permission check
# --------------------------------------------------------------------------

def has_allowed_role():
    """Command check factory: only allow members with one of the
    configured ALLOWED_ROLE_IDS to invoke the command.
    """

    async def predicate(ctx: commands.Context) -> bool:
        if ctx.guild is None or not isinstance(ctx.author, discord.Member):
            return False
        member_role_ids = {role.id for role in ctx.author.roles}
        return bool(member_role_ids.intersection(config.ALLOWED_ROLE_IDS))

    return commands.check(predicate)


# --------------------------------------------------------------------------
# Embed builders
# --------------------------------------------------------------------------

def build_panel_embed(page: int) -> discord.Embed:
    """Build the reaction-role embed for the given page."""
    page_countries = countries.get_page(page)

    lines = [
        f"{emoji}  {name}" for name, emoji in page_countries.items()
    ]
    country_list = "\n".join(lines)

    description = (
        f"{config.EMBED_DESCRIPTION}"
        f"**Page {page}**\n\n"
        f"{country_list}"
    )

    embed = discord.Embed(
        title=config.EMBED_TITLE,
        description=description,
        color=config.EMBED_COLOR,
    )
    embed.set_footer(text=config.EMBED_FOOTER)
    return embed


def build_help_embed() -> discord.Embed:
    """Build the embed shown by the $help command."""
    embed = discord.Embed(
        title="📖 Country Roles — Command Reference",
        description=(
            f"Prefix: `{config.COMMAND_PREFIX}`\n"
            "Commands below require one of the configured management roles, "
            "except where noted."
        ),
        color=config.EMBED_COLOR,
    )

    embed.add_field(
        name="🛠️ Setup",
        value=(
            f"`{config.COMMAND_PREFIX}rrsetup`\n"
            "Creates every missing country role in the server. "
            "Skips roles that already exist."
        ),
        inline=False,
    )

    embed.add_field(
        name="📋 Panels",
        value=(
            f"`{config.COMMAND_PREFIX}rr 1` / `{config.COMMAND_PREFIX}rr 2` / `{config.COMMAND_PREFIX}rr 3`\n"
            "Posts a brand-new reaction-role panel for that page. "
            "Can be run as many times as you like — every panel stays fully functional.\n\n"
            f"`{config.COMMAND_PREFIX}rr refresh`\n"
            "Deletes **every** existing panel (all pages) and posts exactly "
            "one fresh panel per page. Member roles are kept.\n\n"
            f"`{config.COMMAND_PREFIX}rr sync`\n"
            "Repairs every tracked panel: restores missing reactions and "
            "updates outdated embeds. Never creates duplicates.\n\n"
            f"`{config.COMMAND_PREFIX}rr delete`\n"
            "Deletes **every** panel message across all pages and clears "
            "them from storage. Roles are never touched."
        ),
        inline=False,
    )

    embed.add_field(
        name="📊 Info",
        value=(
            f"`{config.COMMAND_PREFIX}rrstats`\n"
            "Shows how many members currently hold each country role.\n\n"
            f"`{config.COMMAND_PREFIX}rrcount`\n"
            "Shows how many panels currently exist for each page."
        ),
        inline=False,
    )

    embed.add_field(
        name="🌍 How members pick a country",
        value=(
            "React with a flag emoji on any panel to receive that role. "
            "Only one country role is allowed at a time — reacting with a "
            "new flag automatically removes the old role and reaction. "
            "Removing your reaction removes the role."
        ),
        inline=False,
    )

    total_countries = len(countries.ALL_COUNTRIES)
    embed.set_footer(
        text=f"{total_countries} countries tracked across {len(countries.PAGES)} pages."
    )
    return embed


# --------------------------------------------------------------------------
# Role helpers
# --------------------------------------------------------------------------

async def get_or_create_role(
    guild: discord.Guild, name: str
) -> Optional[discord.Role]:
    """Return an existing role by name, or create it if missing.

    Returns None if creation fails due to permissions or API errors.
    """
    role = discord.utils.get(guild.roles, name=name)
    if role is not None:
        return role

    try:
        role = await guild.create_role(
            name=name,
            reason="Country Roles setup: creating missing country role.",
        )
        logger.info("Created role '%s' in guild '%s'.", name, guild.name)
        return role
    except discord.Forbidden:
        logger.error(
            "Missing permissions to create role '%s' in guild '%s'.",
            name,
            guild.name,
        )
    except discord.HTTPException as exc:
        logger.error("HTTP error creating role '%s': %s", name, exc)
    return None


async def remove_all_other_country_roles(
    member: discord.Member, keep_role_id: int
) -> None:
    """Remove every country role from a member except the one being kept."""
    country_role_names = set(countries.ALL_COUNTRIES)
    roles_to_remove = [
        role
        for role in member.roles
        if role.name in country_role_names and role.id != keep_role_id
    ]
    if not roles_to_remove:
        return
    try:
        await member.remove_roles(
            *roles_to_remove, reason="Country Roles: enforcing single country role."
        )
    except discord.Forbidden:
        logger.error(
            "Missing permissions to remove roles from member %s in guild %s.",
            member,
            member.guild,
        )
    except discord.HTTPException as exc:
        logger.error("HTTP error removing roles from member %s: %s", member, exc)


async def remove_other_country_reactions(
    message: discord.Message, member: discord.Member, keep_emoji: str
) -> None:
    """Remove the member's reactions for other countries on this message.

    This keeps the reaction panel visually consistent with the member's
    actual role (only one reaction should remain active).
    """
    for reaction in message.reactions:
        emoji_str = str(reaction.emoji)
        if emoji_str == keep_emoji:
            continue
        if not countries.is_country_emoji(emoji_str):
            continue
        try:
            await message.remove_reaction(reaction.emoji, member)
        except discord.Forbidden:
            logger.error(
                "Missing permissions to remove reaction for %s on message %s.",
                member,
                message.id,
            )
        except discord.NotFound:
            # Reaction or member already gone; safe to ignore.
            pass
        except discord.HTTPException as exc:
            logger.error("HTTP error removing reaction: %s", exc)


# --------------------------------------------------------------------------
# Panel management helpers
# --------------------------------------------------------------------------

async def fetch_message_safe(
    channel_id: int, message_id: int
) -> Optional[discord.Message]:
    """Attempt to fetch a message by channel/message ID.

    Returns None if the channel or message can no longer be found.
    """
    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            logger.warning("Channel %s not found.", channel_id)
            return None

    if not isinstance(channel, (discord.TextChannel, discord.Thread)):
        return None

    try:
        message = await channel.fetch_message(message_id)
        return message
    except discord.NotFound:
        logger.warning("Message %s not found (deleted).", message_id)
        return None
    except discord.Forbidden:
        logger.error("Missing permissions to fetch message %s in channel %s.", message_id, channel_id)
        return None
    except discord.HTTPException as exc:
        logger.error("HTTP error fetching message %s: %s", message_id, exc)
        return None


async def add_all_reactions(message: discord.Message, page: int) -> None:
    """Add every flag reaction for the given page to a message."""
    page_countries = countries.get_page(page)
    for emoji in page_countries.values():
        try:
            await message.add_reaction(emoji)
        except discord.Forbidden:
            logger.error("Missing permissions to add reaction %s.", emoji)
        except discord.HTTPException as exc:
            logger.error("HTTP error adding reaction %s: %s", emoji, exc)
        # Small delay to be gentle on rate limits.
        await asyncio.sleep(0.3)


async def create_new_panel(ctx: commands.Context, page: int) -> str:
    """Always create and send a brand-new panel for the given page.

    Panels can be created an unlimited number of times; each call is
    tracked independently in data.json.
    """
    embed = build_panel_embed(page)

    try:
        new_message = await ctx.send(embed=embed)
    except discord.Forbidden:
        return "❌ Missing permissions to send messages in this channel."
    except discord.HTTPException as exc:
        logger.error("HTTP error sending panel message: %s", exc)
        return f"❌ Failed to send panel for page {page} due to an API error."

    await store.add_panel(page, new_message.channel.id, new_message.id)
    await add_all_reactions(new_message, page)
    return f"✅ Created new panel for page {page} (message ID: {new_message.id})."


# --------------------------------------------------------------------------
# Bot events
# --------------------------------------------------------------------------

@bot.event
async def on_ready() -> None:
    """Called when the bot has successfully connected to Discord."""
    logger.info("Logged in as %s (ID: %s)", bot.user, bot.user.id if bot.user else "unknown")
    store.load()

    # Validate stored panels still exist; log warnings for any that don't.
    total_checked = 0
    total_missing = 0
    for page_str, panel_list in store.all_panels().items():
        for panel_info in panel_list:
            total_checked += 1
            message = await fetch_message_safe(
                panel_info.get("channel_id"), panel_info.get("message_id")
            )
            if message is None:
                total_missing += 1
                logger.warning(
                    "Panel message %s for page %s could not be located "
                    "on startup (may have been deleted manually).",
                    panel_info.get("message_id"),
                    page_str,
                )

    logger.info(
        "Startup panel check complete: %s tracked, %s unreachable.",
        total_checked,
        total_missing,
    )
    logger.info("Bot is ready.")


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError) -> None:
    """Global error handler for command invocation errors."""
    if isinstance(error, commands.CommandNotFound):
        return  # Silently ignore unknown commands.

    if isinstance(error, (commands.MissingPermissions, commands.CheckFailure)):
        await ctx.send("❌ You don't have permission to use this command.")
        return

    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing argument: `{error.param.name}`. See `$help`.")
        return

    if isinstance(error, commands.BadArgument):
        await ctx.send("❌ Invalid argument provided.")
        return

    logger.error("Unhandled command error in '%s': %s", ctx.command, error, exc_info=error)
    try:
        await ctx.send("❌ An unexpected error occurred. Please check the logs.")
    except discord.HTTPException:
        pass


@bot.event
async def on_error(event_method: str, *args: Any, **kwargs: Any) -> None:
    """Global event error handler to prevent the bot from crashing."""
    logger.exception("Unhandled exception in event '%s'.", event_method)


# --------------------------------------------------------------------------
# Reaction event handlers
# --------------------------------------------------------------------------

def _find_tracked_page(message_id: int) -> Optional[int]:
    """Return the page number if the given message ID is a tracked panel."""
    for page_str, panel_list in store.all_panels().items():
        for panel_info in panel_list:
            if panel_info.get("message_id") == message_id:
                return int(page_str)
    return None


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent) -> None:
    """Handle a reaction being added to a tracked panel message."""
    if payload.user_id == (bot.user.id if bot.user else None):
        return  # Ignore the bot's own reactions.

    page = _find_tracked_page(payload.message_id)
    if page is None:
        return  # Not a tracked panel.

    if payload.guild_id is None:
        return  # Reactions in DMs are irrelevant here.

    guild = bot.get_guild(payload.guild_id)
    if guild is None:
        logger.warning("Guild %s not found for reaction event.", payload.guild_id)
        return

    member = payload.member
    if member is None:
        try:
            member = await guild.fetch_member(payload.user_id)
        except (discord.NotFound, discord.HTTPException):
            logger.warning("Could not fetch member %s in guild %s.", payload.user_id, guild.id)
            return

    if member.bot:
        return  # Ignore bots.

    emoji_str = str(payload.emoji)
    country_name = countries.country_from_emoji(emoji_str)
    if country_name is None:
        return  # Reaction isn't one of our tracked country flags.

    role = discord.utils.get(guild.roles, name=country_name)
    if role is None:
        logger.warning(
            "Role '%s' does not exist in guild '%s'. Run $rrsetup first.",
            country_name,
            guild.name,
        )
        return

    # Assign the new role.
    try:
        await member.add_roles(role, reason="Country Roles: user selected a country.")
    except discord.Forbidden:
        logger.error("Missing permissions to add role '%s' to %s.", role.name, member)
        return
    except discord.HTTPException as exc:
        logger.error("HTTP error adding role '%s' to %s: %s", role.name, member, exc)
        return

    # Enforce single-country-role rule.
    await remove_all_other_country_roles(member, keep_role_id=role.id)

    # Keep reactions in sync: remove the user's reactions on any OTHER
    # country flags across every tracked panel (all pages, all copies)
    # so only the current selection remains highlighted for them.
    for page_str, panel_list in store.all_panels().items():
        for panel_info in panel_list:
            if panel_info.get("message_id") == payload.message_id:
                continue  # Skip the panel they just reacted on (handled below).
            panel_message = await fetch_message_safe(
                panel_info.get("channel_id"), panel_info.get("message_id")
            )
            if panel_message is None:
                continue
            try:
                await remove_other_country_reactions(panel_message, member, keep_emoji=emoji_str)
            except discord.HTTPException as exc:
                logger.error("Error syncing reactions across panels: %s", exc)

    # Also clean up any other reaction on the SAME panel the member reacted
    # on (in case they had multiple reactions on this one message somehow).
    same_message = await fetch_message_safe(payload.channel_id, payload.message_id)
    if same_message is not None:
        await remove_other_country_reactions(same_message, member, keep_emoji=emoji_str)


@bot.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent) -> None:
    """Handle a reaction being removed from a tracked panel message."""
    page = _find_tracked_page(payload.message_id)
    if page is None:
        return

    if payload.guild_id is None:
        return

    guild = bot.get_guild(payload.guild_id)
    if guild is None:
        logger.warning("Guild %s not found for reaction removal event.", payload.guild_id)
        return

    try:
        member = await guild.fetch_member(payload.user_id)
    except (discord.NotFound, discord.HTTPException):
        # Member may have left the server; nothing to do.
        return

    if member.bot:
        return

    emoji_str = str(payload.emoji)
    country_name = countries.country_from_emoji(emoji_str)
    if country_name is None:
        return

    role = discord.utils.get(guild.roles, name=country_name)
    if role is None:
        return  # Role doesn't exist; nothing to remove.

    if role not in member.roles:
        return  # Member doesn't have this role anyway.

    try:
        await member.remove_roles(role, reason="Country Roles: user removed their reaction.")
    except discord.Forbidden:
        logger.error("Missing permissions to remove role '%s' from %s.", role.name, member)
    except discord.HTTPException as exc:
        logger.error("HTTP error removing role '%s' from %s: %s", role.name, member, exc)


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------

@bot.command(name="help")
async def help_command(ctx: commands.Context) -> None:
    """Show the full command reference. Available to everyone."""
    try:
        await ctx.send(embed=build_help_embed())
    except discord.Forbidden:
        logger.error("Missing permissions to send the help embed in channel %s.", ctx.channel.id)
    except discord.HTTPException as exc:
        logger.error("HTTP error sending help embed: %s", exc)


@bot.command(name="rrsetup")
@has_allowed_role()
@commands.guild_only()
async def rrsetup(ctx: commands.Context) -> None:
    """Create every missing country role in the guild."""
    guild = ctx.guild
    if guild is None:
        return

    created = 0
    skipped = 0

    async with ctx.typing():
        for country_name in countries.ALL_COUNTRIES:
            existing = discord.utils.get(guild.roles, name=country_name)
            if existing is not None:
                skipped += 1
                continue

            role = await get_or_create_role(guild, country_name)
            if role is not None:
                created += 1
            else:
                skipped += 1
            await asyncio.sleep(0.3)  # Gentle on rate limits.

    await ctx.send(f"✅ Created {created} roles. Skipped {skipped} roles.")


@bot.group(name="rr", invoke_without_command=True)
@has_allowed_role()
@commands.guild_only()
async def rr(ctx: commands.Context, page: Optional[str] = None) -> None:
    """Main reaction-role command group.

    Usage:
        $rr 1/2/3    - create a NEW panel for that page (unlimited uses)
        $rr refresh  - delete ALL panels and resend one fresh panel per page
        $rr sync     - repair every existing panel
        $rr delete   - delete ALL panel messages (every page, every copy)
    """
    valid_pages = {str(p) for p in countries.PAGES.keys()}

    if page is None:
        page_list = "/".join(sorted(valid_pages))
        await ctx.send(
            f"Usage:\n"
            f"`$rr {page_list}` - create a new panel for that page (repeatable)\n"
            f"`$rr refresh` - delete ALL panels & resend one fresh panel per page\n"
            f"`$rr sync` - repair all existing panels\n"
            f"`$rr delete` - delete ALL panel messages\n\n"
            f"See `$help` for full details."
        )
        return

    page = page.lower().strip()

    if page in valid_pages:
        page_number = int(page)
        async with ctx.typing():
            status = await create_new_panel(ctx, page_number)
        await ctx.send(status)
        return

    if page == "refresh":
        await rr_refresh(ctx)
        return

    if page == "sync":
        await rr_sync(ctx)
        return

    if page == "delete":
        await rr_delete(ctx)
        return

    page_list = ", ".join(sorted(valid_pages))
    await ctx.send(
        f"❌ Unknown option. Use `{page_list}`, `refresh`, `sync`, or `delete`."
    )


async def rr_refresh(ctx: commands.Context) -> None:
    """Delete ALL existing panels (every page, every copy) and resend one
    fresh panel per page.

    Member country roles are untouched; only the panel messages and
    their reactions are recreated.
    """
    async with ctx.typing():
        deleted_count = await _delete_all_panels()

        # Send one fresh panel per page.
        results = []
        for page_number in countries.PAGES.keys():
            status = await create_new_panel(ctx, page_number)
            results.append(status)

    await ctx.send(
        f"🔄 Refresh complete. Deleted {deleted_count} old panel(s).\n"
        + "\n".join(results)
    )


async def rr_sync(ctx: commands.Context) -> None:
    """Repair every existing tracked panel across all pages:
    fix missing reactions and stale embeds. Never creates duplicates.
    """
    async with ctx.typing():
        results = []
        any_panels = False

        for page_number in countries.PAGES.keys():
            panel_list = store.get_panels(page_number)
            if not panel_list:
                results.append(f"⚠️ No panels stored for page {page_number}.")
                continue

            expected_embed = build_panel_embed(page_number)
            page_countries = countries.get_page(page_number)

            for panel_info in panel_list:
                any_panels = True
                message = await fetch_message_safe(
                    panel_info.get("channel_id"), panel_info.get("message_id")
                )
                if message is None:
                    results.append(
                        f"⚠️ Panel {panel_info.get('message_id')} (page {page_number}) "
                        f"could not be found (deleted?). Skipped."
                    )
                    continue

                # Check and fix the embed if it differs from the expected one.
                needs_edit = True
                if message.embeds:
                    current_embed = message.embeds[0]
                    if (
                        current_embed.title == expected_embed.title
                        and current_embed.description == expected_embed.description
                    ):
                        needs_edit = False

                if needs_edit:
                    try:
                        await message.edit(embed=expected_embed)
                    except (discord.Forbidden, discord.HTTPException) as exc:
                        logger.error("Error editing panel during sync: %s", exc)

                # Check and fix missing reactions.
                existing_emojis = {str(r.emoji) for r in message.reactions}
                added = 0
                for emoji in page_countries.values():
                    if emoji not in existing_emojis:
                        try:
                            await message.add_reaction(emoji)
                            added += 1
                            await asyncio.sleep(0.3)
                        except (discord.Forbidden, discord.HTTPException) as exc:
                            logger.error("Error adding reaction during sync: %s", exc)

                results.append(
                    f"✅ Panel {message.id} (page {page_number}) synced. "
                    f"Embed {'updated' if needs_edit else 'current'}, "
                    f"{added} reaction(s) restored."
                )

        if not any_panels:
            page_list = "/".join(str(p) for p in countries.PAGES.keys())
            results.append(f"No panels exist yet. Use `$rr {page_list}` to create some.")

    await ctx.send("\n".join(results))


async def _delete_all_panels() -> int:
    """Delete every tracked panel message across all pages and clear
    data.json. Returns the number of messages successfully deleted.
    """
    deleted = 0
    for page_str, panel_list in list(store.all_panels().items()):
        page_number = int(page_str)
        for panel_info in list(panel_list):
            message = await fetch_message_safe(
                panel_info.get("channel_id"), panel_info.get("message_id")
            )
            if message is not None:
                try:
                    await message.delete()
                    deleted += 1
                except discord.Forbidden:
                    logger.error(
                        "Missing permissions to delete panel message %s (page %s).",
                        panel_info.get("message_id"),
                        page_number,
                    )
                except discord.NotFound:
                    pass
                except discord.HTTPException as exc:
                    logger.error("HTTP error deleting panel message: %s", exc)

    await store.clear_all_panels()
    return deleted


async def rr_delete(ctx: commands.Context) -> None:
    """Delete ALL reaction-role panel messages (every page, every copy)
    and clear them from data.json. Country roles and member role
    assignments are never affected.
    """
    async with ctx.typing():
        deleted = await _delete_all_panels()

    await ctx.send(
        f"🗑️ Deleted {deleted} panel message(s) across all pages and cleared "
        f"data.json. Country roles and member assignments were not affected."
    )


@bot.command(name="rrcount")
@has_allowed_role()
@commands.guild_only()
async def rrcount(ctx: commands.Context) -> None:
    """Show how many panels currently exist for each page."""
    lines = []
    total = 0
    for page_number in countries.PAGES.keys():
        count = len(store.get_panels(page_number))
        total += count
        lines.append(f"Page {page_number}: **{count}** panel(s)")

    embed = discord.Embed(
        title="📋 Active Panel Count",
        description="\n".join(lines) if lines else "No panels tracked.",
        color=config.EMBED_COLOR,
    )
    embed.set_footer(text=f"Total: {total} panel message(s) across all pages.")
    await ctx.send(embed=embed)


@bot.command(name="rrstats")
@has_allowed_role()
@commands.guild_only()
async def rrstats(ctx: commands.Context) -> None:
    """Show how many members currently hold each country role."""
    guild = ctx.guild
    if guild is None:
        return

    async with ctx.typing():
        counts = []
        for country_name in countries.ALL_COUNTRIES:
            role = discord.utils.get(guild.roles, name=country_name)
            member_count = len(role.members) if role is not None else 0
            emoji = countries.emoji_from_country(country_name) or ""
            counts.append((country_name, emoji, member_count))

        # Sort by member count, descending; keep only countries with 1+ members
        # near the top, but still show the rest for completeness.
        counts.sort(key=lambda item: item[2], reverse=True)

        lines = [
            f"{emoji}  **{name}** — {count}"
            for name, emoji, count in counts
            if count > 0
        ]

        if not lines:
            description = "No members currently hold any country role."
        else:
            description = "\n".join(lines)

        # Discord embed description limit is 4096 characters; truncate safely.
        if len(description) > 4000:
            description = description[:4000] + "\n… (truncated)"

        embed = discord.Embed(
            title="📊 Country Role Distribution",
            description=description,
            color=config.EMBED_COLOR,
        )
        total_assigned = sum(c for _, _, c in counts)
        embed.set_footer(text=f"Total members with a country role: {total_assigned}")

    await ctx.send(embed=embed)


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def main() -> None:
    """Entry point for running the bot."""
    if not config.DISCORD_TOKEN:
        logger.critical(
            "DISCORD_TOKEN environment variable is not set. "
            "Set it before starting the bot."
        )
        raise SystemExit(1)

    store.load()

    try:
        bot.run(config.DISCORD_TOKEN, log_handler=None)
    except discord.LoginFailure:
        logger.critical("Failed to log in: invalid DISCORD_TOKEN.")
        raise SystemExit(1)
    except discord.HTTPException as exc:
        logger.critical("HTTP error while starting the bot: %s", exc)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
