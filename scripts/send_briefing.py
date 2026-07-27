#!/usr/bin/env python
"""일일 텔레그램 시황 보고서 (P7) — 지수·수급·섹터·신호·매크로·워치리스트·전략 요약 전송.

로컬 일일 파이프라인(daily_update.sh)에서 build_insights 다음에 실행된다.
- 인사이트 parquet: APP_DATA (기본 s3://insight-invest-datalake/app)
- 시세: qdata 레이크 (QDATA_LAKE, 기본 ~/Quant/data-lake)
- 봇 설정: /Users/achii/Quant/quant-data/.env 의 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID
  (환경변수가 있으면 우선; BRIEFING_ENV_FILE로 .env 경로 재지정 가능 — 테스트용)

TELEGRAM_BOT_TOKEN이 없으면 조용히 스킵(exit 0) — 파이프라인은 warn-only로 감싼다.
TELEGRAM_CHAT_ID가 없으면 getUpdates에서 최근 chat id를 찾아 이번 전송에 사용하고,
.env에 추가하라는 안내를 출력한다.

각 섹션은 개별 try/except — 일부 데이터가 없어도 나머지로 보고서를 구성한다.
전송은 parse_mode=HTML (동적 문자열은 html.escape).
"""

import html
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server"))

from datastore import meta, portfolio, storage, watchlist  # noqa: E402
from qdata import api as qdata_api  # noqa: E402

DEFAULT_ENV_FILE = str(Path.home() / "Quant" / "quant-data" / ".env")
MAX_LEN = 3800
WATCHLIST_CAP = 8
STRATEGY_CAP = 6
WEEKDAY_KR = "월화수목금토일"

# 섹션 빌더들이 채우는 공유 컨텍스트 — 한 줄 요약·헤더 날짜의 재료.
_ctx: dict = {}


# ---------------------------------------------------------------- 설정 로드


def _load_env_file(path: str) -> dict:
    vals = {}
    p = Path(path)
    if not p.exists():
        return vals
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        vals[k.strip()] = v.strip().strip('"').strip("'")
    return vals


def _telegram_api(token: str, method: str, payload: dict | None = None) -> dict:
    """Telegram Bot API 호출 — 실패는 RuntimeError로 통일 (traceback 없이 처리)."""
    url = f"https://api.telegram.org/bot{token}/{method}"
    try:
        if payload is None:
            req = urllib.request.Request(url)
        else:
            data = urllib.parse.urlencode(payload).encode()
            req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} HTTP {e.code}: {e.reason}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise RuntimeError(f"{method} 네트워크 오류: {e}") from None
    except ValueError as e:
        raise RuntimeError(f"{method} 응답 파싱 실패: {e}") from None
    if not body.get("ok"):
        raise RuntimeError(f"{method} 실패: {body.get('description')}")
    return body


def _discover_chat_id(token: str) -> str:
    """getUpdates에서 가장 최근 메시지의 chat id를 찾는다."""
    body = _telegram_api(token, "getUpdates")
    results = body.get("result") or []
    for upd in reversed(results):
        msg = upd.get("message") or upd.get("edited_message") or upd.get("channel_post") or {}
        chat = msg.get("chat") or {}
        if chat.get("id") is not None:
            return str(chat["id"])
    raise RuntimeError("getUpdates에 메시지가 없음 — 봇에게 아무 메시지나 먼저 보내세요")


# ---------------------------------------------------------------- 포맷 헬퍼


def _esc(s) -> str:
    return html.escape(str(s), quote=False)


def _arrow(x: float) -> str:
    return "▲" if x > 0 else ("▼" if x < 0 else "─")


def _pct(x: float) -> str:
    """등락률 — 부호는 화살표로 (▼1.2%)."""
    return f"{_arrow(x)}{abs(x):.1f}%"


def _eok(v: float) -> str:
    """원 → 억 (부호·콤마, 단위 없음 — 표 안에서 사용)."""
    return f"{v / 1e8:+,.0f}"


def _amount(v: float) -> str:
    """원 → 억/조 자동 단위 (부호 포함)."""
    if abs(v) >= 1e12:
        return f"{v / 1e12:+,.1f}조"
    return f"{v / 1e8:+,.0f}억"


def _try(fn):
    """서브 라인 빌더 실행 — 실패 시 None (섹션 내 부분 결손 허용)."""
    try:
        return fn()
    except Exception as e:
        print(f"[warn] 라인 생략 ({fn.__name__}): {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------- 섹션 빌더


def _section_market() -> str | None:
    lines = []

    def _kr_indices():
        start = (pd.Timestamp.today() - pd.DateOffset(days=90)).strftime("%Y-%m-%d")
        idx = qdata_api.load_krx_index(start=start)
        out = []
        for name in ("KOSPI", "KOSDAQ"):
            s = (
                idx[idx["index"] == name]
                .sort_values("date")
                .set_index("date")["close"]
                .dropna()
            )
            if len(s) < 2:
                continue
            last = float(s.iloc[-1])
            chg_1d = (last / float(s.iloc[-2]) - 1) * 100
            parts = []
            if len(s) > 5:
                parts.append(f"주 {(last / float(s.iloc[-6]) - 1) * 100:+.1f}")
            if len(s) > 21:
                parts.append(f"월 {(last / float(s.iloc[-22]) - 1) * 100:+.1f}")
            tail = f" ({' · '.join(parts)})" if parts else ""
            out.append(f"{name} {last:,.0f} {_pct(chg_1d)}{tail}")
            if name == "KOSPI":
                _ctx["report_date"] = pd.Timestamp(s.index[-1])
        return "\n".join(out) if out else None

    def _us():
        start = (pd.Timestamp.today() - pd.DateOffset(days=30)).strftime("%Y-%m-%d")
        px = qdata_api.load_prices(["SPY", "QQQ"], start=start, fields=("adj_close",))["adj_close"]
        parts = []
        for t in ("SPY", "QQQ"):
            s = px[t].dropna()
            if len(s) >= 2:
                parts.append(f"{t} {_pct((float(s.iloc[-1]) / float(s.iloc[-2]) - 1) * 100)}")
        vix = qdata_api.load_fred(["VIXCLS"], start=start)["VIXCLS"].dropna()
        if not vix.empty:
            parts.append(f"VIX {float(vix.iloc[-1]):.1f}")
        return " · ".join(parts) if parts else None

    def _fx():
        start = (pd.Timestamp.today() - pd.DateOffset(days=30)).strftime("%Y-%m-%d")
        s = qdata_api.load_ecos(["usdkrw"], start=start)["usdkrw"].dropna()
        if len(s) < 2:
            return None
        chg = (float(s.iloc[-1]) / float(s.iloc[-2]) - 1) * 100
        return f"USD/KRW {float(s.iloc[-1]):,.0f} {_pct(chg)}"

    def _breadth():
        df = storage.read_parquet("insight", "breadth_daily.parquet")
        last = df["date"].max()
        rows = df[(df["date"] == last) & (df["market"].isin(["KOSPI", "KOSDAQ"]))]
        if rows.empty:
            return None
        adv, dec = int(rows["advances"].sum()), int(rows["declines"].sum())
        nh, nl = int(rows["new_high_52w"].sum()), int(rows["new_low_52w"].sum())
        lu = int(rows["limit_up"].sum())
        tv = float(rows["total_value"].sum())
        n = (rows["advances"] + rows["declines"] + rows["unchanged"]).astype(float)
        ma20 = float((rows["pct_above_ma20"] * n).sum() / n.sum())
        _ctx["pct_above_ma20"] = ma20
        tag = " (과매도권)" if ma20 <= 20 else (" (과열권)" if ma20 >= 80 else "")
        return (
            f"등락 {adv}↑ {dec}↓ · 52주 신고 {nh}/신저 {nl} · 상한가 {lu}\n"
            f"거래대금 {tv / 1e12:,.1f}조 · MA20상회 {ma20:.0f}%{tag}"
        )

    for part in (_try(_kr_indices), _try(_us), _try(_fx), _try(_breadth)):
        if part:
            lines.append(part)
    if not lines:
        return None
    return "<b>시장</b>\n" + "\n".join(lines)


_INVESTOR_LABEL = [("frgn", "외국인 "), ("inst", "기관   "), ("indiv", "개인   ")]


def _section_flows() -> str | None:
    lines = []

    def _table():
        df = storage.read_parquet("insight", "flows_summary.parquet")
        last = df["date"].max()
        snap = df[(df["date"] == last) & (df["market"].isin(["KOSPI", "KOSDAQ"]))]
        if snap.empty:
            return None
        net = snap.pivot(index="investor", columns="market", values="net_value")
        rows = [f"<code>{'':7}{'KOSPI':>6} {'KOSDAQ':>7}</code>"]
        for inv, label in _INVESTOR_LABEL:
            if inv not in net.index:
                continue
            k = net.loc[inv].get("KOSPI")
            q = net.loc[inv].get("KOSDAQ")
            ks = _eok(float(k)) if pd.notna(k) else "-"
            qs = _eok(float(q)) if pd.notna(q) else "-"
            rows.append(f"<code>{label}{ks:>6} {qs:>7}</code>")
            if inv == "frgn" and pd.notna(k):
                _ctx["frgn_kospi_net"] = float(k)
        return "\n".join(rows) if len(rows) > 1 else None

    def _top():
        df = storage.read_parquet("insight", "flows_top.parquet")
        sub = df[(df["window"] == "1d") & (df["investor"] == "frgn")]
        buys = sub[sub["rank"] >= 1].sort_values("rank").head(3)
        sells = sub[sub["rank"] <= -1].sort_values("rank", ascending=False).head(3)
        out = []
        for label, grp in (("외인 매수", buys), ("외인 매도", sells)):
            if grp.empty:
                continue
            items = " · ".join(
                f"{_esc(r['name'])} {_eok(float(r['net_value']))}" for _, r in grp.iterrows()
            )
            out.append(f"{label} {items}")
        return "\n".join(out) if out else None

    for part in (_try(_table), _try(_top)):
        if part:
            lines.append(part)
    if not lines:
        return None
    return "<b>수급 (당일, 억)</b>\n" + "\n".join(lines)


def _section_sector() -> str | None:
    df = storage.read_parquet("insight", "sector_perf.parquet")
    sp = df[df["market"] == "KOSPI"].dropna(subset=["ret_1d"]).sort_values("ret_1d")
    if len(sp) < 4:
        return None
    top = sp.tail(2).iloc[::-1]
    bot = sp.head(2)
    up = " · ".join(f"{_esc(r['sector'])} {float(r['ret_1d']):+.1f}" for _, r in top.iterrows())
    dn = " · ".join(f"{_esc(r['sector'])} {float(r['ret_1d']):+.1f}" for _, r in bot.iterrows())
    return f"<b>섹터 (1D)</b>\n상위 {up}\n하위 {dn}"


def _section_signals() -> str | None:
    df = storage.read_parquet("insight", "flows_signals.parquet")
    frgn = df[df["investor"] == "frgn"]
    lines = []

    bull = frgn[frgn["divergence"] == "bull"].copy()
    if not bull.empty:
        bull = bull.reindex(bull["intensity_20d"].abs().sort_values(ascending=False).index)
        names = " · ".join(_esc(n) for n in bull["name"].head(3))
        lines.append(f"매집형(주가↓·외인 매집): {names}")

    streak = frgn[frgn["streak"] >= 7].sort_values("streak", ascending=False).head(3)
    if not streak.empty:
        items = " · ".join(
            f"{_esc(r['name'])}({int(r['streak'])}일)" for _, r in streak.iterrows()
        )
        lines.append(f"외인 연속매수 7일+: {items}")

    if not lines:
        return None
    return "<b>신호</b>\n" + "\n".join(lines)


def _section_macro() -> str | None:
    lines = []

    def _regime():
        from module import regime  # 지연 임포트 — FRED/CLI 로드

        ph = regime.current_phase()
        rg = regime.risk_gauge()
        _ctx["phase"] = ph["phase"]
        g = "↑" if ph["growth_dir"] == "up" else "↓"
        i = "↑" if ph["inflation_dir"] == "up" else "↓"
        score = rg["score"]
        label = "안정" if score < 40 else ("중립" if score < 60 else "위험회피")
        return f"국면 {ph['phase']} (성장{g} 물가{i}) · 위험게이지 {score:.0f}/100 {label}"

    def _valuation():
        df = storage.read_parquet("insight", "valuation_daily.parquet")
        kospi = df[df["market"] == "KOSPI"]
        row = kospi[kospi["date"] == kospi["date"].max()].iloc[0]
        pbr, rank = float(row["pbr"]), float(row["pct_rank_pbr"])
        _ctx["pct_rank_pbr"] = rank
        label = "고평가" if rank >= 80 else ("저평가" if rank <= 20 else "중립")
        return f"KOSPI PBR {pbr:.2f} — 역사적 상위 {100 - rank:.0f}% ({label})"

    def _us_rates():
        start = (pd.Timestamp.today() - pd.DateOffset(days=30)).strftime("%Y-%m-%d")
        f = qdata_api.load_fred(["T10Y2Y", "BAMLH0A0HYM2"], start=start)
        parts = []
        curve = f["T10Y2Y"].dropna()
        if not curve.empty:
            parts.append(f"美 10Y-2Y {float(curve.iloc[-1]):+.2f}%p")
        hy = f["BAMLH0A0HYM2"].dropna()
        if not hy.empty:
            parts.append(f"HY OAS {float(hy.iloc[-1]):.2f}%")
        return " · ".join(parts) if parts else None

    for part in (_try(_regime), _try(_valuation), _try(_us_rates)):
        if part:
            lines.append(part)
    if not lines:
        return None
    return "<b>매크로 · 레짐</b>\n" + "\n".join(lines)


def _section_watchlist() -> str | None:
    wl = watchlist.list_items()
    if wl.empty:
        return None
    m = meta.meta_df()[["meta_id", "ticker", "name", "iso_code"]]
    wl = wl.merge(m, on="meta_id", how="left")
    wl = wl[wl["iso_code"] == "KR"].head(WATCHLIST_CAP)
    if wl.empty:
        return None

    # 최신 KR 가격 (qdata) — 종가·등락률
    start = (pd.Timestamp.today() - pd.DateOffset(days=14)).strftime("%Y-%m-%d")
    px = qdata_api.load_krx_prices(start=start, columns=["close", "chg_pct"])
    snap = px[px["date"] == px["date"].max()].set_index("ticker")[["close", "chg_pct"]]

    # 외인 20d 순매수 (flows_signals)
    try:
        sig = storage.read_parquet("insight", "flows_signals.parquet")
        frgn20 = sig[sig["investor"] == "frgn"].set_index("ticker")["net_20d"]
    except FileNotFoundError:
        frgn20 = pd.Series(dtype=float)

    lines = []
    for _, r in wl.iterrows():
        name = r["name"] if isinstance(r["name"], str) and r["name"] else str(r["ticker"])
        row = snap.loc[r["ticker"]] if r["ticker"] in snap.index else None
        f20 = frgn20.get(r["ticker"])
        parts = [_esc(name)]
        if row is not None and pd.notna(row["chg_pct"]):
            chg = float(row["chg_pct"])
            parts.append(f"{float(row['close']):,.0f} {_arrow(chg)}{abs(chg):.1f}")
        if f20 is not None and pd.notna(f20):
            parts.append(f"외인20d {_amount(float(f20))}")
        if len(parts) == 1:  # 가격도 수급도 없으면 스킵 (예: 데이터 없는 ETF)
            continue
        lines.append(f"{parts[0]} " + " · ".join(parts[1:]))
    if not lines:
        return None
    return "<b>워치리스트</b>\n" + "\n".join(lines)


def _section_strategies() -> str | None:
    if not storage.exists("portfolio", "live_nav.parquet"):
        return None
    df = storage.read_parquet("portfolio", "live_nav.parquet")
    if df.empty:
        return None
    as_of = df["as_of"].iloc[-1]
    names = portfolio.records().set_index("port_id")["port_name"]
    try:  # 백테스트 연환산 수익률 (참고 표기)
        bt = storage.read_parquet("portfolio", "metrics.parquet").set_index("port_id")["ann_ret"]
    except Exception:
        bt = pd.Series(dtype=float)

    lines = []
    for port_id, g in df.groupby("port_id"):
        g = g.sort_values("trade_date")
        if pd.Timestamp(g["trade_date"].iloc[-1]).strftime("%Y-%m-%d") != as_of:
            continue  # as_of까지 데이터가 없는 전략(가격 소스 끊김)은 생략
        ret = (float(g["value"].iloc[-1]) / 1000.0 - 1) * 100
        name = names.get(port_id, f"port {port_id}")
        ann = bt.get(port_id)
        tail = f" (BT {float(ann):.1f})" if ann is not None and pd.notna(ann) else ""
        lines.append(f"{_esc(name)} {ret:+.1f}%{tail}")
        if len(lines) >= STRATEGY_CAP:
            break
    if not lines:
        return None
    return "<b>내 전략 (저장 후)</b>\n" + "\n".join(lines)


def _section_summary() -> str | None:
    """룰 기반 한 줄 요약 — 다른 섹션이 채운 _ctx로 문장 1~2개 조합."""
    base = None
    rank = _ctx.get("pct_rank_pbr")
    if rank is not None:
        if rank >= 80:
            base = "역사적 고평가 구간"
        elif rank <= 20:
            base = "역사적 저평가 구간"

    middle = []
    ma20 = _ctx.get("pct_above_ma20")
    if ma20 is not None:
        if ma20 <= 20:
            middle.append("시장폭 과매도권 진입")
        elif ma20 >= 80:
            middle.append("시장폭 과열권")
    frgn = _ctx.get("frgn_kospi_net")
    if frgn is not None:
        middle.append("외인 매수 지속" if frgn > 0 else "외인 매도 지속")

    parts = []
    if base and middle:
        parts.append(f"{base} — {', '.join(middle)}.")
    elif base:
        parts.append(f"{base}.")
    elif middle:
        parts.append(f"{', '.join(middle)}.")
    phase = _ctx.get("phase")
    if phase:
        parts.append(f"국면은 {phase} 유지.")
    if not parts:
        return None
    return "<b>한 줄 요약</b>\n" + " ".join(parts)


# ---------------------------------------------------------------- 조립·실행


def compose_message() -> str:
    sections = []
    for label, fn in [
        ("market", _section_market),
        ("flows", _section_flows),
        ("sector", _section_sector),
        ("signals", _section_signals),
        ("macro", _section_macro),
        ("watchlist", _section_watchlist),
        ("strategies", _section_strategies),
        ("summary", _section_summary),  # 마지막 — 앞 섹션들의 _ctx 사용
    ]:
        try:
            s = fn()
            if s:
                sections.append(s)
        except Exception as e:
            print(f"[warn] 섹션 {label} 생략: {e}", file=sys.stderr)

    d = _ctx.get("report_date", pd.Timestamp.today())
    header = f"<b>📊 시황 보고 · {d.month}/{d.day} ({WEEKDAY_KR[d.weekday()]})</b>"
    msg = header + "\n\n" + "\n\n".join(sections)
    if len(msg) > MAX_LEN:
        msg = msg[: MAX_LEN - 2] + " …"
    return msg


def main() -> int:
    env_file = os.environ.get("BRIEFING_ENV_FILE", DEFAULT_ENV_FILE)
    file_vals = _load_env_file(env_file)
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or file_vals.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID") or file_vals.get("TELEGRAM_CHAT_ID")

    if not token:
        print("[skip] briefing (토큰 없음)")
        return 0

    if not chat_id:
        try:
            chat_id = _discover_chat_id(token)
        except RuntimeError as e:
            print(f"[error] chat id 탐색 실패: {e}", file=sys.stderr)
            return 1
        print(
            f"TELEGRAM_CHAT_ID 미설정 — 다음 줄을 {env_file} 에 추가하세요:\n"
            f"TELEGRAM_CHAT_ID={chat_id}"
        )

    msg = compose_message()
    print(msg)
    try:
        _telegram_api(
            token,
            "sendMessage",
            {"chat_id": chat_id, "text": msg, "parse_mode": "HTML"},
        )
    except RuntimeError as e:
        print(f"[error] 브리핑 전송 실패: {e}", file=sys.stderr)
        return 1
    print(f"브리핑 전송 완료 ({len(msg)}자, chat_id={chat_id})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
