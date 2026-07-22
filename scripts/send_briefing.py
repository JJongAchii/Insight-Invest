#!/usr/bin/env python
"""일일 텔레그램 브리핑 (P7) — 국면·시장폭·수급·관심종목·전략 추적 요약 전송.

로컬 일일 파이프라인(daily_update.sh)에서 build_insights 다음에 실행된다.
- 인사이트 parquet: APP_DATA (기본 s3://insight-invest-datalake/app)
- 시세: qdata 레이크 (QDATA_LAKE, 기본 ~/Quant/data-lake)
- 봇 설정: /Users/achii/Quant/quant-data/.env 의 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID
  (환경변수가 있으면 우선; BRIEFING_ENV_FILE로 .env 경로 재지정 가능 — 테스트용)

TELEGRAM_BOT_TOKEN이 없으면 조용히 스킵(exit 0) — 파이프라인은 warn-only로 감싼다.
TELEGRAM_CHAT_ID가 없으면 getUpdates에서 최근 chat id를 찾아 이번 전송에 사용하고,
.env에 추가하라는 안내를 출력한다.

각 섹션은 개별 try/except — 일부 데이터가 없어도 나머지로 브리핑을 구성한다.
"""

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
MAX_LEN = 3500
WATCHLIST_CAP = 10


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


# ---------------------------------------------------------------- 섹션 빌더


def _fmt_eok(value: float) -> str:
    """원 단위 → 억 단위 부호 표기 (+1,234억)."""
    eok = value / 1e8
    return f"{eok:+,.0f}억"


def _section_regime() -> str:
    from module import regime  # 지연 임포트 — FRED/CLI 로드

    ph = regime.current_phase()
    rg = regime.risk_gauge()
    return (
        f"*국면* {ph['phase']} (성장 {ph['growth_dir']} · 물가 {ph['inflation_dir']})\n"
        f"*리스크 게이지* {rg['score']:.0f}/100 (as of {rg['as_of']})"
    )


def _section_breadth() -> str:
    df = storage.read_parquet("insight", "breadth_daily.parquet")
    kospi = df[df["market"] == "KOSPI"]
    row = kospi[kospi["date"] == kospi["date"].max()].iloc[0]
    d = pd.Timestamp(row["date"]).strftime("%m/%d")
    return (
        f"*KOSPI 시장폭* ({d}) 상승 {int(row['advances'])} / 하락 {int(row['declines'])}"
        f" · 52주 신고가 {int(row['new_high_52w'])}"
    )


def _section_flows_top() -> str:
    df = storage.read_parquet("insight", "flows_top.parquet")
    top = df[(df["window"] == "1d") & (df["investor"] == "frgn") & (df["rank"] >= 1)]
    top = top.sort_values("rank").head(3)
    if top.empty:
        return ""
    items = ", ".join(
        f"{row['name']} {_fmt_eok(row['net_value'])}" for _, row in top.iterrows()
    )
    return f"*외인 순매수 Top3* (1d) {items}"


def _section_watchlist() -> str:
    wl = watchlist.list_items()
    if wl.empty:
        return ""
    m = meta.meta_df()[["meta_id", "ticker", "name", "iso_code"]]
    wl = wl.merge(m, on="meta_id", how="left")
    wl = wl[wl["iso_code"] == "KR"].head(WATCHLIST_CAP)
    if wl.empty:
        return ""

    # 최신 KR 가격 (qdata) — 등락률
    start = (pd.Timestamp.today() - pd.DateOffset(days=14)).strftime("%Y-%m-%d")
    px = qdata_api.load_krx_prices(start=start, columns=["chg_pct"])
    snap = px[px["date"] == px["date"].max()].set_index("ticker")["chg_pct"]

    # 외인 20d 순매수 (flows_signals)
    try:
        sig = storage.read_parquet("insight", "flows_signals.parquet")
        frgn20 = sig[sig["investor"] == "frgn"].set_index("ticker")["net_20d"]
    except FileNotFoundError:
        frgn20 = pd.Series(dtype=float)

    lines = []
    for _, r in wl.iterrows():
        name = r["name"] if isinstance(r["name"], str) and r["name"] else str(r["ticker"])
        chg = snap.get(r["ticker"])
        f20 = frgn20.get(r["ticker"])
        parts = [f"{name}"]
        if chg is not None and pd.notna(chg):
            parts.append(f"{float(chg):+.1f}%")
        if f20 is not None and pd.notna(f20):
            parts.append(f"외인20d {_fmt_eok(float(f20))}")
        if len(parts) == 1:  # 가격도 수급도 없으면 스킵 (예: 데이터 없는 ETF)
            continue
        lines.append("· " + " ".join(parts))
    if not lines:
        return ""
    return "*관심종목*\n" + "\n".join(lines)


def _section_live_strategies() -> str:
    if not storage.exists("portfolio", "live_nav.parquet"):
        return ""
    df = storage.read_parquet("portfolio", "live_nav.parquet")
    if df.empty:
        return ""
    as_of = df["as_of"].iloc[-1]
    names = portfolio.records().set_index("port_id")["port_name"]
    lines = []
    for port_id, g in df.groupby("port_id"):
        g = g.sort_values("trade_date")
        if pd.Timestamp(g["trade_date"].iloc[-1]).strftime("%Y-%m-%d") != as_of:
            continue  # as_of까지 데이터가 없는 전략(가격 소스 끊김)은 생략
        ret = (float(g["value"].iloc[-1]) / 1000.0 - 1) * 100
        name = names.get(port_id, f"port {port_id}")
        lines.append(f"· {name}: 저장후 {ret:+.1f}%")
    if not lines:
        return ""
    return f"*전략 실전 추적* (as of {as_of})\n" + "\n".join(lines)


def compose_message() -> str:
    sections = []
    for label, fn in [
        ("regime", _section_regime),
        ("breadth", _section_breadth),
        ("flows_top", _section_flows_top),
        ("watchlist", _section_watchlist),
        ("live", _section_live_strategies),
    ]:
        try:
            s = fn()
            if s:
                sections.append(s)
        except Exception as e:
            print(f"[warn] 섹션 {label} 생략: {e}", file=sys.stderr)

    today = pd.Timestamp.today().strftime("%Y-%m-%d")
    msg = f"📈 *데일리 브리핑* {today}\n\n" + "\n\n".join(sections)
    if len(msg) > MAX_LEN:
        msg = msg[: MAX_LEN - 2] + " …"
    return msg


# ---------------------------------------------------------------- 실행


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
    try:
        _telegram_api(
            token,
            "sendMessage",
            {"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"},
        )
    except RuntimeError as e:
        print(f"[error] 브리핑 전송 실패: {e}", file=sys.stderr)
        return 1
    print(f"브리핑 전송 완료 ({len(msg)}자, chat_id={chat_id})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
