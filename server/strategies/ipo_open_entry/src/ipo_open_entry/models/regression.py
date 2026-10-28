"""부호 제약 회귀 (brief §10 축 2 둘째 계열, 부호는 §11 무조건 표).

청산마다 실현 로그 성장(`blocks.growth_cap_by_h`, 체제 상한가 지정가 주문) 또는 그
순위를 블록 값에 회귀한다. 블록 계수는 가설 방향 또는 0으로 묶고(`linear.Design`),
시장 통제는 부호 자유다. R2 계수는 R1 쪽으로 사전 강도 k건만큼 수축한다
(`linear.partial_pool`). 세 청산 예측의 평균이 사건의 기대 성장이다.

결정 형태
- "growth"(형태 c): 기대 성장 > 0이면 산다(순위 라벨에서는 쓰지 않는다 — 순위는 0 기준이 없다)
- "top"(형태 a): 학습창 예측의 상위 q(격자에서 학습창 실현 성장 합이 가장 큰 q)의 문턱 이상을 산다
지정가는 체제 상한가다. `entry_cap`을 주면 고른 사건만 그 배수×공모가 지정가로 낸다(형태 b의
상수 진입 상한 — 체제 상한 배수보다 크면 엔진이 상한가로 자른다).
`label_order`는 학습 라벨과 q 선택의 실현 성장을 어느 주문으로 재는지다: "cap"(체제 상한가 주문,
기본) 또는 "limit"(진입 상한 L 주문의 시가 체결 근사, `blocks.growth_limit_by_h` — entry_cap 필요).
모든 설계값은 `--strategy-args`로 받는다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ipo_open_entry.config import load_config
from ipo_open_entry.models import blocks as B
from ipo_open_entry.models import linear as L
from ipo_open_entry.models.common import make_percentile

LABELS = ("growth", "rank")


class SignedRegression:
    def __init__(
        self,
        decision: str,
        blocks: list[str],
        percentile: str,
        shrinkage: float | str,
        missing_indicators: bool,
        label: str,
        recent_n: int | None = None,
        top_grid: list[float] | None = None,
        entry_cap: float | None = None,
        label_order: str = "cap",
    ):
        if decision not in ("growth", "top"):
            raise ValueError(f"결정 형태를 모른다: {decision!r}")
        if label not in LABELS:
            raise ValueError(f"라벨을 모른다: {label!r}")
        if decision == "growth" and label == "rank":
            raise ValueError("순위 라벨에는 기대 성장 > 0 규칙을 쓸 수 없다")
        if decision == "top" and not top_grid:
            raise ValueError("decision='top'에는 top_grid가 필요하다")
        unknown = [b for b in blocks if b not in B.BLOCKS]
        if unknown or not blocks:
            raise ValueError(f"블록을 모른다: {unknown or blocks}")
        self.decision = decision
        self.blocks = tuple(blocks)
        self.percentile = percentile
        self.recent_n = recent_n
        self.shrinkage = shrinkage
        self.missing_indicators = bool(missing_indicators)
        self.label = label
        self.top_grid = tuple(float(q) for q in (top_grid or ()))
        if entry_cap is not None and not float(entry_cap) > 0:
            raise ValueError(f"진입 상한 배수는 양수여야 한다: {entry_cap}")
        self.entry_cap = None if entry_cap is None else float(entry_cap)
        if label_order not in ("cap", "limit"):
            raise ValueError(f"라벨 주문을 모른다: {label_order!r}")
        if label_order == "limit" and self.entry_cap is None:
            raise ValueError("label_order='limit'에는 entry_cap이 필요하다")
        self.label_order = label_order
        self.columns = [*B.feature_columns(self.blocks), L.CONTROL]
        self.designs = {
            h: L.Design(self.blocks, B.UNCONDITIONAL, h, True, self.missing_indicators)
            for h in B.HORIZONS
        }
        self.config = load_config()
        self.name = (
            f"SignedRegression-{decision}-{label}-k{shrinkage}"
            + (f"-L{self.entry_cap:g}" if self.entry_cap is not None else "")
            + ("-limitlabel" if label_order == "limit" else "")
        )

    def _predict(self, frame: pd.DataFrame) -> np.ndarray:
        pct = self.ref_.transform(frame)
        regimes = frame["regime"].to_numpy()
        preds = [
            L.predict(self.designs[h].matrix(pct, regimes), regimes, self.coefs_[h])
            for h in B.HORIZONS
        ]
        return np.mean(preds, axis=0)

    def fit(self, train: pd.DataFrame) -> None:
        self.ref_ = make_percentile(self.percentile, self.columns, self.recent_n).fit(train)
        pct = self.ref_.transform(train)
        regimes = train["regime"].to_numpy()
        if self.label_order == "limit":
            growth = B.growth_limit_by_h(train, self.entry_cap, self.config)
        else:
            growth = B.growth_cap_by_h(train, self.config)
        self.coefs_ = {}
        for h in B.HORIZONS:
            y = growth[f"g{h}"].to_numpy()
            ok = np.isfinite(y)  # 실데이터 라벨은 늘 유한하다 — 교란 검사 같은 비정상 입력 방어
            if self.label == "rank":
                y = pd.Series(np.where(ok, y, np.nan)).rank(pct=True).to_numpy() - 0.5
            design = self.designs[h]
            z = design.matrix(pct, regimes)
            self.coefs_[h] = L.partial_pool(z[ok], y[ok], regimes[ok], design, self.shrinkage)
        if self.decision == "top":
            s = self._predict(train)
            realized = growth.mean(axis=1).to_numpy()
            best_total, self.threshold_, self.q_ = -np.inf, np.inf, None
            for q in self.top_grid:
                tau = float(np.quantile(s, 1 - q)) if len(s) else np.inf
                total = float(realized[s >= tau].sum())
                if total > best_total:
                    best_total, self.threshold_, self.q_ = total, tau, q

    def decide(self, test: pd.DataFrame) -> pd.DataFrame:
        s = self._predict(test)
        buy = s > 0 if self.decision == "growth" else s >= self.threshold_
        mult = np.nan if self.entry_cap is None else np.where(buy, self.entry_cap, np.nan)
        return pd.DataFrame(
            {"event_id": test["event_id"].to_numpy(), "buy": buy.astype(bool), "limit_mult": mult}
        )
