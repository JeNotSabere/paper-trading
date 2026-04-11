"""Append-only CSV logs per agent."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from paper_agent.broker.paper import PaperBroker, TradeRecord


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def append_trade_csv(data_dir: Path, agent_slug: str, trade: TradeRecord) -> Path:
    path = data_dir / f"trades_{agent_slug}.csv"
    _ensure_parent(path)
    new_file = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(
                [
                    "id",
                    "ts_utc",
                    "agent",
                    "symbol",
                    "side",
                    "qty",
                    "price_eur",
                    "fee_eur",
                    "cash_after_eur",
                    "realized_pnl_eur",
                ]
            )
        w.writerow(
            [
                trade.id,
                trade.ts_utc,
                trade.agent,
                trade.symbol,
                trade.side,
                f"{trade.qty:.8f}",
                f"{trade.price_eur:.6f}",
                f"{trade.fee_eur:.4f}",
                f"{trade.cash_after_eur:.4f}",
                "" if trade.realized_pnl_eur is None else f"{trade.realized_pnl_eur:.4f}",
            ]
        )
    return path


def write_state_snapshot(
    data_dir: Path,
    agent_slug: str,
    broker: PaperBroker,
    equity_eur: float,
) -> Path:
    path = data_dir / f"snapshot_{agent_slug}.csv"
    _ensure_parent(path)
    new_file = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["ts_utc", "agent", "cash_eur", "equity_eur", "realized_pnl_eur", "positions_json"])
        pos = {k: {"qty": v.qty, "avg": v.avg_price_eur} for k, v in broker.positions.items()}
        w.writerow(
            [
                datetime.now(timezone.utc).isoformat(),
                broker.agent_name,
                f"{broker.cash_eur:.4f}",
                f"{equity_eur:.4f}",
                f"{broker.realized_pnl_eur:.4f}",
                json.dumps(pos),
            ]
        )
    return path


def aggregate_trades_path(data_dir: Path) -> Path:
    return data_dir / "trades_all_agents.csv"
