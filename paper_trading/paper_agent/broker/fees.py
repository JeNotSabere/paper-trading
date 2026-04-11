"""Variable, realistic-style fees: max(min, percent * notional) + spread proxy."""

from __future__ import annotations


def compute_fee_eur(
    notional_eur: float,
    *,
    percent_fee: float,
    min_fee_eur: float,
) -> float:
    """Broker fee in EUR (one side)."""
    pct = abs(notional_eur) * percent_fee
    return max(min_fee_eur, pct)


def apply_spread_to_price(
    mid_eur: float,
    side: str,
    spread_bps: float,
) -> float:
    """
    Simulate bid/ask: buy pays above mid, sell receives below mid.
    spread_bps is total spread in basis points (e.g. 5 => 0.05%).
    """
    half = (spread_bps / 10_000.0) * mid_eur / 2.0
    if side.upper() == "BUY":
        return mid_eur + half
    if side.upper() == "SELL":
        return mid_eur - half
    raise ValueError("side must be BUY or SELL")
