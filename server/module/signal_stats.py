"""signal_study 조회 — 신호 성과를 '기준선 대비 몇 %p'로 환산한다.

median_excess를 그대로 읽으면 안 된다. 벤치마크가 유동성 유니버스 동일가중
횡단면 *평균*이고 수익률 분포가 우편향이라, 조건 없는 기준선조차 20일 중앙값이
-1.80%다. 신호가 좋은지 나쁜지는 오직 baseline 행과의 차이로만 판정된다.
이 모듈이 그 뺄셈을 하는 유일한 지점이다 — attention·텔레그램 브리핑 공용.
"""

import logging

import pandas as pd

from datastore import storage

logger = logging.getLogger(__name__)

_PARTS = ("insight", "signal_study.parquet")
BASELINE = "baseline"
_UNSET = object()  # "인자 미지정"과 "데이터 없음(None)"을 구분하기 위한 센티널


def load_study() -> pd.DataFrame | None:
    """signal_study.parquet 로드. 부재·손상 시 None (호출부는 실측치를 생략한다).

    신호 13종 × 지평선 3개 = 39행짜리 테이블이라 캐시하지 않는다 — Lambda
    컨테이너가 며칠 살아남아도 갱신된 값을 바로 읽는 쪽이 낫다.
    """
    try:
        return storage.read_parquet(*_PARTS)
    except Exception:
        logger.debug("signal_study 로드 실패", exc_info=True)
        return None


def _row(df: pd.DataFrame, signal_type: str, horizon: int) -> pd.Series | None:
    hit = df[(df["signal_type"] == signal_type) & (df["horizon"] == horizon)]
    return hit.iloc[0] if len(hit) else None


def excess_vs_baseline(
    df: pd.DataFrame, signal_type: str, horizon: int
) -> tuple[int, float, float] | None:
    """(n_events, 중앙값 초과수익 차이 %p, 승률 차이 %p). 비교 불가면 None.

    같은 지평선의 baseline 행하고만 뺀다 — 20일 신호를 60일 기준선에 대면
    벤치마크를 바꾼 의미가 없어진다.
    """
    sig = _row(df, signal_type, horizon)
    base = _row(df, BASELINE, horizon)
    if sig is None or base is None:
        return None
    med = float(sig["median_excess"]) - float(base["median_excess"])
    hit = float(sig["hit_rate"]) - float(base["hit_rate"])
    if pd.isna(med) or pd.isna(hit):  # 표본이 빈 신호 — 문장을 만들지 않는다
        return None
    return int(sig["n_events"]), med, hit


def format_evidence(n_events: int, median_delta: float, hit_delta: float, horizon: int) -> str:
    """'과거 27.6만건 · 20일 뒤 기준선 대비 -2.4%p (승률 -3.1%p)'."""
    n = f"{n_events / 10000:.1f}만건" if n_events >= 10000 else f"{n_events:,}건"
    return (
        f"과거 {n} · {horizon}일 뒤 기준선 대비 " f"{median_delta:+.1f}%p (승률 {hit_delta:+.1f}%p)"
    )


def evidence_phrase(
    signal_type: str, horizon: int = 20, df: pd.DataFrame | None = _UNSET
) -> str | None:
    """실측치 한 줄.

    df 인자는 세 가지 경우로 갈린다:
    - 아예 생략(센티널 유지): load_study()를 호출해 직접 로드한다.
    - 명시적으로 None을 전달: 호출부가 이미 load_study()를 시도했는데 결과가
      없었다는 뜻이다 — 다시 로드하지 않고 곧장 None을 반환한다. attention.py
      처럼 루프 밖에서 한 번만 로드해 넘기는 호출부에서, parquet 부재 시
      load_study()가 None을 돌려준 것과 "안 넘겼다"를 구분하지 못하면 매
      아이템마다 재로드해버려 캐싱이 무력화된다.
    - 실제 DataFrame을 전달: 그대로 사용한다.
    """
    if df is _UNSET:
        df = load_study()
    if df is None:
        return None
    stats = excess_vs_baseline(df, signal_type, horizon)
    return format_evidence(*stats, horizon) if stats else None
