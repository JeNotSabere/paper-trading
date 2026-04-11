"""Execute strategy actions against the paper broker."""

from __future__ import annotations

from paper_agent.broker.paper import PaperBroker, TradeRecord
from paper_agent.strategies.base import Action


def execute_action(
    broker: PaperBroker,
    prices: dict[str, float],
    action: Action,
    equity_eur: float,
) -> TradeRecord | None:
    if action.side == "HOLD" or not action.symbol:
        return None
    mid = prices.get(action.symbol)
    if mid is None or not (mid == mid):
        return None

    strength = max(0.05, min(1.0, float(action.strength)))

    if action.side == "BUY":
        notional = equity_eur * 0.12 * strength
        if notional < 2.0:
            notional = min(equity_eur * 0.25, max(2.0, equity_eur * 0.05))
        qty = notional / mid
        qty = _round_qty(qty, action.symbol)
        if qty <= 0:
            return None
        return broker.buy(action.symbol, qty, mid)

    if action.side == "SELL":
        pos = broker.positions.get(action.symbol)
        if not pos:
            return None
        frac = min(0.55, max(0.1, 0.2 + 0.35 * strength))
        qty = min(pos.qty, pos.qty * frac)
        qty = _round_qty(qty, action.symbol)
        if qty <= 0:
            return None
        return broker.sell(action.symbol, qty, mid)

    return None


def _round_qty(qty: float, symbol: str) -> float:
    sym = symbol.upper()
    if "-" in sym or sym.endswith("USD") or len(sym) <= 5 and any(c.isdigit() for c in sym):
        return round(qty, 6)
    return round(qty, 4)
