"""Entry: Discord bot + paper-trading loops + Lisbon 10:00/22:00 reports."""

from __future__ import annotations

import asyncio
import logging
import random
import sys
from dataclasses import dataclass
from pathlib import Path

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from paper_agent.broker.paper import PaperBroker
from paper_agent.config import Settings, load_settings
from paper_agent.discord_bot.notifier import DiscordNotifier
from paper_agent.learning.adaptive import AdaptiveLearner
from paper_agent.market.prices import PriceFeed
from paper_agent.persistence.csv_logger import append_trade_csv, write_state_snapshot
from paper_agent.reporting import build_agent_report, build_leaderboard
from paper_agent.runner import execute_action
from paper_agent.strategies import (
    HybridStrategy,
    MeanReversionStrategy,
    MomentumStrategy,
    RandomBaselineStrategy,
)
from paper_agent.strategies.base import Strategy
from paper_agent.strategies.history import RollingPrices

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("paper_agent.main")


@dataclass
class AgentBundle:
    slug: str
    strategy: Strategy
    broker: PaperBroker
    learner: AdaptiveLearner
    last_meta: dict | None = None


def _make_bundles(settings: Settings) -> list[AgentBundle]:
    fee_kw = dict(
        percent_fee=settings.percent_fee,
        min_fee_eur=settings.min_fee_eur,
        spread_bps=settings.spread_bps,
    )
    return [
        AgentBundle(
            "momentum",
            MomentumStrategy(),
            PaperBroker(
                "Momentum",
                settings.initial_balance_eur,
                **fee_kw,
            ),
            AdaptiveLearner(),
        ),
        AgentBundle(
            "mean_reversion",
            MeanReversionStrategy(),
            PaperBroker(
                "Mean reversion",
                settings.initial_balance_eur,
                **fee_kw,
            ),
            AdaptiveLearner(),
        ),
        AgentBundle(
            "random",
            RandomBaselineStrategy(),
            PaperBroker(
                "Random baseline",
                settings.initial_balance_eur,
                **fee_kw,
            ),
            AdaptiveLearner(),
        ),
        AgentBundle(
            "hybrid",
            HybridStrategy(),
            PaperBroker(
                "Hybrid",
                settings.initial_balance_eur,
                **fee_kw,
            ),
            AdaptiveLearner(),
        ),
    ]


def _channel_map(settings: Settings) -> dict[str, str]:
    return {
        "momentum": settings.channel_momentum,
        "mean_reversion": settings.channel_mean_reversion,
        "random": settings.channel_random,
        "hybrid": settings.channel_hybrid,
    }


async def _tick(
    bundle: AgentBundle,
    prices: dict[str, float],
    history: RollingPrices,
    settings: Settings,
    notifier: DiscordNotifier,
) -> None:
    b = bundle.broker
    eq = b.equity_eur(prices)
    action = bundle.strategy.decide(b, prices, history, bundle.learner)
    bundle.last_meta = action.meta
    rec = execute_action(b, prices, action, eq)
    if not rec:
        return

    append_trade_csv(settings.data_dir, bundle.slug, rec)

    pnl_txt = ""
    if rec.realized_pnl_eur is not None:
        pnl_txt = f" | Realized P/L: **{rec.realized_pnl_eur:+.2f} €**"
        bundle.learner.on_sell(
            rec,
            strategy_name=bundle.strategy.name,
            meta=bundle.last_meta,
        )

    msg = (
        f"**{rec.side}** {rec.symbol}\n"
        f"Qty: `{rec.qty:.6f}` @ **{rec.price_eur:.4f} €** (mid+spread)\n"
        f"Fee: **{rec.fee_eur:.4f} €** | Cash: **{rec.cash_after_eur:.2f} €**{pnl_txt}"
    )
    await notifier.send_trade(bundle.strategy.name, msg)


async def trading_loop(
    bot: discord.Client,
    settings: Settings,
    bundles: list[AgentBundle],
    history: RollingPrices,
    notifier: DiscordNotifier,
) -> None:
    feed = PriceFeed(settings.watchlist)
    await bot.wait_until_ready()
    logger.info("Trading loop started; watchlist=%s", settings.watchlist)

    while not bot.is_closed():
        try:
            prices = await feed.get_prices_eur()
            if len(prices) < len(settings.watchlist) * 0.25:
                logger.warning("Thin price snapshot: %s", prices)
            history.push(prices)

            for bundle in bundles:
                await _tick(bundle, prices, history, settings, notifier)

            delay = random.uniform(float(settings.tick_min_sec), float(settings.tick_max_sec))
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Trading tick failed")
            await asyncio.sleep(30.0)


async def scheduled_reports(
    bot: discord.Client,
    settings: Settings,
    bundles: list[AgentBundle],
    notifier: DiscordNotifier,
) -> None:
    feed = PriceFeed(settings.watchlist)
    prices = await feed.get_prices_eur()
    parts = [build_leaderboard([(x.slug, x.broker, settings.initial_balance_eur) for x in bundles], prices)]
    for bundle in bundles:
        parts.append(
            build_agent_report(bundle.broker, prices, settings.initial_balance_eur),
        )
        write_state_snapshot(settings.data_dir, bundle.slug, bundle.broker, bundle.broker.equity_eur(prices))

    text = "\n\n".join(parts)
    csvs = [settings.data_dir / f"trades_{b.slug}.csv" for b in bundles]
    await notifier.send_leaderboard(text, files=csvs)


def main() -> None:
    settings = load_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    bundles = _make_bundles(settings)
    history = RollingPrices(maxlen=120)

    intents = discord.Intents.default()
    intents.guilds = True
    bot = discord.Client(intents=intents)
    notifier = DiscordNotifier(
        bot,
        settings.discord_guild_id,
        _channel_map(settings),
        settings.channel_leaderboards,
    )

    scheduler: AsyncIOScheduler | None = None

    @bot.event
    async def on_ready() -> None:
        nonlocal scheduler
        if getattr(bot, "_paper_agent_started", False):
            return
        bot._paper_agent_started = True  # type: ignore[attr-defined]

        logger.info("Logged in as %s (%s)", bot.user, bot.user.id if bot.user else "")
        asyncio.create_task(trading_loop(bot, settings, bundles, history, notifier))

        scheduler = AsyncIOScheduler(timezone="Europe/Lisbon")

        async def job() -> None:
            if bot.is_closed():
                return
            await scheduled_reports(bot, settings, bundles, notifier)

        scheduler.add_job(job, "cron", hour=10, minute=0)
        scheduler.add_job(job, "cron", hour=22, minute=0)
        scheduler.start()
        logger.info("Scheduler: reports at 10:00 and 22:00 Europe/Lisbon")

    bot.run(settings.discord_bot_token)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
