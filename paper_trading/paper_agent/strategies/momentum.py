"""Momentum: ROC vs lookback; strength scaled by learner."""

from __future__ import annotations

import random

from paper_agent.broker.paper import PaperBroker
from paper_agent.learning.adaptive import AdaptiveLearner
from paper_agent.strategies.base import Action
from paper_agent.strategies.history import RollingPrices


class MomentumStrategy:
    name = "momentum"
    lookback = 12
    trade_frac = 0.12

    def decide(
        self,
        broker: PaperBroker,
        prices: dict[str, float],
        history: RollingPrices,
        learner: AdaptiveLearner,
    ) -> Action:
        if not prices:
            return Action("", "HOLD", 0.0)
        symbols = [s for s in broker.positions] or list(prices.keys())
        if not symbols:
            return Action(next(iter(prices)), "HOLD", 0.0)

        best_sym = symbols[0]
        best_score = -1e9
        for sym in prices:
            s = history.series(sym)
            if len(s) < self.lookback + 1:
                continue
            roc = (s[-1] - s[-self.lookback - 1]) / (abs(s[-self.lookback - 1]) + 1e-9)
            if roc > best_score:
                best_score = roc
                best_sym = sym

        scale = learner.confidence_scale()
        thresh = 0.0012 * scale
        if best_score > thresh and best_sym in prices:
            return Action(best_sym, "BUY", min(1.0, abs(best_score) * 80 * scale))

        # Sell weakest momentum held
        worst_sym = None
        worst = 1e9
        for sym in list(broker.positions.keys()):
            s = history.series(sym)
            if len(s) < self.lookback + 1:
                continue
            roc = (s[-1] - s[-self.lookback - 1]) / (abs(s[-self.lookback - 1]) + 1e-9)
            if roc < worst:
                worst = roc
                worst_sym = sym

        if worst_sym and worst < -thresh:
            return Action(worst_sym, "SELL", min(1.0, abs(worst) * 80 * scale))

        return Action(best_sym, "HOLD", 0.0)
