"""Rolling price history built from periodic ticks (same feed for all agents)."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import DefaultDict


class RollingPrices:
    def __init__(self, maxlen: int = 120) -> None:
        self._d: DefaultDict[str, deque[float]] = defaultdict(lambda: deque(maxlen=maxlen))

    def push(self, prices: dict[str, float]) -> None:
        for sym, px in prices.items():
            if px and px == px:
                self._d[sym].append(float(px))

    def series(self, symbol: str) -> list[float]:
        return list(self._d.get(symbol, ()))
