"""Hybrid: combines momentum + mean-reversion signals; weights adapted online."""

from __future__ import annotations

import statistics

from paper_agent.broker.paper import PaperBroker
from paper_agent.learning.adaptive import AdaptiveLearner
from paper_agent.strategies.base import Action
from paper_agent.strategies.history import RollingPrices


class HybridStrategy:
    name = "hybrid"
    mom_lookback = 10
    mr_window = 18

    def _roc_z(
        self,
        sym: str,
        prices: dict[str, float],
        history: RollingPrices,
    ) -> tuple[float, float]:
        px = prices[sym]
        s = history.series(sym)
        roc = 0.0
        z = 0.0
        if len(s) >= self.mom_lookback + 1:
            roc = (s[-1] - s[-self.mom_lookback - 1]) / (abs(s[-self.mom_lookback - 1]) + 1e-9)
        if len(s) >= self.mr_window:
            window = s[-self.mr_window :]
            mu = statistics.fmean(window)
            sd = statistics.pstdev(window) or 1e-9
            z = (px - mu) / sd
        return roc, z

    def decide(
        self,
        broker: PaperBroker,
        prices: dict[str, float],
        history: RollingPrices,
        learner: AdaptiveLearner,
    ) -> Action:
        wm, wr = learner.hybrid_weights()
        scale = learner.confidence_scale()

        best: tuple[str, float, str] | None = None
        for sym, px in prices.items():
            s = history.series(sym)
            if len(s) < max(self.mom_lookback + 1, self.mr_window):
                continue
            roc = (s[-1] - s[-self.mom_lookback - 1]) / (abs(s[-self.mom_lookback - 1]) + 1e-9)
            window = s[-self.mr_window :]
            mu = statistics.fmean(window)
            sd = statistics.pstdev(window) or 1e-9
            z = (px - mu) / sd
            score = wm * roc - wr * z
            if best is None or score > best[1]:
                best = (sym, score, "BUY" if score > 0.002 * scale else "HOLD")

        if best is None:
            sym = next(iter(prices), "")
            return Action(sym, "HOLD", 0.0)

        sym, score, _ = best
        buy_thresh = 0.0018 * scale
        sell_thresh = -0.0018 * scale

        if score > buy_thresh:
            roc, z = self._roc_z(sym, prices, history)
            prob = learner.hybrid_success_probability(roc, z)
            meta = {"mom_roc": roc, "mr_z": z}
            if prob is not None:
                meta["clf_p_win"] = prob
            return Action(sym, "BUY", min(1.0, abs(score) * 60 * scale), meta=meta)

        worst: tuple[str, float] | None = None
        for pos_sym in broker.positions:
            if pos_sym not in prices:
                continue
            s = history.series(pos_sym)
            if len(s) < max(self.mom_lookback + 1, self.mr_window):
                continue
            roc = (s[-1] - s[-self.mom_lookback - 1]) / (abs(s[-self.mom_lookback - 1]) + 1e-9)
            window = s[-self.mr_window :]
            mu = statistics.fmean(window)
            sd = statistics.pstdev(window) or 1e-9
            z = (prices[pos_sym] - mu) / sd
            sc = wm * roc - wr * z
            if worst is None or sc < worst[1]:
                worst = (pos_sym, sc)

        if worst and worst[1] < sell_thresh:
            ws = worst[0]
            roc, z = self._roc_z(ws, prices, history)
            return Action(
                ws,
                "SELL",
                min(1.0, abs(worst[1]) * 60 * scale),
                meta={"mom_roc": roc, "mr_z": z},
            )

        return Action(sym, "HOLD", 0.0)
