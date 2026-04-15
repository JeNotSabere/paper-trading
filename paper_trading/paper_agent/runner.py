"""Execute strategy actions against the paper broker."""

from __future__ import annotations

from paper_agent.config import Settings
from paper_agent.broker.paper import PaperBroker, TradeRecord
from paper_agent.strategies.base import Action


def execute_action(
    broker: PaperBroker,
    prices: dict[str, float],
    action: Action,
    equity_eur: float,
    settings: Settings,
) -> TradeRecord | None:
    if action.side == "HOLD" or not action.symbol:
        return None
    mid = prices.get(action.symbol)
    if mid is None or not (mid == mid):
        return None

    strength = max(0.05, min(1.0, float(action.strength)))
    min_safe_notional = _safe_min_notional(settings, broker)

    if action.side == "BUY":
        notional = equity_eur * 0.10 * strength
        notional = max(notional, min_safe_notional, settings.min_order_notional_eur)
        if notional > broker.cash_eur:
            notional = broker.cash_eur
        current_notional = 0.0
        pos = broker.positions.get(action.symbol)
        if pos:
            current_notional = pos.qty * mid
        max_symbol_notional = max(0.0, equity_eur * max(0.05, settings.max_symbol_allocation))
        if current_notional >= max_symbol_notional:
            return None
        notional = min(notional, max_symbol_notional - current_notional)
        if notional < min_safe_notional:
            return None
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
        # Avoid tiny sells where the minimum fee dominates the trade.
        if qty * mid < min_safe_notional:
            qty = pos.qty
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


def _safe_min_notional(settings: Settings, broker: PaperBroker) -> float:
    # Keep the fee ratio bounded so trades are not eaten by min-fee.
    max_rate = max(settings.max_fee_rate_per_side, broker.percent_fee + 1e-6)
    fee_floor_notional = broker.min_fee_eur / max_rate if broker.min_fee_eur > 0 else 0.0
    return max(settings.min_order_notional_eur, fee_floor_notional)
