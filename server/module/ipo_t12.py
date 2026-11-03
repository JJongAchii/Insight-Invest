"""공모주 t12 운영 결정 (계약 ipo-live-ops v2, quant-lab recall-v1 t12).

t12는 recall-v1 개발 구간 탐색(과학 실행 12회, 누수 감사 pass)에서 보존한 최선이다. 개발 구간 후보이고 순방향
확증 전이다 — 2026-11-02 사용자가 확정 결정(순방향 기록으로만 확증)의 예외로 운영 전환을 골랐다.

결정 계산은 quant-lab `strategies/ipo-open-entry`의 recall 결정 경로 사본(`server/strategies/ipo_open_entry`,
`VENDOR.json`의 t12 절)이 한다. 결정 시점·대상·개발 뒤 사건·피처 한 행은 t01과 같은 `ipo_t01.prepare`가 만든다.

결정 순서는 recall-v1 walk-forward(`recall.models.walk_forward`)의 한 분기와 같다.
1. 학습 표: 개발 사건은 recall이 쓴 표(`signal.data.build_table` — 공모가 1.5배 당일 지정가·2일째 종가로 낸
   체결 상태 라벨 포함). 개발 구간 뒤 사건은 t01과 같은 표에 같은 함수(`signal.data.exact_labels`)로 라벨을 붙인다
2. 학습: 분기 시작 전에 상장하고 라벨(세 청산과 체결 상태)이 확정된 사건(`recall.data.mature_before`)
3. 결정: `recall.models.Model`(t12 변형) fit → decide(대상 한 행). 1차 점수(기관 반응)가 문턱 이상이면 매수,
   아니면 원래 t01이 패스한 사건 중 체결 상태 보완 점수가 보완 문턱 이상이면 매수
4. 주문(계약 v3, 2026-11-03부터): quant-lab entry-t12-v1 t06(`entry_t12.execution.limit_mults`, VENDOR.json의
   entry 절). 1차 매수 공모가 × 1.5, 보완 매수 공모가 × 1.25 호가 내림 지정가를 장전 동시호가에 내고, 시가에
   체결되지 않으면 9시 직후 취소한다(시가 단일가 전용). t12의 학습 라벨(1.5배 당일 지정가 체결 상태)은 그대로다
"""

from __future__ import annotations

import datetime as dt
import functools
import hashlib
import json
import math

import pandas as pd
import yaml

# ipo_t01을 먼저 불러야 결정 경로 사본(server/strategies/ipo_open_entry/src)이 sys.path에 들어간다
from module import ipo_t01

# isort: split
from ipo_open_entry.entry_t12 import execution as entry_execution
from ipo_open_entry.operate import decision
from ipo_open_entry.recall import data as recall_data
from ipo_open_entry.recall.complement import STATES
from ipo_open_entry.recall.models import Model
from ipo_open_entry.signal import data as signal_data

from module.ipo_t01 import NotEligible, NotReady, TooLate

SPEC = "recall-v1-t12"
STAGE = "개발 구간 후보 · 순방향 확증 전(2026-11-02 전환)"

ENTRY_SPEC = "entry-t12-v1-t06"
ENTRY_STAGE = "개발 구간 후보 · 순방향 확증 전(2026-11-03 전환)"

__all__ = [
    "NotEligible",
    "NotReady",
    "TooLate",
    "SPEC",
    "ENTRY_SPEC",
    "decide_listing",
    "entry_limit_mult",
    "entry_rule",
    "rule",
]


@functools.lru_cache(maxsize=1)
def vendor() -> dict:
    """t12 출처(quant-lab 산출 경로·trial 커밋·설정 digest·변형) — vendor 스크립트가 기록한다."""
    return json.loads((ipo_t01.LINE_DIR / "VENDOR.json").read_text())["t12"]


def rule() -> dict:
    v = vendor()
    return {
        "spec": SPEC,
        "stage": STAGE,
        "trial_commit": v["trial_commit"],
        "config_digest": v["config_digest"],
        "variant": v["variant"],
    }


@functools.lru_cache(maxsize=1)
def entry_vendor() -> dict:
    """진입 규칙 출처(quant-lab entry-t12-v1 t06 산출·trial 커밋·변형) — vendor 스크립트가 기록한다."""
    return json.loads((ipo_t01.LINE_DIR / "VENDOR.json").read_text())["entry"]


@functools.lru_cache(maxsize=1)
def entry_config() -> dict:
    return yaml.safe_load((ipo_t01.LINE_DIR / "config-entry-t12-v1.yaml").read_text())


def entry_rule() -> dict:
    """결정 기록에 남기는 진입 규칙(지정가 배수 규칙과 체결 방식)."""
    v = entry_vendor()
    return {
        "spec": ENTRY_SPEC,
        "stage": ENTRY_STAGE,
        "trial_commit": v["trial_commit"],
        "config_digest": v["config_digest"],
        "limit": v["variant"]["limit"],
        "fill": v["variant"]["fill"],
    }


def entry_limit_mult(made: dict, qs: pd.Timestamp) -> float | None:
    """t12 결정 한 행의 지정가 배수 — quant-lab `entry_t12.execution.limit_mults` 그대로(패스면 None).

    t06 규칙은 강한 확신 계단이 없어(strong = None) 그 행의 보완 매수 여부만 읽는다.
    """
    if not made["buy"]:
        return None
    row = pd.DataFrame(
        [
            {
                "event_id": "target",
                "quarter": qs,
                "buy": True,
                "additional_buy": bool(made["additional_buy"]),
                "score": float(made["score"]),
                "threshold": float(made["threshold"]),
            }
        ]
    )
    cfg = entry_config()
    mult = entry_execution.limit_mults(
        row, entry_vendor()["variant"]["limit"], cfg["limit_mults"], int(cfg["strong_min_history"])
    )
    return float(mult.iloc[0])


def make_model() -> Model:
    return Model(**vendor()["variant"])


@functools.lru_cache(maxsize=1)
def dev_table() -> pd.DataFrame:
    """recall이 쓴 개발 사건 표(t01 표 + 체결 상태 라벨·label_available)."""
    return signal_data.build_table(ipo_t01.dev_data(), ipo_t01.config())


def post_dev_table(
    dev: dict, post: dict, index_close: pd.Series, config: dict
) -> pd.DataFrame | None:
    """개발 구간 뒤 청산이 끝난 사건의 표에 체결 상태 라벨을 붙인다(`signal.data.build_table`과 같은 결합)."""
    base = decision.post_dev_table(dev, post, index_close, config)
    if base is None:
        return None
    done = post["events"]["event_id"].isin(base["event_id"])
    data = {
        "events": post["events"][done],
        "bars": post["bars"][post["bars"]["event_id"].isin(base["event_id"])],
    }
    exact = signal_data.exact_labels(data, config, signal_data.spec())
    table = base.set_index("event_id").join(exact, how="left", validate="one_to_one")
    table["label_available"] = table[
        ["exit_date_h1", "exit_date_h2", "exit_date_h3", "sig_available"]
    ].max(axis=1)
    return table.reset_index()


def training_table(dev_tab: pd.DataFrame, post_tab, qs: pd.Timestamp) -> pd.DataFrame:
    """분기 시작 전에 상장하고 라벨이 확정된 개발 사건과 개발 구간 뒤 사건."""
    parts = [dev_tab]
    if post_tab is not None and len(post_tab):
        parts.append(post_tab)
    t = pd.concat(parts, ignore_index=True)
    return recall_data.mature_before(t, qs).sort_values(["listing_date", "event_id"])


def _finite(v) -> float | None:
    v = float(v)
    return v if math.isfinite(v) else None


def decide(train: pd.DataFrame, row: pd.DataFrame, qs: pd.Timestamp) -> dict:
    """t12를 학습 표로 맞추고 대상 한 행의 결정과 근거를 낸다."""
    model = make_model().fit(train.copy(), qs)
    out = model.decide(row.copy())
    if len(out) != 1 or out["event_id"].iloc[0] != row["event_id"].iloc[0]:
        raise ValueError("결정이 대상 사건 한 행이 아니다")
    r = out.iloc[0]
    buy = bool(r["buy"])
    meta = model.meta
    return {
        "buy": buy,
        "limit_mult": float(r["limit_mult"]) if buy else None,
        "score": float(r["score"]),
        "threshold": float(r["threshold"]),
        "q": meta["q"],
        "primary_buy": bool(r["primary_buy"]),
        "baseline_buy": bool(r["baseline_buy"]),
        "additional_buy": bool(r["additional_buy"]),
        "supplement_active": bool(meta["supplement_active"]),
        "supplement_q": meta["supplement_q"],
        "supplement_score": float(r["supplement_score"]),
        "supplement_threshold": _finite(r["supplement_threshold"]),
        "fill_probability": {
            s: float(r[f"predicted_{s}_probability"])
            for s in STATES
            if f"predicted_{s}_probability" in out
        },
        "decision_reason": str(r["decision_reason"]),
        "train_events": int(len(train)),
        "train_sha256": hashlib.sha256("\n".join(sorted(train["event_id"])).encode()).hexdigest(),
    }


def decide_listing(
    api, event_id: str, listing_date, market: str, now: dt.datetime | None = None
) -> dict:
    """상장 예정 공모주 하나의 t12 결정. 결정할 수 없으면 NotReady·TooLate·NotEligible을 낸다."""
    ctx = ipo_t01.prepare(api, event_id, listing_date, market, now)
    cfg = ctx["cfg"]
    post_table = post_dev_table(ctx["dev"], ctx["post"], ctx["close"], cfg)
    train = training_table(dev_table(), post_table, ctx["qs"])
    made = decide(train, ctx["row"], ctx["qs"])
    order = decision.order(
        ctx["target"], {**made, "limit_mult": entry_limit_mult(made, ctx["qs"])}, cfg
    )
    return {
        **ipo_t01.record(ctx, SPEC, order, post_table),
        **{k: v for k, v in made.items() if k not in ("buy", "limit_mult")},
        "entry": entry_rule(),
    }
