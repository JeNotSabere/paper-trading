"""Mean reversion: z-score vs rolling mean."""

from __future__ import annotations

import random
import statistics

from paper_agent.broker.paper import PaperBroker
from paper_agent.learning.adaptive import AdaptiveLearner
from paper_agent.strategies.base import Action
from paper_agent.strategies.history import RollingPrices


class MeanReversionStrategy:
    name = "mean_reversion"
    window = 20
    trade_frac = 0.12

    def decide(
        self,
        broker: PaperBroker,
        prices: dict[str, float],
        history: RollingPrices,
        learner: AdaptiveLearner,
    ) -> Action:
        scale = learner.confidence_scale()
        z_thresh = 1.15 / max(0.5, scale)

        candidates: list[tuple[str, float]] = []
        for sym, px in prices.items():
            s = history.series(sym)
            if len(s) < self.window:
                continue
            window = s[-self.window :]
            mu = statistics.fmean(window)
            sd = statistics.pstdev(window) or 1e-9
            z = (px - mu) / sd
            candidates.append((sym, z))

        if not candidates:
            sym = random.choice(list(prices.keys())) if prices else ""
            return Action(sym, "HOLD", 0.0)

        # Buy most oversold (low z), sell most overbought from holdings
        candidates.sort(key=lambda x: x[1])
        most_oversold, z_lo = candidates[0]
        most_overbought, z_hi = candidates[-1]

        if z_lo < -z_thresh:
            return Action(most_oversold, "BUY", min(1.0, abs(z_lo) / 3 * scale))

        pos_syms = list(broker.positions.keys())
        if pos_syms:
            best_hold = max((c for c in candidates if c[0] in pos_syms), key=lambda x: x[1], default=None)
            if best_hold and best_hold[1] > z_thresh:
                return Action(best_hold[0], "SELL", min(1.0, abs(best_hold[1]) / 3 * scale))

        return Action(most_oversold, "HOLD", 0.0)
