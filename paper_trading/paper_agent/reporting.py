"""Performance summaries for Discord."""

from __future__ import annotations

from paper_agent.broker.paper import PaperBroker


def build_agent_report(
    broker: PaperBroker,
    prices: dict[str, float],
    initial_eur: float,
) -> str:
    eq = broker.equity_eur(prices)
    total_pnl = eq - initial_eur
    sells = [t for t in broker.trades if t.realized_pnl_eur is not None]
    wins = [t for t in sells if (t.realized_pnl_eur or 0) > 0]
    win_rate = (len(wins) / len(sells)) if sells else 0.0
    best = max((t.realized_pnl_eur for t in sells), default=None)
    worst = min((t.realized_pnl_eur for t in sells), default=None)

    lines = [
        f"**{broker.agent_name}**",
        f"Equity: **{eq:.2f} €** (start {initial_eur:.2f} €)",
        f"Total P/L: **{total_pnl:+.2f} €**",
        f"Realized (closed): **{broker.realized_pnl_eur:+.2f} €**",
        f"Win rate: **{win_rate*100:.1f}%** ({len(wins)}/{len(sells)} closed sells)",
    ]
    if best is not None:
        lines.append(f"Best trade: **{best:+.2f} €**")
    if worst is not None:
        lines.append(f"Worst trade: **{worst:+.2f} €**")
    if broker.positions:
        lines.append("**Open positions:**")
        for sym, pos in broker.positions.items():
            px = prices.get(sym)
            if px is None:
                lines.append(f"  • {sym}: {pos.qty:.6f} @ avg {pos.avg_price_eur:.4f} (no price)")
            else:
                mtm = pos.qty * px
                lines.append(
                    f"  • {sym}: {pos.qty:.6f} @ avg {pos.avg_price_eur:.4f} → ~{mtm:.2f} € @ {px:.4f}",
                )
    else:
        lines.append("**Open positions:** none")
    return "\n".join(lines)


def build_leaderboard(
    bundles: list[tuple[str, PaperBroker, float]],
    prices: dict[str, float],
) -> str:
    rows: list[tuple[str, float]] = []
    for _slug, broker, initial in bundles:
        eq = broker.equity_eur(prices)
        pnl = eq - initial
        rows.append((broker.agent_name, pnl))
    rows.sort(key=lambda x: x[1], reverse=True)
    out = ["**12h leaderboard** (by total P/L vs start)", ""]
    for i, (name, pnl) in enumerate(rows, 1):
        out.append(f"{i}. {name}: **{pnl:+.2f} €**")
    return "\n".join(out)
