"""Price feed: yfinance for stocks and crypto (same precision as the library provides)."""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Iterable

import yfinance as yf

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="yfinance")


def _fetch_one(sym: str) -> float | None:
    t = yf.Ticker(sym)
    try:
        fast = t.fast_info
        last = None
        if fast is not None:
            last = getattr(fast, "last_price", None) or getattr(fast, "lastPrice", None)
        if last is None or last != last:
            hist = t.history(period="5d", interval="1d")
            if not hist.empty:
                last = float(hist["Close"].iloc[-1])
            else:
                hist2 = t.history(period="2d", interval="1h")
                if not hist2.empty:
                    last = float(hist2["Close"].iloc[-1])
        if last is not None and last == last:
            return float(last)
    except Exception:
        logger.warning("Price fetch failed for %s", sym, exc_info=True)
    return None


def _fetch_batch(symbols: list[str]) -> dict[str, float]:
    """Blocking: last price in instrument currency (yfinance; delayed / best-effort)."""
    out: dict[str, float] = {}
    for sym in symbols:
        px = _fetch_one(sym)
        if px is not None:
            out[sym] = px
        else:
            logger.warning("No price for %s", sym)
    return out


class PriceFeed:
    """Async wrapper around yfinance (runs in thread pool)."""

    def __init__(self, symbols: Iterable[str]) -> None:
        self.symbols = tuple(dict.fromkeys(s.upper() for s in symbols))

    async def get_prices_eur(self) -> dict[str, float]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, _fetch_batch, list(self.symbols))
