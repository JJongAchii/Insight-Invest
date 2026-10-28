"""가설 블록·부호 표(brief §11)와 학습 라벨(brief §10 축 5) — 결과를 보기 전에 고정한 정의.

부호 표는 brief §11을 그대로 옮긴다. +1/−1은 '값이 클수록 시가 이후 순수익이
높다/낮다', 0은 '영향 없음' 또는 '그 체제에 값이 없음', None은 '자유(결과 전에
부호를 고정하지 않음)'다. 부호 고정 점수는 0과 None인 블록을 쓰지 않는다.
회귀는 None인 블록에 부호 제약을 걸지 않는다.

- 무조건 표(UNCONDITIONAL): 시가 배수를 모르는 결정(형태 a·c)
- 시가 배수 조건부 표(M_CONDITIONAL): 시가 배수 m을 함께 조건으로 두는 진입 상한형(형태 b)
- H4(개인 수요)는 청산별로 부호가 다르다: 1일째 +, 2·3일째 −
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ipo_open_entry import rules

HORIZONS = (1, 2, 3)

#: 블록 → 피처 열. '{h}'는 청산 번호로 바뀐다(H7은 같은 청산의 직전 실현 순수익).
BLOCKS: dict[str, tuple[str, ...]] = {
    "H1": ("h1_unlocked_inst",),
    "H1p": ("h1p_float_ratio",),
    "H2": ("h2_lockup_bid", "h2_lockup_alloc"),
    "H3": ("h3_bookbuild_ratio", "h3_bid_top"),
    "H4": ("h4_retail_comp", "h4_refund"),
    "H5": ("h5_price_vs_top",),
    "H6": ("h6_secondary",),
    "H7": ("h7_prior_drift_h{h}",),
    "H8": ("h8_log_offer_amount", "h8_log_float_value"),
    "H9": ("h9_longterm",),
    # brief-day1 §9 — 상장일 시가를 아는 결정의 블록
    "D1": ("d1_gap",),
    "D2a": ("d2a_refund_open",),
    "D2b": ("d2b_ipo_flow_open",),
    "D2c": ("d2c_market_heat",),
    "D3": ("d3_sector_mom",),
    "M": ("m_log_open",),
}
#: 1차 brief의 블록(H1~H9). day1 블록은 넣지 않는다 — 1차 모형의 '블록 전부'가 바뀌지 않게
ALL_BLOCKS = ("H1", "H1p", "H2", "H3", "H4", "H5", "H6", "H7", "H8", "H9")
DAY1_BLOCKS = ("D1", "D2a", "D2b", "D2c", "D3", "M")

_H4 = (1, -1, -1)
#: 블록 → 체제 → 부호(정수 또는 청산별 튜플). brief §11 R1·R2 열
UNCONDITIONAL: dict[str, dict[str, object]] = {
    "H1": {"R1": -1, "R2": -1},
    "H1p": {"R1": -1, "R2": -1},
    "H2": {"R1": 1, "R2": 1},
    "H3": {"R1": 1, "R2": 0},
    "H4": {"R1": _H4, "R2": _H4},
    "H5": {"R1": -1, "R2": -1},
    "H6": {"R1": -1, "R2": -1},
    "H7": {"R1": 1, "R2": 1},
    "H8": {"R1": 1, "R2": 1},
    "H9": {"R1": 0, "R2": 1},  # R1은 '값 없음'(brief §11)
}
#: brief §11 'm 조건부' 열. H1′은 자유, H3·H5는 0. H9는 R2 전용 항목이라 R1은 0
M_CONDITIONAL: dict[str, dict[str, object]] = {
    "H1": {"R1": -1, "R2": -1},
    "H1p": {"R1": None, "R2": None},
    "H2": {"R1": 1, "R2": 1},
    "H3": {"R1": 0, "R2": 0},
    "H4": {"R1": _H4, "R2": _H4},
    "H5": {"R1": 0, "R2": 0},
    "H6": {"R1": -1, "R2": -1},
    "H7": {"R1": 1, "R2": 1},
    "H8": {"R1": 1, "R2": 1},
    "H9": {"R1": 0, "R2": 1},
}
#: brief-day1 §9: 1차 블록은 m 조건부 열, D1 −, D2a~c·D3 +, M(시가 배수)은 자유
DAY1: dict[str, dict[str, object]] = {
    **M_CONDITIONAL,
    "D1": {"R1": -1, "R2": -1},
    "D2a": {"R1": 1, "R2": 1},
    "D2b": {"R1": 1, "R2": 1},
    "D2c": {"R1": 1, "R2": 1},
    "D3": {"R1": 1, "R2": 1},
    "M": {"R1": None, "R2": None},
}
TABLES = {"unconditional": UNCONDITIONAL, "m_conditional": M_CONDITIONAL, "day1": DAY1}


def sign(table: dict, block: str, regime: str, horizon: int) -> int | None:
    """그 체제·청산에서 블록의 부호(+1/−1/0, 자유는 None)."""
    s = table[block][regime]
    if isinstance(s, tuple):
        return s[HORIZONS.index(horizon)]
    return s


def block_columns(block: str, horizon: int) -> list[str]:
    return [c.format(h=horizon) for c in BLOCKS[block]]


def feature_columns(blocks: tuple[str, ...]) -> list[str]:
    """블록들이 쓰는 피처 열(세 청산 합집합, 순서 고정)."""
    out: list[str] = []
    for b in blocks:
        for h in HORIZONS:
            for c in block_columns(b, h):
                if c not in out:
                    out.append(c)
    return out


def block_values(pct: pd.DataFrame, blocks: tuple[str, ...], horizon: int) -> pd.DataFrame:
    """백분위 프레임 → 블록 값(블록 안의 비결측 백분위 평균, 모두 결측이면 결측). 행별 계산."""
    return pd.DataFrame(
        {b: pct[block_columns(b, horizon)].mean(axis=1, skipna=True) for b in blocks},
        index=pct.index,
    )


def block_score(
    pct: pd.DataFrame, regimes: pd.Series, blocks: tuple[str, ...], table: dict
) -> pd.Series:
    """부호 고정 블록 점수.

    청산별로 (부호 × (블록 값 − 0.5))를 쓸 수 있는 블록끼리 같은 무게로 평균하고,
    세 청산 점수를 평균한다. 쓸 블록이 하나도 없으면 그 청산 점수는 0(중립)이다.
    행별 계산이라 다른 사건의 값이 섞이지 않는다.
    """
    regimes = pd.Series(np.asarray(regimes), index=pct.index)
    per_h = []
    for h in HORIZONS:
        vals = block_values(pct, blocks, h)
        signs = pd.DataFrame(
            {b: regimes.map(lambda r, b=b, h=h: sign(table, b, r, h) or 0) for b in blocks},
            index=pct.index,
            dtype=float,
        )
        used = signs.ne(0) & vals.notna()
        n = used.sum(axis=1)
        total = (signs * (vals - 0.5)).where(used).sum(axis=1)
        per_h.append((total / n.where(n > 0)).fillna(0.0))
    return sum(per_h) / len(per_h)


def growth_cap_by_h(train: pd.DataFrame, config: dict) -> pd.DataFrame:
    """학습 라벨(brief §10 축 5): 체제 상한가 지정가(B1 주문)의 청산별 실현 로그 성장(g1~g3).

    g_h = log(1 + w·r_h / slots), r_h = B1 체결의 h일째 stress 순수익,
    w = 체결가/지정가(지정가만큼 현금이 묶이므로 실제 투입 비율 — 시가 체결이면
    m/상한 배수, 상한 도달 체결이면 1). 미체결은 0. 학습 사건의 라벨 열만 쓰는 행별 계산이다.
    """
    slots = float(config["sizing"]["slots"])
    cap = train["regime"].map(lambda r: rules.cap_multiple(r, config)).to_numpy(dtype=float)
    m = train["m"].to_numpy(dtype=float)
    at_cap = train["at_cap"].astype(bool).to_numpy()
    w = np.where(at_cap, 1.0, np.minimum(m / cap, 1.0))
    filled = train["b1_filled"].astype(bool).to_numpy()
    out = {}
    for h in HORIZONS:
        net = train[f"b1_net_h{h}"].to_numpy(dtype=float)
        ok = filled & np.isfinite(net) & np.isfinite(w)
        out[f"g{h}"] = np.where(ok, np.log1p(np.where(ok, w * net, 0.0) / slots), 0.0)
    return pd.DataFrame(out, index=train.index)


def growth_cap(train: pd.DataFrame, config: dict) -> pd.Series:
    """`growth_cap_by_h`의 세 청산 평균."""
    return growth_cap_by_h(train, config).mean(axis=1).rename("growth_cap")


def growth_limit_by_h(train: pd.DataFrame, limit_mult: float, config: dict) -> pd.DataFrame:
    """학습 라벨: 진입 상한 L×공모가 지정가 주문의 청산별 실현 로그 성장(시가 체결 근사).

    지정가 배수는 체제 상한 배수 이하로 자른다(L_r = min(L, 상한)). 시가 배수 m < L_r이면
    시가에 체결되어 투입 비율 m/L_r로 h일째 시가 진입 stress 순수익 r_h를 얻는다:
    g_h = log(1 + (m/L_r)·r_h/slots). 그 밖은 0 — 장중에 지정가 아래로 내려가 체결되는 경우는
    학습 표본에 상장일 저가가 없어 근사에서 뺀다(엔진은 실제로 체결한다).
    학습 사건의 라벨 열만 쓰는 행별 계산이다.
    """
    slots = float(config["sizing"]["slots"])
    cap = train["regime"].map(lambda r: rules.cap_multiple(r, config)).to_numpy(dtype=float)
    lim = np.minimum(float(limit_mult), cap)
    m = train["m"].to_numpy(dtype=float)
    fill = np.isfinite(m) & (m > 0) & (m < lim)
    w = np.where(fill, m / lim, 0.0)
    out = {}
    for h in HORIZONS:
        net = train[f"net_open_h{h}"].to_numpy(dtype=float)
        ok = fill & np.isfinite(net)
        out[f"g{h}"] = np.where(ok, np.log1p(np.where(ok, w * net, 0.0) / slots), 0.0)
    return pd.DataFrame(out, index=train.index)


def growth_open(train: pd.DataFrame, config: dict) -> pd.DataFrame:
    """시가 전량 진입의 청산별 로그 성장 log(1 + r_h/slots), r_h = 시가 진입 stress 순수익.

    진입 상한형(형태 b)의 조건부 모형이 시가 배수와 함께 학습하는 라벨이다
    (체결 판정 전 값).
    """
    slots = float(config["sizing"]["slots"])
    return pd.DataFrame(
        {
            f"g{h}": np.log1p(train[f"net_open_h{h}"].to_numpy(dtype=float) / slots)
            for h in HORIZONS
        },
        index=train.index,
    )
