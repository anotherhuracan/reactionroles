"""
Country Roles Discord Bot
==========================

A production-ready Discord bot that lets members self-assign a single
country role via reaction-role panels.

Features:
    - $rrsetup       : Create all missing country roles.
    - $rr 1 / $rr 2   : Create/edit reaction-role panels for page 1 / 2.
    - $rr refresh    : Delete and resend panels, preserving member roles.
    - $rr sync       : Repair panels (missing reactions / stale embeds).
    - $rr delete     : Delete only the panel messages (not roles).

Persistence:
    Message IDs and channel IDs for each panel are stored in data.json
    so the bot can recover its state after a restart (e.g. on Railway).

Author: Generated for production Railway deployment.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional

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
            "1": {"channel_id": int, "message_id": int},
            "2": {"channel_id": int, "message_id": int}
        }
    }
    """

    def __init__(self, path: str) -> None:
        self.path = path
        self._lock = asyncio.Lock()
        self.data: Dict[str, Any] = {"panels": {}}

    def load(self) -> None:
        """Load data from disk, creating a default file if missing/corrupt."""
        if not os.path.exists(self.path):
            logger.info("No data file found at %s, creating a new one.", self.path)
            self.data = {"panels": {}}
            self._save_sync()
            return

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if not isinstance(loaded, dict) or "panels" not in loaded:
                raise ValueError("Malformed data.json structure")
            self.data = loaded
            logger.info("Loaded data.json successfully.")
        except (json.JSONDecodeError, ValueError, OSError) as exc:
            logger.error("Failed to load data.json (%s). Starting fresh.", exc)
            self.data = {"panels": {}}
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

    def get_panel(self, page: int) -> Optional[Dict[str, int]]:
        """Return stored panel info (channel_id, message_id) for a page."""
        return self.data.get("panels", {}).get(str(page))

    async def set_panel(self, page: int, channel_id: int, message_id: int) -> None:
        """Store panel info for a page and persist to disk."""
        self.data.setdefault("panels", {})[str(page)] = {
            "channel_id": channel_id,
            "message_id": message_id,
        }
        await self.save()

    async def remove_panel(self, page: int) -> None:
        """Remove a stored panel entry and persist to disk."""
        panels = self.data.setdefault("panels", {})
        if str(page) in panels:
            del panels[str(page)]
            await self.save()

    def all_panels(self) -> Dict[str, Dict[str, int]]:
        """Return all stored panels."""
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
# Embed builder
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


def get_country_roles(guild: discord.Guild) -> Dict[str, discord.Role]:
    """Return a mapping of country name -> Role object for roles that exist."""
    result: Dict[str, discord.Role] = {}
    for country_name in countries.ALL_COUNTRIES:
        role = discord.utils.get(guild.roles, name=country_name)
        if role is not None:
            result[country_name] = role
    return result


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

async def fetch_panel_message(
    page: int,
) -> Optional[discord.Message]:
    """Attempt to fetch the stored panel message for a page.

    Returns None if no panel is stored, or if the channel/message
    can no longer be found (deleted channel/message, etc).
    """
    panel_info = store.get_panel(page)
    if panel_info is None:
        return None

    channel_id = panel_info.get("channel_id")
    message_id = panel_info.get("message_id")
    if channel_id is None or message_id is None:
        return None

    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            logger.warning("Stored channel %s for page %s not found.", channel_id, page)
            return None

    if not isinstance(channel, (discord.TextChannel, discord.Thread)):
        return None

    try:
        message = await channel.fetch_message(message_id)
        return message
    except discord.NotFound:
        logger.warning("Stored message %s for page %s not found (deleted).", message_id, page)
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


async def create_or_update_panel(
    ctx: commands.Context, page: int
) -> str:
    """Create a new panel or edit the existing one for the given page.

    Returns a human-readable status string.
    """
    embed = build_panel_embed(page)

    existing_message = await fetch_panel_message(page)

    if existing_message is not None:
        # Panel exists and is reachable -> edit it in place.
        try:
            await existing_message.edit(embed=embed)
        except discord.Forbidden:
            return f"❌ Missing permissions to edit the panel for page {page}."
        except discord.HTTPException as exc:
            logger.error("HTTP error editing panel message: %s", exc)
            return f"❌ Failed to edit the panel for page {page} due to an API error."

        # Ensure all reactions are present (covers manually-cleared reactions).
        existing_emojis = {str(r.emoji) for r in existing_message.reactions}
        page_countries = countries.get_page(page)
        for emoji in page_countries.values():
            if emoji not in existing_emojis:
                try:
                    await existing_message.add_reaction(emoji)
                    await asyncio.sleep(0.3)
                except (discord.Forbidden, discord.HTTPException) as exc:
                    logger.error("Error adding missing reaction %s: %s", emoji, exc)

        return f"✏️ Edited existing panel for page {page}."

    # No existing/reachable panel -> send a new one.
    try:
        new_message = await ctx.send(embed=embed)
    except discord.Forbidden:
        return "❌ Missing permissions to send messages in this channel."
    except discord.HTTPException as exc:
        logger.error("HTTP error sending panel message: %s", exc)
        return f"❌ Failed to send panel for page {page} due to an API error."

    await store.set_panel(page, new_message.channel.id, new_message.id)
    await add_all_reactions(new_message, page)
    return f"✅ Created new panel for page {page}."


# --------------------------------------------------------------------------
# Bot events
# --------------------------------------------------------------------------

@bot.event
async def on_ready() -> None:
    """Called when the bot has successfully connected to Discord."""
    logger.info("Logged in as %s (ID: %s)", bot.user, bot.user.id if bot.user else "unknown")
    store.load()

    # Validate stored panels still exist; log warnings for any that don't.
    for page_str in list(store.all_panels().keys()):
        page = int(page_str)
        message = await fetch_panel_message(page)
        if message is None:
            logger.warning(
                "Panel for page %s could not be located on startup "
                "(channel/message may have been deleted). It will be "
                "recreated on next '$rr %s' or '$rr refresh'.",
                page,
                page,
            )
        else:
            logger.info("Verified panel for page %s is reachable.", page)

    logger.info("Bot is ready.")


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError) -> None:
    """Global error handler for command invocation errors."""
    if isinstance(error, commands.CommandNotFound):
        return  # Silently ignore unknown commands.

    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command.")
        return

    if isinstance(error, commands.CheckFailure):
        await ctx.send("❌ You don't have permission to use this command.")
        return

    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing argument: `{error.param.name}`. See `$rr` usage.")
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

def _is_tracked_panel_message(message_id: int) -> Optional[int]:
    """Return the page number if the given message ID is a tracked panel."""
    for page_str, info in store.all_panels().items():
        if info.get("message_id") == message_id:
            return int(page_str)
    return None


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent) -> None:
    """Handle a reaction being added to a tracked panel message."""
    if payload.user_id == (bot.user.id if bot.user else None):
        return  # Ignore the bot's own reactions.

    page = _is_tracked_panel_message(payload.message_id)
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
    # country flags (across both panel pages) so only the current
    # selection remains highlighted for them.
    channel = bot.get_channel(payload.channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(payload.channel_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            channel = None

    if channel is not None and isinstance(channel, (discord.TextChannel, discord.Thread)):
        for page_str in store.all_panels().keys():
            other_page = int(page_str)
            panel_message = await fetch_panel_message(other_page)
            if panel_message is None:
                continue
            try:
                await remove_other_country_reactions(panel_message, member, keep_emoji=emoji_str)
            except discord.HTTPException as exc:
                logger.error("Error syncing reactions across panels: %s", exc)


@bot.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent) -> None:
    """Handle a reaction being removed from a tracked panel message."""
    page = _is_tracked_panel_message(payload.message_id)
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

@bot.command(name="rrsetup")
@commands.has_permissions(manage_roles=True)
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
@commands.has_permissions(manage_roles=True)
@commands.guild_only()
async def rr(ctx: commands.Context, page: Optional[str] = None) -> None:
    """Main reaction-role command group.

    Usage:
        $rr 1        - create/edit panel for page 1
        $rr 2        - create/edit panel for page 2
        $rr refresh  - delete and resend all panels
        $rr sync     - repair existing panels
        $rr delete   - delete panel messages only
    """
    if page is None:
        await ctx.send(
            "Usage:\n"
            "`$rr 1` - create/update page 1 panel\n"
            "`$rr 2` - create/update page 2 panel\n"
            "`$rr refresh` - delete & resend all panels\n"
            "`$rr sync` - repair existing panels\n"
            "`$rr delete` - delete panel messages only"
        )
        return

    page = page.lower().strip()

    if page in ("1", "2"):
        page_number = int(page)
        async with ctx.typing():
            status = await create_or_update_panel(ctx, page_number)
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

    await ctx.send(
        "❌ Unknown option. Use `1`, `2`, `refresh`, `sync`, or `delete`."
    )


async def rr_refresh(ctx: commands.Context) -> None:
    """Delete existing panels and resend fresh ones.

    Member country roles are untouched; only the panel messages and
    their reactions are recreated.
    """
    async with ctx.typing():
        # Step 1: delete existing panel messages (if reachable).
        for page_str in list(store.all_panels().keys()):
            page_number = int(page_str)
            message = await fetch_panel_message(page_number)
            if message is not None:
                try:
                    await message.delete()
                except discord.Forbidden:
                    logger.error("Missing permissions to delete panel message for page %s.", page_number)
                except discord.NotFound:
                    pass
                except discord.HTTPException as exc:
                    logger.error("HTTP error deleting panel message: %s", exc)
            await store.remove_panel(page_number)

        # Step 2: send fresh panels for both pages.
        results = []
        for page_number in (1, 2):
            status = await create_or_update_panel(ctx, page_number)
            results.append(status)

    await ctx.send("🔄 Refresh complete.\n" + "\n".join(results))


async def rr_sync(ctx: commands.Context) -> None:
    """Repair existing panels: fix missing reactions and stale embeds."""
    async with ctx.typing():
        results = []
        for page_number in (1, 2):
            panel_info = store.get_panel(page_number)
            if panel_info is None:
                results.append(f"⚠️ No panel stored for page {page_number}. Use `$rr {page_number}` to create one.")
                continue

            message = await fetch_panel_message(page_number)
            if message is None:
                results.append(
                    f"⚠️ Panel for page {page_number} could not be found "
                    f"(deleted?). Use `$rr {page_number}` to recreate it."
                )
                continue

            # Check and fix the embed if it differs from the expected one.
            expected_embed = build_panel_embed(page_number)
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
            page_countries = countries.get_page(page_number)
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
                f"✅ Page {page_number} synced. "
                f"Embed {'updated' if needs_edit else 'already current'}, "
                f"{added} reaction(s) restored."
            )

    await ctx.send("\n".join(results))


async def rr_delete(ctx: commands.Context) -> None:
    """Delete only the reaction-role panel messages, preserving roles."""
    async with ctx.typing():
        deleted = 0
        for page_str in list(store.all_panels().keys()):
            page_number = int(page_str)
            message = await fetch_panel_message(page_number)
            if message is not None:
                try:
                    await message.delete()
                    deleted += 1
                except discord.Forbidden:
                    logger.error("Missing permissions to delete panel message for page %s.", page_number)
                except discord.NotFound:
                    pass
                except discord.HTTPException as exc:
                    logger.error("HTTP error deleting panel message: %s", exc)
            await store.remove_panel(page_number)

    await ctx.send(
        f"🗑️ Deleted {deleted} panel message(s) and cleared them from data.json. "
        f"Country roles and member assignments were not affected."
    )


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
