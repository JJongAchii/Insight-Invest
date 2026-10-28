"""모형 공용 도구 — 학습창 안에서만 맞추는 변환."""

from __future__ import annotations

import numpy as np
import pandas as pd


class TrainPercentile:
    """학습창 분포 기준 백분위(0~1). 결측은 결측으로 남긴다.

    fit은 train의 비결측 값만 정렬해 둔다. transform은 각 값보다 작거나 같은 학습 값의 비율을 낸다 —
    시험 값끼리는 서로 영향을 주지 않는다.
    """

    def __init__(self, columns: list[str]):
        self.columns = list(columns)
        self.sorted_: dict[str, np.ndarray] = {}

    def fit(self, train: pd.DataFrame) -> TrainPercentile:
        for c in self.columns:
            values = train[c].to_numpy(dtype=float)
            self.sorted_[c] = np.sort(values[np.isfinite(values)])
        return self

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        out = pd.DataFrame(index=frame.index)
        for c in self.columns:
            ref = self.sorted_[c]
            x = frame[c].to_numpy(dtype=float)
            pct = np.full(x.shape, np.nan)
            ok = np.isfinite(x)
            if ref.size:
                pct[ok] = np.searchsorted(ref, x[ok], side="right") / ref.size
            out[c] = pct
        return out


class RecentPercentile(TrainPercentile):
    """학습창의 최근 n건 분포 기준 백분위(brief §10 축 1, n은 결과 전 집합에서).

    열마다 그 열 값이 있는 학습 사건을 상장일(같으면 event_id) 순으로 세워
    마지막 n건만 기준으로 쓴다.
    척도가 해마다 움직이는 항목(수요예측 경쟁률 등)을 최근 분포로 읽기 위한 변환이다.
    학습창 밖 값은 기준에 들어가지 않고, 시험 값끼리는 서로 영향을 주지 않는다.
    """

    def __init__(self, columns: list[str], n: int):
        super().__init__(columns)
        if int(n) < 1:
            raise ValueError(f"최근 건수 n은 1 이상이어야 한다: {n}")
        self.n = int(n)

    def fit(self, train: pd.DataFrame) -> RecentPercentile:
        ordered = train.sort_values(["listing_date", "event_id"], kind="mergesort")
        for c in self.columns:
            values = ordered[c].to_numpy(dtype=float)
            values = values[np.isfinite(values)][-self.n :]
            self.sorted_[c] = np.sort(values)
        return self


def make_percentile(kind: str, columns: list[str], recent_n: int | None) -> TrainPercentile:
    """'train'(학습창 전체) 또는 'recent'(최근 n건) 백분위 변환기."""
    if kind == "train":
        return TrainPercentile(columns)
    if kind == "recent":
        if recent_n is None:
            raise ValueError("percentile='recent'에는 recent_n이 필요하다")
        return RecentPercentile(columns, recent_n)
    raise ValueError(f"백분위 종류를 모른다: {kind!r}")
