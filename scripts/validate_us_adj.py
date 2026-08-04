"""massive 수정주가 정합성 검증 — yfinance 대조 (10종목, 전 구간).

검증 A (분할 조정): massive adj_close 가격수익률 vs yfinance Close 가격수익률
  (둘 다 분할 조정·배당 미반영 — 모든 날 일치해야 함. 분할 계수 오류 검출)
검증 B (총수익 합성): 스펙 D3 식으로 합성한 TR 수익률 vs yfinance Adj Close 수익률
  (배당락일에서 차이 나면 배당 데이터/합성식 오류)
검증 C (누적): 전 구간 누적수익 괴리 (연환산 드리프트)
"""

import time
import warnings

import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

MIRROR = "s3://insight-invest-datalake/qdata/clean"
TICKERS = ["GLD", "SPY", "QQQ", "SHY", "XLE", "TMF", "AAPL", "NVDA", "TSLA", "COST"]
BP = 1e-4

print("massive 로드 중...")
px = pd.read_parquet(
    f"{MIRROR}/us_prices.parquet",
    columns=["date", "ticker", "close", "adj_close"],
    filters=[("ticker", "in", TICKERS)],
)
dv = pd.read_parquet(f"{MIRROR}/us_dividends.parquet", filters=[("ticker", "in", TICKERS)])
# 같은 (ticker, ex_date) 복수 유형(정규+특별 등)은 합산
dv_sum = dv.groupby(["ticker", "ex_date"])["cash_amount"].sum()
dv_types = dv.groupby("ticker")["dividend_type"].agg(lambda s: sorted(set(s)))

rows = []
details = []
for t in TICKERS:
    m = px[px.ticker == t].set_index("date").sort_index()
    m.index = pd.to_datetime(m.index).normalize()
    F = m.adj_close / m.close  # 그날의 분할 누적계수

    div = dv_sum.loc[t] if t in dv_sum.index.get_level_values(0) else pd.Series(dtype=float)
    div.index = pd.to_datetime(div.index).normalize()
    dropped = div[~div.index.isin(m.index)]  # 거래일 밖 ex_date (소실 감시)
    div_on = div.reindex(m.index).fillna(0.0)

    r_px = m.adj_close.pct_change()
    r_tr = (m.adj_close + div_on * F) / m.adj_close.shift(1) - 1

    for attempt in range(3):
        try:
            y = yf.download(t, start="2003-09-01", auto_adjust=False, progress=False)
            if len(y):
                break
        except Exception:
            pass
        time.sleep(5)
    if y.empty:
        rows.append({"ticker": t, "n": 0, "note": "yfinance 실패"})
        continue
    if isinstance(y.columns, pd.MultiIndex):
        y.columns = y.columns.get_level_values(0)
    y.index = pd.to_datetime(y.index).tz_localize(None).normalize()
    yr_px = y["Close"].pct_change()
    yr_tr = y["Adj Close"].pct_change()

    common = m.index.intersection(y.index)[1:]
    dA = (r_px - yr_px).reindex(common).abs()
    dB = (r_tr - yr_tr).reindex(common).abs()

    cum_m = (1 + r_tr.reindex(common)).prod()
    cum_y = (1 + yr_tr.reindex(common)).prod()
    years = len(common) / 252
    drift_pa = ((cum_m / cum_y) ** (1 / years) - 1) * 1e4  # bp/년

    only_m = len(m.index.difference(y.index))
    only_y = len(y.index.difference(m.index))
    rows.append({
        "ticker": t,
        "n": len(common),
        "시작": str(common.min().date()),
        "A.분할 p99(bp)": dA.quantile(0.99) / BP,
        "A.최대(bp)": dA.max() / BP,
        "B.TR p99(bp)": dB.quantile(0.99) / BP,
        "B.최대(bp)": dB.max() / BP,
        "B>10bp일수": int((dB > 10 * BP).sum()),
        "B>50bp일수": int((dB > 50 * BP).sum()),
        "C.누적드리프트(bp/년)": drift_pa,
        "달력차(m/y)": f"{only_m}/{only_y}",
        "락일소실": len(dropped),
    })

    worst = dB.nlargest(3)
    for d, v in worst.items():
        if v > 10 * BP:
            details.append(
                f"  {t} {d.date()}: |Δr|={v/BP:.0f}bp  massiveTR={r_tr.get(d):+.4%} "
                f"yfTR={yr_tr.get(d):+.4%} div={div_on.get(d, 0):.4f} F={F.get(d, float('nan')):.3f}"
            )

rep = pd.DataFrame(rows)
pd.set_option("display.width", 200)
print("\n=== 종목별 정합성 (수익률 차이 bp) ===")
print(rep.to_string(index=False, float_format=lambda x: f"{x:,.1f}"))
print("\n=== 배당 유형 ===")
print(dv_types.to_string())
if details:
    print("\n=== B검증 최악일 (>10bp) ===")
    print("\n".join(details))
