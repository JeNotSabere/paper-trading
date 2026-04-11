"""Load settings from environment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _f(name: str, default: float) -> float:
    v = os.getenv(name)
    return float(v) if v is not None and v != "" else default


def _i(name: str, default: int) -> int:
    v = os.getenv(name)
    return int(v) if v is not None and v != "" else default


def _s(name: str, default: str) -> str:
    v = os.getenv(name)
    return v if v is not None and v != "" else default


@dataclass(frozen=True)
class Settings:
    discord_bot_token: str
    discord_guild_id: int
    channel_momentum: str
    channel_mean_reversion: str
    channel_random: str
    channel_hybrid: str
    channel_leaderboards: str
    initial_balance_eur: float
    tick_min_sec: int
    tick_max_sec: int
    watchlist: tuple[str, ...]
    percent_fee: float
    min_fee_eur: float
    spread_bps: float
    data_dir: Path


def load_settings() -> Settings:
    token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("DISCORD_BOT_TOKEN is required")

    guild = os.getenv("DISCORD_GUILD_ID", "").strip()
    if not guild:
        raise RuntimeError("DISCORD_GUILD_ID is required")

    raw_watch = _s("WATCHLIST", "BTC-EUR,ETH-EUR,AIR.PA,SAN.MC")
    watchlist = tuple(s.strip().upper() for s in raw_watch.split(",") if s.strip())

    data_dir = Path(_s("DATA_DIR", "data")).resolve()

    return Settings(
        discord_bot_token=token,
        discord_guild_id=int(guild),
        channel_momentum=_s("CHANNEL_MOMENTUM", "agent-momentum"),
        channel_mean_reversion=_s("CHANNEL_MEAN_REVERSION", "agent-mean-reversion"),
        channel_random=_s("CHANNEL_RANDOM", "agent-random"),
        channel_hybrid=_s("CHANNEL_HYBRID", "agent-reversion"),
        channel_leaderboards=_s("CHANNEL_LEADERBOARDS", "leaderboards"),
        initial_balance_eur=_f("INITIAL_BALANCE_EUR", 50.0),
        tick_min_sec=_i("TICK_MIN_SEC", 60),
        tick_max_sec=_i("TICK_MAX_SEC", 180),
        watchlist=watchlist,
        percent_fee=_f("PERCENT_FEE", 0.0008),
        min_fee_eur=_f("MIN_FEE_EUR", 0.25),
        spread_bps=_f("SPREAD_BPS", 5.0),
        data_dir=data_dir,
    )
