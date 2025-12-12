"""
ETL Step 1: 데이터 수집 (최적화)
- 배치 다운로드 + curl_cffi
- 재시도 + 지수 백오프
- Fallback 메커니즘
"""

import os
import sys
import time
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/../..")

from datetime import datetime, timedelta

import pandas as pd
import pyarrow as pa
import pyarrow.fs as pafs
import pyarrow.parquet as pq
import yfinance as yf
from curl_cffi import requests as curl_requests
from module.etl.config import get_staging_path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


def get_stocks_to_update(
    iso_code: str, database_url: str, target_date: datetime.date
) -> pd.DataFrame:
    """
    업데이트 대상 종목 조회

    Returns:
        DataFrame [meta_id, ticker, name, start_date]
    """
    engine = create_engine(database_url, pool_pre_ping=True)

    lookback_days = 7

    # Parameterized query로 SQL Injection 방지
    sql = text(
        """
        SELECT
            meta_id,
            ticker,
            name,
            CASE
                WHEN max_date IS NULL THEN
                    DATE '2000-01-01'
                ELSE
                    max_date - INTERVAL :lookback_days
            END as start_date
        FROM tb_meta
        WHERE iso_code = :iso_code
        AND (max_date IS NULL OR max_date < :target_date)
        ORDER BY start_date, meta_id
    """
    )

    df = pd.read_sql(
        sql,
        engine,
        params={
            "iso_code": iso_code,
            "target_date": target_date,
            "lookback_days": f"{lookback_days} days",
        },
    )
    engine.dispose()

    # KR 종목: Yahoo Finance는 .KS/.KQ 접미사 필요
    # (KOSPI: .KS, KOSDAQ: .KQ - 현재는 모두 .KS로 시도, 추후 개선 필요)
    if iso_code == "KR":
        df["ticker"] = df["ticker"] + ".KS"

    return df


def download_batch_with_retry(
    tickers: List[str], start_date: datetime.date, end_date: datetime.date, max_retries: int = 3
) -> Tuple[pd.DataFrame, bool]:
    """
    배치 다운로드 (curl_cffi + 재시도)

    Returns:
        (DataFrame, success: bool)
    """
    # curl_cffi 세션 생성
    session = curl_requests.Session(impersonate="chrome")

    try:
        for attempt in range(max_retries):
            try:
                print(f"      시도 {attempt + 1}/{max_retries}...")

                # yf.download()에 curl_cffi 세션 적용
                df = yf.download(
                    tickers=tickers,
                    start=start_date,
                    end=end_date,
                    group_by="ticker",
                    progress=False,
                    threads=False,
                    auto_adjust=False,
                    session=session,
                )

                if not df.empty:
                    return df, True

            except Exception as e:
                error_msg = str(e).lower()

                # Rate Limit 감지
                if "429" in error_msg or "rate limit" in error_msg or "too many" in error_msg:
                    wait = (attempt + 1) ** 2 * 10  # 지수 백오프: 10s, 40s, 90s
                    print(f"      ⚠️  Rate Limit! {wait}초 대기...")
                    time.sleep(wait)
                else:
                    wait = (attempt + 1) * 5
                    print(f"      ⚠️  에러: {str(e)[:50]}... {wait}초 후 재시도")
                    time.sleep(wait)

        return pd.DataFrame(), False

    finally:
        # 세션은 항상 닫기
        try:
            session.close()
        except:
            pass


def download_single_ticker_fallback(
    ticker: str, start_date: datetime.date, end_date: datetime.date
) -> Optional[pd.DataFrame]:
    """
    개별 종목 Fallback (배치 실패 시)
    """
    session = None
    try:
        session = curl_requests.Session(impersonate="chrome")

        # Ticker().history() 방식 (다른 엔드포인트)
        stock = yf.Ticker(ticker, session=session)
        df = stock.history(start=start_date, end=end_date, auto_adjust=False)

        if not df.empty:
            df = df[["Close", "Adj Close", "Volume"]].reset_index()
            df["ticker"] = ticker
            df.columns = ["trade_date", "close", "adj_close", "volume", "ticker"]
            return df
    except Exception as e:
        print(f"         ⚠️  {ticker} Fallback 실패: {str(e)[:30]}...")
    finally:
        if session:
            try:
                session.close()
            except:
                pass

    return None


def process_batch_optimized(
    batch_df: pd.DataFrame, target_date: datetime.date
) -> Tuple[pa.Table, List[str]]:
    """
    배치 처리 (최적화)

    Returns:
        (arrow_table, failed_tickers)
    """
    tickers = batch_df["ticker"].tolist()
    start_date = batch_df["start_date"].min()
    failed_tickers = []

    # 1차: 배치 다운로드 시도
    price_data, success = download_batch_with_retry(
        tickers=tickers,
        start_date=start_date,
        end_date=target_date + timedelta(days=1),
        max_retries=3,
    )

    results = []

    if success and not price_data.empty:
        # 배치 성공: 데이터 파싱
        if len(tickers) == 1:
            ticker = tickers[0]
            df = price_data[["Close", "Adj Close", "Volume"]].copy()
            df = df.reset_index()  # 🔽 추가 (index를 컬럼으로)
            df["ticker"] = ticker
            df.columns = ["trade_date", "close", "adj_close", "volume", "ticker"]
            results.append(df)
        else:
            for ticker in tickers:
                try:
                    ticker_data = price_data[ticker][["Close", "Adj Close", "Volume"]].copy()
                    ticker_data = ticker_data.reset_index()  # 🔽 추가
                    ticker_data["ticker"] = ticker
                    ticker_data.columns = ["trade_date", "close", "adj_close", "volume", "ticker"]
                    results.append(ticker_data)
                except (KeyError, AttributeError):
                    failed_tickers.append(ticker)
    else:
        # 배치 실패: 개별 Fallback
        print(f"      ⚠️  배치 실패, 개별 Fallback 시도...")

        for ticker in tickers:
            df = download_single_ticker_fallback(
                ticker, start_date, target_date + timedelta(days=1)
            )

            if df is not None and not df.empty:
                results.append(df)
            else:
                failed_tickers.append(ticker)

            # 개별 요청 간 딜레이
            time.sleep(1)

    if not results:
        return None, failed_tickers

    # DataFrame 통합
    combined = pd.concat(results, ignore_index=True)

    combined["ticker"] = combined["ticker"].astype(str)
    combined["trade_date"] = pd.to_datetime(combined["trade_date"]).dt.date

    # meta_id, name 추가 (ticker로 조인)
    batch_df_copy = batch_df.copy()
    batch_df_copy["ticker"] = batch_df_copy["ticker"].astype(str)

    combined = combined.merge(batch_df_copy[["ticker", "meta_id", "name"]], on="ticker", how="left")

    # KR 종목: .KS/.KQ 접미사 제거 (원래 ticker로 복원)
    combined["ticker"] = combined["ticker"].str.replace(".KS", "", regex=False)
    combined["ticker"] = combined["ticker"].str.replace(".KQ", "", regex=False)

    # 정제
    combined = combined.dropna(subset=["close", "adj_close"])
    combined["volume"] = combined["volume"].fillna(0).astype("int64")
    combined["gross_return"] = None
    combined["updated_at"] = datetime.now()

    # Arrow 변환
    arrow_schema = pa.schema(
        [
            pa.field("meta_id", pa.int32(), nullable=False),
            pa.field("trade_date", pa.date32(), nullable=False),
            pa.field("ticker", pa.string(), nullable=False),
            pa.field("name", pa.string(), nullable=True),
            pa.field("close", pa.float64(), nullable=True),
            pa.field("adj_close", pa.float64(), nullable=True),
            pa.field("gross_return", pa.float64(), nullable=True),
            pa.field("volume", pa.int64(), nullable=True),
            pa.field("updated_at", pa.timestamp("us"), nullable=False),
        ]
    )

    arrow_table = pa.Table.from_pandas(
        combined[
            [
                "meta_id",
                "trade_date",
                "ticker",
                "name",
                "close",
                "adj_close",
                "gross_return",
                "volume",
                "updated_at",
            ]
        ],
        schema=arrow_schema,
    )

    return arrow_table, failed_tickers


def ingest_daily_data(
    iso_code: str, date: datetime.date, database_url: str
) -> Tuple[int, List[str]]:
    """
    일별 데이터 수집 (최적화)

    Returns:
        (success_count, failed_tickers)
    """
    print(f"\n{'='*70}")
    print(f"📥 [{iso_code}] {date} 데이터 수집 (최적화)")
    print(f"{'='*70}")

    # 1. 대상 종목
    print("\n1️⃣ 대상 종목 조회 중...")
    stocks_df = get_stocks_to_update(iso_code, database_url, date)

    print(f"   ✅ {len(stocks_df)} 종목")

    if len(stocks_df) == 0:
        return 0, []

    # 2. 배치 처리
    print(f"\n2️⃣ Yahoo Finance 배치 다운로드 중...")

    batch_size = 150  # 보수적인 배치 크기
    arrow_tables = []
    all_failed = []
    total_success = 0

    for batch_idx in range(0, len(stocks_df), batch_size):
        batch = stocks_df.iloc[batch_idx : batch_idx + batch_size]
        batch_num = batch_idx // batch_size + 1
        total_batches = (len(stocks_df) + batch_size - 1) // batch_size

        print(f"\n   📦 배치 {batch_num}/{total_batches} ({len(batch)} 종목)")

        arrow_table, failed = process_batch_optimized(batch, date)

        if arrow_table is not None:
            arrow_tables.append(arrow_table)
            success = len(batch) - len(failed)
            total_success += success
            print(f"      ✅ 성공: {success}/{len(batch)}")

            if failed:
                print(f"      ⚠️  실패: {len(failed)}개")
                all_failed.extend(failed)
        else:
            print(f"      ❌ 전체 실패")
            all_failed.extend(batch["ticker"].tolist())

        # 배치 간 충분한 딜레이 (Rate Limit 방지)
        if batch_idx + batch_size < len(stocks_df):
            wait_time = 8  # 8초 대기
            print(f"      ⏳ {wait_time}초 대기 중...")
            time.sleep(wait_time)

    print(f"\n   📊 최종: {total_success}/{len(stocks_df)} 성공, {len(all_failed)} 실패")

    if not arrow_tables:
        print("   ⚠️  수집 데이터 없음")
        return 0, all_failed

    # 3. 통합 및 저장
    print(f"\n3️⃣ S3 저장 중...")
    combined_table = pa.concat_tables(arrow_tables)

    staging_path = get_staging_path(iso_code, date.strftime("%Y-%m-%d"))
    s3_fs = pafs.S3FileSystem(region="ap-northeast-2")

    with s3_fs.open_output_stream(staging_path.replace("s3://", "")) as f:
        pq.write_table(combined_table, f, compression="snappy")

    print(f"   ✅ {staging_path}")
    print(f"   📊 {len(combined_table)} rows, {combined_table.nbytes / 1024 / 1024:.2f} MB")

    return total_success, all_failed


if __name__ == "__main__":
    print("=" * 70)
    print("🚀 Step 1: Ingest (최적화)")
    print("=" * 70)

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL 환경변수가 없습니다!")

    target_date = datetime.now().date() - timedelta(days=1)

    print(f"\n📅 날짜: {target_date}")
    print(f"🌍 국가: US")
    print(f"⏱️  예상: 20~30분")
    print(f"📋 전략: 배치(150) + curl_cffi + 재시도 + Fallback\n")

    try:
        success, failed = ingest_daily_data("US", target_date, database_url)

        print("\n" + "=" * 70)
        print(f"✅ 완료: {success} 종목")

        if failed:
            print(f"⚠️  실패: {len(failed)} 종목")
            # 실패 목록 저장 (나중에 재시도용)
            failed_file = f"/tmp/failed_tickers_{target_date}.txt"
            with open(failed_file, "w") as f:
                f.write("\n".join(failed))
            print(f"   실패 목록: {failed_file}")

        print("=" * 70)

        staging_path = get_staging_path("US", target_date.strftime("%Y-%m-%d"))
        print(f"\n💾 {staging_path}")

    except Exception as e:
        print(f"\n❌ 실패: {e}")
        import traceback

        traceback.print_exc()
        exit(1)
