"""매크로 레짐 v2 — 성장(OECD CLI) × 물가(CPI YoY) 4국면 + 리스크 게이지 + 한국 매크로.

데이터는 qdata 레이크(QDATA_LAKE)에서 읽는다. 순수 계산 모듈 — FastAPI 의존 없음.
로드는 lru_cache로 프로세스 수명 동안 캐시 (Lambda 컨테이너 재사용 시 유지).
캐시된 원본 DataFrame/Series는 절대 in-place 수정하지 않는다.
"""

from functools import lru_cache

import pandas as pd

from qdata import api as qdata_api

PHASE_START = "1998-01"

# 국면 매핑: (growth_up, inflation_up) → phase
_PHASES = {
    (True, False): "Goldilocks",
    (True, True): "Reflation",
    (False, True): "Stagflation",
    (False, False): "Deflation",
}


# ── 캐시된 로드 ──────────────────────────────────────────────────────────────


@lru_cache(maxsize=4)
def _cli(country: str = "USA") -> pd.Series:
    return qdata_api.load_oecd_cli(country)


@lru_cache(maxsize=8)
def _fred(series: str) -> pd.Series:
    return qdata_api.load_fred([series])[series]


@lru_cache(maxsize=1)
def _cpi() -> pd.Series:
    """CPIAUCSL 월간 — RDS 아카이브(1947~) ∪ qdata 레이크(2006~, 일일 갱신).

    레이크 FRED START가 2006이라 1998~ 국면 산출엔 아카이브로 과거를 보강한다
    (routers/regime._macro_data와 같은 패턴). 같은 달은 최신 수집(qdata) 우선.
    아카이브가 없으면 레이크 단독으로 동작한다.
    """
    live = _fred("CPIAUCSL").dropna()
    try:
        from datastore import storage

        macro = storage.read_parquet("macro.parquet")
        ids = macro.loc[macro["fred"] == "CPIAUCSL", "macro_id"]
        arch = storage.read_parquet("macro_data.parquet")
        arch = arch[arch["macro_id"].isin(ids)]
        archive = pd.Series(
            arch["value"].to_numpy(), index=pd.to_datetime(arch["base_date"])
        ).dropna()
    except (FileNotFoundError, KeyError):
        return live
    s = pd.concat([archive, live])
    return s[~s.index.duplicated(keep="last")].sort_index()  # 같은 달은 live 우선


@lru_cache(maxsize=1)
def _hyg_ief() -> pd.DataFrame:
    return qdata_api.load_prices(["HYG", "IEF"], fields=("adj_close",))["adj_close"]


@lru_cache(maxsize=1)
def _ecos() -> pd.DataFrame:
    return qdata_api.load_ecos(
        ["base_rate", "ktb_3y", "ktb_10y", "usdkrw", "cpi"], start="2010-01-01"
    )


# ── 4국면 (성장 × 물가) ──────────────────────────────────────────────────────


def phase_history() -> pd.DataFrame:
    """월간 국면 히스토리 (1998-01~).

    컬럼: cli, cli_delta, cpi_yoy, cpi_yoy_delta, growth_up, inflation_up, phase.
    인덱스: 월간 Period. CLI는 참조월 다음 달 중순 발표라 인덱스를 1개월 앞으로
    시프트해 '알려진 시점' 기준으로 정렬한다 (look-ahead 방지).
    """
    cli = _cli("USA").copy()
    cli.index = pd.PeriodIndex(cli.index, freq="M") + 1  # 발표 시차 1개월
    cli_delta = cli.diff(3)

    cpi = _cpi()
    cpi = cpi.set_axis(pd.PeriodIndex(cpi.index, freq="M"))
    cpi_yoy = cpi.pct_change(12) * 100
    cpi_yoy_delta = cpi_yoy.diff(3)

    df = pd.DataFrame(
        {
            "cli": cli,
            "cli_delta": cli_delta,
            "cpi_yoy": cpi_yoy,
            "cpi_yoy_delta": cpi_yoy_delta,
        }
    ).dropna()
    df = df.loc[pd.Period(PHASE_START, freq="M") :]
    df["growth_up"] = df["cli_delta"] > 0
    df["inflation_up"] = df["cpi_yoy_delta"] > 0
    df["phase"] = [
        _PHASES[(g, i)] for g, i in zip(df["growth_up"], df["inflation_up"])
    ]
    return df


def current_phase() -> dict:
    row = phase_history().iloc[-1]
    return {
        "phase": row["phase"],
        "growth_dir": "up" if row["growth_up"] else "down",
        "inflation_dir": "up" if row["inflation_up"] else "down",
        "as_of": str(row.name),
        "cli": float(row["cli"]),
        "cli_delta": float(row["cli_delta"]),
        "cpi_yoy": float(row["cpi_yoy"]),
        "cpi_yoy_delta": float(row["cpi_yoy_delta"]),
    }


# ── 리스크 게이지 ────────────────────────────────────────────────────────────


def _percentile(series: pd.Series, value: float) -> float:
    """value의 히스토리 내 백분위 (0~100) — 전체 히스토리 기준."""
    s = series.dropna()
    return float((s < value).mean() * 100)


def risk_gauge() -> dict:
    """리스크오프 게이지 0~100 (높을수록 위험회피). 4개 지표 동일가중."""
    components = []

    # 1) 장단기 금리차 — 낮을수록(역전) 침체 신호
    curve = _fred("T10Y2Y").dropna()
    level = float(curve.iloc[-1])
    components.append(
        {
            "name": "Yield curve (10Y-2Y)",
            "value": level,
            "percentile": _percentile(curve, level),
            "score": 100 - _percentile(curve, level),
        }
    )

    # 2) 하이일드 상대강도 (HYG−IEF 126일 상대수익) — 낮을수록 크레딧 스트레스
    px = _hyg_ief().dropna()
    rel = (px["HYG"] / px["HYG"].shift(126) - 1) - (px["IEF"] / px["IEF"].shift(126) - 1)
    rel = rel.dropna()
    rel_latest = float(rel.iloc[-1])
    try:
        hy_value = float(_fred("BAMLH0A0HYM2").dropna().iloc[-1])  # 표시용 OAS 레벨
    except (KeyError, IndexError, FileNotFoundError):
        hy_value = rel_latest
    components.append(
        {
            "name": "HY spread (HYG-IEF)",
            "value": hy_value,
            "percentile": _percentile(rel, rel_latest),
            "score": 100 - _percentile(rel, rel_latest),
        }
    )

    # 3) VIX — 높을수록 위험
    vix = _fred("VIXCLS").dropna()
    vix_latest = float(vix.iloc[-1])
    components.append(
        {
            "name": "VIX",
            "value": vix_latest,
            "percentile": _percentile(vix, vix_latest),
            "score": _percentile(vix, vix_latest),
        }
    )

    # 4) 실업률 모멘텀 — 최근 12개월 저점 대비 상승폭 (Sahm 룰 근사)
    unrate = _fred("UNRATE").dropna()
    gap = unrate - unrate.rolling(12, min_periods=12).min()
    gap = gap.dropna()
    gap_latest = float(gap.iloc[-1])
    components.append(
        {
            "name": "Unemployment momentum",
            "value": gap_latest,
            "percentile": _percentile(gap, gap_latest),
            "score": _percentile(gap, gap_latest),
        }
    )

    for c in components:
        c["weight"] = 0.25
    score = sum(c["score"] * c["weight"] for c in components)
    as_of = max(curve.index.max(), px.index.max(), vix.index.max()).strftime("%Y-%m-%d")
    return {"score": score, "as_of": as_of, "components": components}


# ── 한국 매크로 ──────────────────────────────────────────────────────────────

_KR_NAMES = {
    "base_rate": "한은 기준금리 (%)",
    "ktb_3y": "국고채 3년 (%)",
    "ktb_10y": "국고채 10년 (%)",
    "usdkrw": "원/달러 환율",
    "cpi_yoy": "소비자물가 YoY (%)",
    "cli_kor": "OECD 경기선행지수 (한국)",
}


def _series_payload(s: pd.Series, date_fmt: str = "%Y-%m-%d") -> list[dict]:
    return [{"date": d.strftime(date_fmt), "value": float(v)} for d, v in s.items()]


def kr_macro() -> dict:
    """한국 매크로 대시보드 시계열 (2010~). 일간은 주간(금요일) 다운샘플."""
    ecos = _ecos()
    out = {}

    for key in ("base_rate", "ktb_3y", "ktb_10y", "usdkrw"):
        s = ecos[key].dropna()
        weekly = s.resample("W-FRI").last().dropna()  # 페이로드 축소
        out[key] = {
            "name": _KR_NAMES[key],
            "data": _series_payload(weekly),
            "latest": float(s.iloc[-1]),
        }

    # CPI: 월간 지수 → YoY %
    cpi = ecos["cpi"].dropna()
    cpi = cpi.set_axis(pd.PeriodIndex(cpi.index, freq="M"))
    cpi_yoy = (cpi.pct_change(12) * 100).dropna()
    cpi_yoy.index = cpi_yoy.index.to_timestamp()
    out["cpi_yoy"] = {
        "name": _KR_NAMES["cpi_yoy"],
        "data": _series_payload(cpi_yoy, "%Y-%m-%d"),
        "latest": float(cpi_yoy.iloc[-1]),
    }

    cli = _cli("KOR").loc["2010-01-01":].dropna()
    out["cli_kor"] = {
        "name": _KR_NAMES["cli_kor"],
        "data": _series_payload(cli, "%Y-%m-%d"),
        "latest": float(cli.iloc[-1]),
    }
    return out
