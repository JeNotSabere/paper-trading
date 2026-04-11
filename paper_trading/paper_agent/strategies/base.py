"""Strategy interface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from paper_agent.broker.paper import PaperBroker
    from paper_agent.learning.adaptive import AdaptiveLearner
    from paper_agent.strategies.history import RollingPrices


@dataclass
class Action:
    symbol: str
    side: str  # BUY | SELL | HOLD
    strength: float  # 0..1 scales order size
    meta: dict | None = None  # optional: hybrid learning features


class Strategy(Protocol):
    name: str

    def decide(
        self,
        broker: PaperBroker,
        prices: dict[str, float],
        history: RollingPrices,
        learner: AdaptiveLearner,
    ) -> Action:
        ...
