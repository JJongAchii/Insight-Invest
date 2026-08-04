"""massive 수정주가 정합성 검증 — yfinance 대조 + 전수 연속성 스캔.

인자 없음: massive 원본 vs yfinance 대조 (ETF 10종, 전 구간).
  검증 A (분할 조정): massive adj_close 가격수익률 vs yfinance Close 가격수익률
    (둘 다 분할 조정·배당 미반영 — 모든 날 일치해야 함. 분할 계수 오류 검출)
  검증 B (총수익 합성): 스펙 D3 식으로 합성한 TR 수익률 vs yfinance Adj Close 수익률
    (배당락일에서 차이 나면 배당 데이터/합성식 오류)
  검증 C (누적): 전 구간 누적수익 괴리 (연환산 드리프트)

--scan: 미러 US 전 종목 연속성 스캔 — 티커별 continuity_issues(공백·무분할 점프)로
  자동 제외 후보를 잡고, 리포트 전용 완화 티어(|일수익| 15~25%, 분할 계수 변동 없음)로
  사람 검토 후보를 별도 표기한다. datastore.meta.meta_df() 를 쓰므로 APP_DATA
  환경변수가 필요하다 (예: APP_DATA=s3://insight-invest-datalake/app). repo 루트에서
  실행: server/.venv-test/bin/python scripts/validate_us_adj.py --scan
  (미러 2.77GB를 연 청크로 읽어 수 분 소요될 수 있다)

--app-file: 위 대조를 massive 원본 대신 빌드된 앱 us_prices.parquet(APP_DATA 경로)의
  adj_close 로 재실행 — 합성 재계산 없이 빌더 산출물 자체의 회귀를 확인한다
  (A검증은 앱 파일에 무수정 close가 없어 대상 외 — B·C만). ETF 10종 + 개별주 14종.
  실행: APP_DATA=... server/.venv-test/bin/python scripts/validate_us_adj.py --app-file

심볼 표기: massive/앱 파일은 점 표기(BRK.B), yfinance 는 대시 표기(BRK-B) —
자동 변환해서 조회한다.
"""

import argparse
import os
import time
import warnings

import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

MIRROR = "s3://insight-invest-datalake/qdata/clean"
APP_DATA_DEFAULT = "s3://insight-invest-datalake/app"
TICKERS = ["GLD", "SPY", "QQQ", "SHY", "XLE", "TMF", "AAPL", "NVDA", "TSLA", "COST"]
STOCKS = ["MSFT", "JNJ", "KO", "XOM", "JPM", "MO", "GOOGL", "AMZN", "META",
          "C", "GE", "T", "MMM", "BRK.B"]
BP = 1e-4


def _yf_symbol(t: str) -> str:
    """massive/앱 표기(점) → yfinance 표기(대시). 예: BRK.B → BRK-B."""
    return t.replace(".", "-")


def _fetch_yf(t: str) -> pd.DataFrame:
    y = pd.DataFrame()
    for attempt in range(3):
        try:
            y = yf.download(_yf_symbol(t), start="2003-09-01", auto_adjust=False, progress=False)
            if len(y):
                break
        except Exception:
            pass
        time.sleep(5)
    return y


def _load_mirror(tickers):
    print("massive 로드 중...")
    px = pd.read_parquet(
        f"{MIRROR}/us_prices.parquet",
        columns=["date", "ticker", "close", "adj_close"],
        filters=[("ticker", "in", tickers)],
    )
    dv = pd.read_parquet(f"{MIRROR}/us_dividends.parquet", filters=[("ticker", "in", tickers)])
    # 같은 (ticker, ex_date) 복수 유형(정규+특별 등)은 합산
    dv_sum = dv.groupby(["ticker", "ex_date"])["cash_amount"].sum()
    dv_types = dv.groupby("ticker")["dividend_type"].agg(lambda s: sorted(set(s)))
    return px, dv_sum, dv_types


def _mirror_side(t: str, px: pd.DataFrame, dv_sum: pd.Series) -> dict | None:
    """massive 원본에서 배당을 합성한 TR (검증 A·B 모두 가능)."""
    m = px[px.ticker == t].set_index("date").sort_index()
    if m.empty:
        return None
    m.index = pd.to_datetime(m.index).normalize()
    F = m.adj_close / m.close  # 그날의 분할 누적계수

    div = dv_sum.loc[t] if t in dv_sum.index.get_level_values(0) else pd.Series(dtype=float)
    div.index = pd.to_datetime(div.index).normalize()
    dropped = div[~div.index.isin(m.index)]  # 거래일 밖 ex_date (소실 감시)
    div_on = div.reindex(m.index).fillna(0.0)

    r_px = m.adj_close.pct_change()
    r_tr = (m.adj_close + div_on * F) / m.adj_close.shift(1) - 1
    return {
        "index": m.index, "r_px": r_px, "r_tr": r_tr,
        "dropped": len(dropped), "div_on": div_on, "F": F,
    }


def _app_side(t: str, app_root: str) -> dict | None:
    """빌드된 앱 us_prices.parquet — adj_close pct_change 그대로 (합성 재계산 없음)."""
    m = pd.read_parquet(
        f"{app_root}/us_prices.parquet",
        columns=["trade_date", "ticker", "adj_close"],
        filters=[("ticker", "==", t)],
    )
    if m.empty:
        return None
    m = m.rename(columns={"trade_date": "date"}).set_index("date").sort_index()
    m.index = pd.to_datetime(m.index).normalize()
    r_tr = m["adj_close"].pct_change()
    return {"index": m.index, "r_px": None, "r_tr": r_tr, "dropped": None, "div_on": None, "F": None}


def compare(tickers: list[str], side_fn, label: str):
    """yfinance 대조 공용 루프 — side_fn(t) 가 massive/앱 쪽 시계열을 반환."""
    rows, details = [], []
    for t in tickers:
        side = side_fn(t)
        if side is None:
            rows.append({"ticker": t, "n": 0, "note": "소스에 없음"})
            continue
        idx, r_px, r_tr = side["index"], side["r_px"], side["r_tr"]

        y = _fetch_yf(t)
        if y.empty:
            rows.append({"ticker": t, "n": 0, "note": "yfinance 실패"})
            continue
        if isinstance(y.columns, pd.MultiIndex):
            y.columns = y.columns.get_level_values(0)
        y.index = pd.to_datetime(y.index).tz_localize(None).normalize()
        yr_px = y["Close"].pct_change()
        yr_tr = y["Adj Close"].pct_change()

        common = idx.intersection(y.index)[1:]
        dB = (r_tr - yr_tr).reindex(common).abs()

        cum_m = (1 + r_tr.reindex(common)).prod()
        cum_y = (1 + yr_tr.reindex(common)).prod()
        years = len(common) / 252
        drift_pa = ((cum_m / cum_y) ** (1 / years) - 1) * 1e4  # bp/년

        only_m = len(idx.difference(y.index))
        only_y = len(y.index.difference(idx))
        row = {"ticker": t, "n": len(common), "시작": str(common.min().date())}
        if r_px is not None:
            dA = (r_px - yr_px).reindex(common).abs()
            row["A.분할 p99(bp)"] = dA.quantile(0.99) / BP
            row["A.최대(bp)"] = dA.max() / BP
        row["B.TR p99(bp)"] = dB.quantile(0.99) / BP
        row["B.최대(bp)"] = dB.max() / BP
        row["B>10bp일수"] = int((dB > 10 * BP).sum())
        row["B>50bp일수"] = int((dB > 50 * BP).sum())
        row["C.누적드리프트(bp/년)"] = drift_pa
        row["달력차(m/y)"] = f"{only_m}/{only_y}"
        if side["dropped"] is not None:
            row["락일소실"] = side["dropped"]
        rows.append(row)

        worst = dB.nlargest(3)
        for d, v in worst.items():
            if v > 10 * BP:
                extra = ""
                if side["div_on"] is not None:
                    extra = f" div={side['div_on'].get(d, 0):.4f} F={side['F'].get(d, float('nan')):.3f}"
                details.append(
                    f"  {t} {d.date()}: |Δr|={v / BP:.0f}bp  {label}TR={r_tr.get(d):+.4%} "
                    f"yfTR={yr_tr.get(d):+.4%}{extra}"
                )
    return rows, details


def _print_report(title: str, rows, details, dv_types=None):
    rep = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    print(f"\n=== {title} (수익률 차이 bp) ===")
    print(rep.to_string(index=False, float_format=lambda x: f"{x:,.1f}"))
    if dv_types is not None:
        print("\n=== 배당 유형 ===")
        print(dv_types.to_string())
    if details:
        print("\n=== B검증 최악일 (>10bp) ===")
        print("\n".join(details))


def run_mirror_compare():
    px, dv_sum, dv_types = _load_mirror(TICKERS)
    rows, details = compare(TICKERS, lambda t: _mirror_side(t, px, dv_sum), label="massive")
    _print_report("종목별 정합성", rows, details, dv_types=dv_types)


def run_app_file_compare():
    app_root = os.environ.get("APP_DATA", APP_DATA_DEFAULT).rstrip("/")
    print(f"앱 파일 로드 중... ({app_root}/us_prices.parquet)")
    tickers = TICKERS + STOCKS
    rows, details = compare(tickers, lambda t: _app_side(t, app_root), label="app")
    _print_report("종목별 정합성 [--app-file]", rows, details)


def scan_continuity():
    """미러 US 전 종목 연속성 스캔 — 자동 제외(가드) vs 사람 검토(완화 티어) 분류.

    datastore.meta.meta_df() 는 APP_DATA 환경변수가 필요하다
    (예: APP_DATA=s3://insight-invest-datalake/app).
    """
    import sys
    sys.path.insert(0, "server")
    from datastore import meta
    from module.us_prices import JUMP_LIMIT, TICKER_SEGMENTS, continuity_issues, stitch_segments

    us = meta.meta_df().query("iso_code == 'US'")[["ticker"]].drop_duplicates()
    want = sorted(set(us["ticker"]) | {s for v in TICKER_SEGMENTS.values() for s, _, _ in v})
    print(f"스캔 대상 {len(want)}종목, 연도별 청크 로드 중...")
    frames = []
    for y in range(2008, pd.Timestamp.today().year + 1):
        c = pd.read_parquet(
            f"{MIRROR}/us_prices.parquet", columns=["date", "ticker", "close", "adj_close"],
            filters=[("ticker", "in", want), ("date", ">=", pd.Timestamp(f"{y}-01-01")),
                     ("date", "<=", pd.Timestamp(f"{y}-12-31"))],
        )
        if len(c):
            frames.append(c)
    px = pd.concat(frames, ignore_index=True)
    px["date"] = pd.to_datetime(px["date"])
    # dtype 명시 필수 — 빈 리스트로 만들면 ex_date가 float64가 돼 stitch_segments 내부의
    # Timestamp 비교(_cut)가 "'<=' not supported between ndarray and Timestamp"로 죽는다.
    empty_div = pd.DataFrame({
        "ticker": pd.Series(dtype="object"),
        "ex_date": pd.Series(dtype="datetime64[ns]"),
        "cash_amount": pd.Series(dtype="float64"),
    })
    px, _ = stitch_segments(px, empty_div, TICKER_SEGMENTS)

    hard, soft = [], []
    for tk, g in px.groupby("ticker", sort=False):
        g = g.sort_values("date").set_index("date")
        issues = continuity_issues(g)
        if issues:
            hard.append((tk, issues[:3]))
        r = g["adj_close"].pct_change().abs()
        f_chg = (g["adj_close"] / g["close"]).pct_change().abs() > 0.005
        watch = r[(r > 0.15) & (r <= JUMP_LIMIT) & ~f_chg]
        if len(watch):
            soft.append((tk, [f"{d.date()} {v:.0%}" for d, v in watch.tail(3).items()]))
    print(f"자동 제외(가드) {len(hard)}종목:")
    for tk, iss in hard:
        print(f"  {tk}: {'; '.join(iss)}")
    print(f"\n사람 검토(15~25% 점프) {len(soft)}종목:")
    for tk, days in soft:
        print(f"  {tk}: {'; '.join(days)}")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--scan", action="store_true",
        help="미러 US 전 종목 연속성 스캔 (자동 제외/사람 검토 분류). APP_DATA 필요",
    )
    parser.add_argument(
        "--app-file", action="store_true", dest="app_file",
        help="massive 원본 대신 빌드된 앱 us_prices.parquet 로 ETF10+개별주14 재대조",
    )
    args = parser.parse_args()
    if args.scan and args.app_file:
        parser.error("--scan 과 --app-file 은 동시에 쓸 수 없다")

    if args.scan:
        scan_continuity()
    elif args.app_file:
        run_app_file_compare()
    else:
        run_mirror_compare()


if __name__ == "__main__":
    main()
