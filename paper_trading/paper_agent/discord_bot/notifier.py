"""Discord: resolve channels by name, post trades, reports, CSV attachments."""

from __future__ import annotations

import io
import logging
from pathlib import Path

import discord

logger = logging.getLogger(__name__)


class DiscordNotifier:
    def __init__(
        self,
        bot: discord.Client,
        guild_id: int,
        channel_map: dict[str, str],
        leaderboards_name: str,
    ) -> None:
        self.bot = bot
        self.guild_id = guild_id
        self.channel_map = channel_map  # strategy_name -> channel name
        self.leaderboards_name = leaderboards_name

    def _guild(self) -> discord.Guild | None:
        g = self.bot.get_guild(self.guild_id)
        return g

    async def _text_channel(self, channel_name: str) -> discord.TextChannel | None:
        g = self._guild()
        if not g:
            logger.error("Guild %s not found", self.guild_id)
            return None
        ch = discord.utils.get(g.text_channels, name=channel_name)
        if not ch:
            logger.error("Channel #%s not found in guild", channel_name)
        return ch

    async def send_trade(self, strategy_name: str, text: str) -> None:
        name = self.channel_map.get(strategy_name)
        if not name:
            return
        ch = await self._text_channel(name)
        if ch:
            await ch.send(text[:1900])

    async def send_leaderboard(self, text: str, files: list[Path] | None = None) -> None:
        ch = await self._text_channel(self.leaderboards_name)
        if not ch:
            return
        discord_files: list[discord.File] = []
        if files:
            for p in files:
                if p.is_file():
                    discord_files.append(discord.File(str(p)))
        if discord_files:
            await ch.send(content=text[:1900], files=discord_files)
        else:
            await ch.send(content=text[:1900])

    async def upload_csv_snippet(self, path: Path, max_lines: int = 400) -> None:
        ch = await self._text_channel(self.leaderboards_name)
        if not ch or not path.is_file():
            return
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        body = "\n".join(lines[-max_lines:])
        buf = io.BytesIO(body.encode("utf-8"))
        await ch.send(
            file=discord.File(buf, filename=path.name),
        )
