"""부호 제약 선형 적합과 R1→R2 부분 풀링 (brief §10 축 2·4).

설계 행렬은 블록 값(학습창 백분위의 블록 평균 − 0.5, 결측은 0 = 중립)에 부호를
곱한 열과 시장 통제 열(부호 자유)로 만든다. 블록별 결측 지시 열(부호 자유)은 인자로
켠다. 부호가 정해진 블록의 계수는 0 이상으로 묶는다(부호를 이미 곱했으므로 '가설 방향
또는 0'). 부호가 0인 체제의 행에서는 그 블록 열이 0이라 그 체제에 영향이 없다 —
H3은 R1에서만, H9는 R2에서만 작동한다(H3만의 체제 상호작용).

부분 풀링: R1 행으로 θ_R1을 맞추고, R2 계수는 사전 강도 k건의 가상 R2 사건만큼
θ_R1 쪽으로 끌어당긴 능선 수축으로 맞춘다(SEARCH 사전등록 r1ShrinkageDefinition).
R2 학습 사건이 없으면 θ_R2 = θ_R1이다. k='full-pooling'이면 체제 절편만 따로 두고
계수를 공유한다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import lsq_linear

from ipo_open_entry.models import blocks as B

CONTROL = "ctrl_market_mom"
REGIMES = ("R1", "R2")
#: 수치 안정화(설계값이 아니다): 사전 없는 적합에 절편을 뺀 계수마다 √(ε·n) 크기의 0 표적 가상 행을
#: 붙인다. 설계 행렬이 계수 순위 부족(0인 지시변수 열, 절편과 겹치는 열)일 때 경계 있는 최소제곱이
#: 영공간 방향으로 발산하지 않고 최소 노름 쪽 해를 고르게 한다. 잘 정의된 적합은 소수 넷째 자리까지
#: 같다(SEARCH 기술 시도 X1·X2)
RIDGE_EPS = 1e-6


def _numeric(s: int | None) -> float:
    """부호 자유(None)는 1(부호를 곱하지 않음), 0은 0."""
    return 1.0 if s is None else float(s)


class Design:
    """블록 회귀 설계 — 열 이름·경계와 (백분위 프레임, 체제) → 행렬. 행별 계산이다.

    table=None이면 모든 블록의 부호가 자유다(시가 배수 예측처럼 가설 부호가 없는 적합).
    """

    def __init__(
        self,
        blocks: tuple[str, ...],
        table: dict | None,
        horizon: int,
        control: bool,
        missing_indicators: bool,
    ):
        self.blocks = tuple(blocks)
        self.table = table
        self.horizon = horizon
        self.control = control
        self.missing_indicators = missing_indicators
        names, lower = ["const"], [-np.inf]
        for b in self.blocks:
            free = table is None or all(B.sign(table, b, r, horizon) is None for r in REGIMES)
            names.append(f"blk:{b}")
            lower.append(-np.inf if free else 0.0)
        if missing_indicators:
            for b in self.blocks:
                names.append(f"miss:{b}")
                lower.append(-np.inf)
        if control:
            names.append(f"ctrl:{CONTROL}")
            lower.append(-np.inf)
        self.names = names
        self.lower = np.array(lower, dtype=float)
        self.upper = np.full(len(names), np.inf)

    def matrix(self, pct: pd.DataFrame, regimes) -> np.ndarray:
        regimes = np.asarray(regimes)
        vals = B.block_values(pct, self.blocks, self.horizon)
        cols = [np.ones(len(pct))]
        for b in self.blocks:
            v = vals[b].to_numpy(dtype=float)
            centered = np.where(np.isfinite(v), v - 0.5, 0.0)
            if self.table is None:
                sign = np.ones(len(pct))
            else:
                sign = np.array(
                    [_numeric(B.sign(self.table, b, r, self.horizon)) for r in regimes], float
                )
            cols.append(sign * centered)
        if self.missing_indicators:
            for b in self.blocks:
                cols.append((~np.isfinite(vals[b].to_numpy(dtype=float))).astype(float))
        if self.control:
            c = pct[CONTROL].to_numpy(dtype=float)
            cols.append(np.where(np.isfinite(c), c - 0.5, 0.0))
        return np.column_stack(cols)


def fit_bounded(
    z: np.ndarray,
    y: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    prior: np.ndarray | None = None,
    prior_scale: np.ndarray | None = None,
) -> np.ndarray:
    """경계 있는 최소제곱.

    prior가 있으면 열마다 prior_scale 크기의 가상 관측 행을 덧붙여 prior 쪽으로 수축한다. prior가
    없으면 RIDGE_EPS 수치 안정화 행을 붙이고, 데이터가 전혀 정하지 못한 열(학습 행에서 모두 0)은
    0으로 둔다.
    """
    n_data = len(z)
    if n_data == 0 and prior is None:
        return np.zeros(len(lower))
    if prior is not None:
        z = np.vstack([z, np.diag(prior_scale)])
        y = np.concatenate([y, prior_scale * prior])
    else:
        ridge = np.full(z.shape[1], np.sqrt(RIDGE_EPS * n_data))
        ridge[0] = 0.0  # 절편은 수축하지 않는다
        z = np.vstack([z, np.diag(ridge)])
        y = np.concatenate([y, np.zeros(len(ridge))])
    theta = lsq_linear(z, y, bounds=(lower, upper), method="trf", lsq_solver="exact").x
    if prior is None:
        idle = ~np.any(z[:n_data] != 0, axis=0)
        theta = np.where(idle, np.clip(0.0, lower, upper), theta)
    return theta


def partial_pool(
    z: np.ndarray, y: np.ndarray, regimes, design: Design, shrinkage: float | str
) -> dict[str, np.ndarray]:
    """체제별 계수. R1 적합 → R2는 R1 쪽 능선 수축(k건). 'full-pooling'은 계수 공유 + 체제 절편."""
    regimes = np.asarray(regimes)
    r1, r2 = regimes == "R1", regimes == "R2"
    if shrinkage == "full-pooling":
        zz = np.hstack([z, r2.astype(float)[:, None]])
        theta = fit_bounded(
            zz, y, np.append(design.lower, -np.inf), np.append(design.upper, np.inf)
        )
        t1 = theta[:-1].copy()
        t2 = t1.copy()
        t2[0] += theta[-1]
        return {"R1": t1, "R2": t2}
    k = float(shrinkage)
    t1 = fit_bounded(z[r1], y[r1], design.lower, design.upper)
    if not r2.any():
        return {"R1": t1, "R2": t1.copy()}
    var = z.var(axis=0)
    var[0] = 1.0
    scale = np.sqrt(k * np.where(var > 0, var, 1.0))
    t2 = fit_bounded(z[r2], y[r2], design.lower, design.upper, prior=t1, prior_scale=scale)
    return {"R1": t1, "R2": t2}


def predict(z: np.ndarray, regimes, coefs: dict[str, np.ndarray]) -> np.ndarray:
    regimes = np.asarray(regimes)
    out = np.zeros(len(z))
    for r in REGIMES:
        mask = regimes == r
        if mask.any():
            out[mask] = z[mask] @ coefs[r]
    return out
