"""Price feed: yfinance for stocks/crypto, normalized to EUR."""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Iterable

import yfinance as yf

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="yfinance")


def _fetch_last_price(sym: str) -> float | None:
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


def _extract_currency(sym: str) -> tuple[str, float]:
    """
    Return (currency, quote_multiplier).

    Some venues quote in subunits (for example GBp). Multiplier converts quote
    units to the major currency before FX conversion.
    """
    t = yf.Ticker(sym)
    currency = "EUR"
    try:
        fast = t.fast_info
        ccy = None
        if fast is not None:
            if hasattr(fast, "get"):
                ccy = fast.get("currency")
            if not ccy:
                ccy = getattr(fast, "currency", None)
        if not ccy:
            meta = t.get_history_metadata() or {}
            ccy = meta.get("currency")
        if ccy:
            currency = str(ccy).upper()
    except Exception:
        logger.debug("Currency metadata failed for %s", sym, exc_info=True)

    if currency in {"GBX", "GBPX", "GBPENCE", "GBP.PENCE"}:
        return "GBP", 0.01
    return currency, 1.0


def _fx_to_eur_rate(currency: str) -> float | None:
    ccy = currency.upper()
    if ccy == "EUR":
        return 1.0
    pair = f"{ccy}EUR=X"
    return _fetch_last_price(pair)


def _fetch_one_eur(sym: str) -> float | None:
    raw = _fetch_last_price(sym)
    if raw is None:
        return None
    currency, quote_mult = _extract_currency(sym)
    fx = _fx_to_eur_rate(currency)
    if fx is None:
        logger.warning("No FX rate %s->EUR for %s", currency, sym)
        return None
    return float(raw) * quote_mult * float(fx)


def _fetch_batch(symbols: list[str]) -> dict[str, float]:
    """Blocking: last price normalized to EUR (best effort)."""
    out: dict[str, float] = {}
    for sym in symbols:
        px = _fetch_one_eur(sym)
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
