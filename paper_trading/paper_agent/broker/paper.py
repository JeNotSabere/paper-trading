"""Paper portfolio: EUR cash, positions, fees, PnL."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from paper_agent.broker.fees import apply_spread_to_price, compute_fee_eur


@dataclass
class Position:
    symbol: str
    qty: float
    avg_price_eur: float


@dataclass
class TradeRecord:
    id: str
    ts_utc: str
    agent: str
    symbol: str
    side: Literal["BUY", "SELL"]
    qty: float
    price_eur: float
    fee_eur: float
    cash_after_eur: float
    realized_pnl_eur: float | None


@dataclass
class PaperBroker:
    agent_name: str
    initial_cash_eur: float
    percent_fee: float
    min_fee_eur: float
    spread_bps: float
    cash_eur: float = field(init=False)
    positions: dict[str, Position] = field(default_factory=dict)
    trades: list[TradeRecord] = field(default_factory=list)
    realized_pnl_eur: float = 0.0

    def __post_init__(self) -> None:
        self.cash_eur = float(self.initial_cash_eur)

    def equity_eur(self, prices_eur: dict[str, float]) -> float:
        """Mark-to-market in EUR."""
        pos_val = 0.0
        for sym, pos in self.positions.items():
            px = prices_eur.get(sym)
            if px is None:
                continue
            pos_val += pos.qty * px
        return self.cash_eur + pos_val

    def buy(
        self,
        symbol: str,
        qty: float,
        mid_price_eur: float,
    ) -> TradeRecord | None:
        if qty <= 0:
            return None
        exec_px = apply_spread_to_price(mid_price_eur, "BUY", self.spread_bps)
        notional = qty * exec_px
        fee = compute_fee_eur(notional, percent_fee=self.percent_fee, min_fee_eur=self.min_fee_eur)
        total = notional + fee
        if total > self.cash_eur + 1e-9:
            return None

        self.cash_eur -= total
        prev = self.positions.get(symbol)
        if prev is None:
            self.positions[symbol] = Position(symbol, qty, exec_px)
        else:
            new_qty = prev.qty + qty
            new_avg = (prev.qty * prev.avg_price_eur + qty * exec_px) / new_qty
            self.positions[symbol] = Position(symbol, new_qty, new_avg)

        rec = TradeRecord(
            id=str(uuid4()),
            ts_utc=datetime.now(timezone.utc).isoformat(),
            agent=self.agent_name,
            symbol=symbol,
            side="BUY",
            qty=qty,
            price_eur=exec_px,
            fee_eur=fee,
            cash_after_eur=self.cash_eur,
            realized_pnl_eur=None,
        )
        self.trades.append(rec)
        return rec

    def sell(
        self,
        symbol: str,
        qty: float,
        mid_price_eur: float,
    ) -> TradeRecord | None:
        if qty <= 0:
            return None
        prev = self.positions.get(symbol)
        if prev is None or prev.qty < qty - 1e-12:
            return None

        exec_px = apply_spread_to_price(mid_price_eur, "SELL", self.spread_bps)
        notional = qty * exec_px
        fee = compute_fee_eur(notional, percent_fee=self.percent_fee, min_fee_eur=self.min_fee_eur)
        proceeds = notional - fee

        cost_basis = qty * prev.avg_price_eur
        realized = proceeds - cost_basis
        self.realized_pnl_eur += realized

        self.cash_eur += proceeds
        new_qty = prev.qty - qty
        if new_qty <= 1e-12:
            del self.positions[symbol]
        else:
            self.positions[symbol] = Position(symbol, new_qty, prev.avg_price_eur)

        rec = TradeRecord(
            id=str(uuid4()),
            ts_utc=datetime.now(timezone.utc).isoformat(),
            agent=self.agent_name,
            symbol=symbol,
            side="SELL",
            qty=qty,
            price_eur=exec_px,
            fee_eur=fee,
            cash_after_eur=self.cash_eur,
            realized_pnl_eur=realized,
        )
        self.trades.append(rec)
        return rec
