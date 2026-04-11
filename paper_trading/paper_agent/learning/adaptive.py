"""Online adaptation: win-rate-based confidence + hybrid branch weights + incremental classifier."""

from __future__ import annotations

from collections import deque

import numpy as np
from sklearn.linear_model import SGDClassifier

from paper_agent.broker.paper import TradeRecord


class AdaptiveLearner:
    """
    - Confidence scales position aggressiveness from recent trade outcomes.
    - Hybrid maintains two weights (momentum vs mean-reversion) nudged by closed PnL.
    - A tiny SGDClassifier learns 'profitable vs not' from (roc, z) features on sells.
    """

    def __init__(self) -> None:
        self._pnl_binary: deque[float] = deque(maxlen=40)
        self._w_mom = 1.0
        self._w_rev = 1.0
        self._clf: SGDClassifier | None = SGDClassifier(
            loss="log_loss",
            average=True,
            random_state=42,
        )
        self._clf_fitted = False
        self._clf_buf_X: list[list[float]] = []
        self._clf_buf_y: list[int] = []

    def confidence_scale(self) -> float:
        if len(self._pnl_binary) < 6:
            return 1.0
        wr = sum(self._pnl_binary) / len(self._pnl_binary)
        # Map ~0.35–0.65 win rate into 0.88–1.12 multiplier
        return float(np.clip(0.88 + (wr - 0.35) * (0.24 / 0.30), 0.75, 1.25))

    def hybrid_weights(self) -> tuple[float, float]:
        s = self._w_mom + self._w_rev
        if s <= 0:
            return 0.5, 0.5
        return self._w_mom / s, self._w_rev / s

    def on_sell(
        self,
        trade: TradeRecord,
        *,
        strategy_name: str,
        meta: dict | None,
    ) -> None:
        pnl = trade.realized_pnl_eur
        if pnl is None:
            return
        self._pnl_binary.append(1.0 if pnl > 0 else 0.0)

        if strategy_name == "hybrid" and meta:
            roc = float(meta.get("mom_roc", 0.0))
            zed = float(meta.get("mr_z", 0.0))
            mom_part = abs(roc)
            rev_part = abs(zed)
            if pnl > 0:
                self._w_mom *= 1.0 + 0.04 * mom_part
                self._w_rev *= 1.0 + 0.04 * rev_part
            else:
                self._w_mom *= max(0.85, 1.0 - 0.03 * mom_part)
                self._w_rev *= max(0.85, 1.0 - 0.03 * rev_part)
            self._w_mom = float(np.clip(self._w_mom, 0.2, 3.0))
            self._w_rev = float(np.clip(self._w_rev, 0.2, 3.0))

            y = 1 if pnl > 0 else 0
            self._clf_buf_X.append([roc, zed])
            self._clf_buf_y.append(y)
            if len(self._clf_buf_X) >= 16:
                self._flush_clf()

    def _flush_clf(self) -> None:
        if not self._clf_buf_X or self._clf is None:
            return
        X = np.array(self._clf_buf_X, dtype=np.float64)
        y = np.array(self._clf_buf_y, dtype=np.int64)
        classes = np.array([0, 1])
        try:
            if not self._clf_fitted:
                self._clf.partial_fit(X, y, classes=classes)
                self._clf_fitted = True
            else:
                self._clf.partial_fit(X, y)
        except Exception:
            pass
        self._clf_buf_X.clear()
        self._clf_buf_y.clear()

    def hybrid_success_probability(self, mom_roc: float, mr_z: float) -> float | None:
        if self._clf is None or not self._clf_fitted:
            return None
        try:
            p = self._clf.predict_proba(np.array([[mom_roc, mr_z]], dtype=np.float64))[0, 1]
            return float(p)
        except Exception:
            return None
