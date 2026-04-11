"""Random baseline: stochastic noise for comparison."""

from __future__ import annotations

import random

from paper_agent.broker.paper import PaperBroker
from paper_agent.learning.adaptive import AdaptiveLearner
from paper_agent.strategies.base import Action
from paper_agent.strategies.history import RollingPrices


class RandomBaselineStrategy:
    name = "random"
    p_trade = 0.22

    def decide(
        self,
        broker: PaperBroker,
        prices: dict[str, float],
        history: RollingPrices,
        learner: AdaptiveLearner,
    ) -> Action:
        syms = list(prices.keys())
        if not syms:
            return Action("", "HOLD", 0.0)

        if random.random() > self.p_trade * learner.confidence_scale():
            return Action(random.choice(syms), "HOLD", 0.0)

        sym = random.choice(syms)
        has_pos = [s for s in syms if s in broker.positions and broker.positions[s].qty > 0]
        if has_pos and random.random() < 0.45:
            sym = random.choice(has_pos)
            return Action(sym, "SELL", random.uniform(0.25, 0.9))

        return Action(sym, "BUY", random.uniform(0.2, 0.85))
