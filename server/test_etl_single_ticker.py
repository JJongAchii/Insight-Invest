#!/usr/bin/env python3
"""
단일 티커 ETL 테스트 스크립트
SPY 등 특정 티커에 대해 전체 ETL 파이프라인을 테스트합니다.

Usage:
    python test_etl_single_ticker.py --ticker SPY
    python test_etl_single_ticker.py --ticker SPY --from step2
    python test_etl_single_ticker.py --ticker SPY --date 2025-12-01
"""
import argparse
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import pandas as pd
import pyarrow as pa
import pyarrow.fs as pafs
import pyarrow.parquet as pq
import yfinance as yf
from curl_cffi import requests as curl_requests
from module.etl.config import (
    S3_BUCKET,
    get_latest_staging_file,
    get_latest_transformed_file,
    get_staging_path,
    get_transformed_path,
)
from module.etl.step2_transform import (
    get_last_iceberg_data,
    recalculate_adj_close_and_returns,
    validate_data,
)
from module.etl.step3_load import load_to_iceberg
from sqlalchemy import create_engine, text


def get_ticker_meta(ticker: str, database_url: str) -> dict:
    """티커의 메타 정보 조회"""
    engine = create_engine(database_url, pool_pre_ping=True)

    sql = text(
        """
        SELECT meta_id, ticker, name, iso_code, max_date
        FROM tb_meta
        WHERE ticker = :ticker
    """
    )

    df = pd.read_sql(sql, engine, params={"ticker": ticker})
    engine.dispose()

    if df.empty:
        raise ValueError(f"Ticker '{ticker}' not found in tb_meta")

    return df.iloc[0].to_dict()


def step1_ingest_single(ticker: str, meta_info: dict, target_date, lookback_days: int = 7):
    """Step 1: 단일 티커 데이터 수집"""
    print(f"\n{'='*70}")
    print(f"📥 Step 1: {ticker} 데이터 수집")
    print(f"{'='*70}")

    iso_code = meta_info["iso_code"]
    meta_id = meta_info["meta_id"]
    name = meta_info["name"]
    max_date = meta_info["max_date"]

    # 시작 날짜 계산
    if max_date:
        start_date = max_date - timedelta(days=lookback_days)
    else:
        start_date = datetime(2000, 1, 1).date()

    print(f"   📊 meta_id: {meta_id}")
    print(f"   📊 iso_code: {iso_code}")
    print(f"   📊 max_date: {max_date}")
    print(f"   📊 start_date: {start_date}")
    print(f"   📊 target_date: {target_date}")

    # Yahoo ticker (KR은 .KS 추가)
    yf_ticker = f"{ticker}.KS" if iso_code == "KR" else ticker

    # Yahoo Finance 다운로드
    print(f"\n   🔽 Yahoo Finance 다운로드 중... ({yf_ticker})")

    session = curl_requests.Session(impersonate="chrome")

    df = yf.download(
        tickers=yf_ticker,
        start=start_date,
        end=target_date + timedelta(days=1),
        progress=False,
        auto_adjust=False,
        session=session,
    )

    session.close()

    if df.empty:
        raise ValueError(f"No data downloaded for {yf_ticker}")

    print(f"   ✅ {len(df)} rows 다운로드 완료")
    print(f"   📅 범위: {df.index.min().date()} ~ {df.index.max().date()}")

    # DataFrame 정제
    df = df[["Close", "Adj Close", "Volume"]].reset_index()
    df["ticker"] = ticker  # 원본 ticker (KR이면 .KS 제거)
    df.columns = ["trade_date", "close", "adj_close", "volume", "ticker"]

    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
    df["meta_id"] = meta_id
    df["name"] = name
    df["gross_return"] = None
    df["updated_at"] = datetime.now()

    # 정제
    df = df.dropna(subset=["close", "adj_close"])
    df["volume"] = df["volume"].fillna(0).astype("int64")

    print(f"   ✅ 정제 후: {len(df)} rows")

    # Arrow Table 변환
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
        df[
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

    # S3 저장
    print(f"\n   💾 S3 저장 중...")

    staging_path = get_staging_path(iso_code, target_date.strftime("%Y-%m-%d"))
    # 테스트용 경로로 변경
    staging_path = staging_path.replace("/staging/", "/staging-test/")

    s3_fs = pafs.S3FileSystem(region="ap-northeast-2")

    with s3_fs.open_output_stream(staging_path.replace("s3://", "")) as f:
        pq.write_table(arrow_table, f, compression="snappy")

    print(f"   ✅ {staging_path}")
    print(f"   📊 {len(arrow_table)} rows, {arrow_table.nbytes / 1024:.2f} KB")

    return arrow_table, staging_path


def step2_transform_single(arrow_table: pa.Table, iso_code: str, target_date):
    """Step 2: 단일 티커 데이터 변환"""
    print(f"\n{'='*70}")
    print(f"🔄 Step 2: 데이터 변환 (Iceberg 기준)")
    print(f"{'='*70}")

    # meta_id 추출
    meta_ids = list(set(arrow_table.column("meta_id").to_pylist()))
    print(f"   📊 meta_ids: {meta_ids}")

    # Iceberg 기준점 조회
    print(f"\n   🔍 Iceberg 기준점 조회 중...")
    last_iceberg_data = get_last_iceberg_data(iso_code, meta_ids)

    if last_iceberg_data:
        for mid, data in last_iceberg_data.items():
            print(f"      meta_id={mid}: {data['trade_date']}, adj_close={data['adj_close']:.4f}")
    else:
        print(f"      ⚠️  Iceberg에 데이터 없음 (신규 종목)")

    # 재계산
    print(f"\n   🔄 adj_close 재계산 중...")
    transformed_table = recalculate_adj_close_and_returns(arrow_table, last_iceberg_data)

    if transformed_table is None:
        print(f"   ⚠️  신규 데이터 없음 (모두 기존 데이터)")
        return None, None

    print(f"   ✅ {len(transformed_table)} rows 변환 완료")

    # 데이터 검증
    print(f"\n   🔍 데이터 검증 중...")
    cleaned_table, warnings = validate_data(transformed_table)

    if warnings:
        for warning in warnings:
            print(f"      ⚠️  {warning}")

    print(f"   ✅ 최종: {len(cleaned_table)} rows")

    # 샘플 출력
    print(f"\n   📊 데이터 샘플:")
    sample_df = cleaned_table.to_pandas()[
        ["meta_id", "ticker", "trade_date", "close", "adj_close", "gross_return"]
    ]
    print(sample_df.head(10).to_string(index=False))
    print("   ...")
    print(sample_df.tail(5).to_string(index=False))

    # S3 저장
    print(f"\n   💾 Transformed 저장 중...")

    transformed_path = get_transformed_path(iso_code, target_date.strftime("%Y-%m-%d"))
    # 테스트용 경로로 변경
    transformed_path = transformed_path.replace("/transformed/", "/transformed-test/")

    s3_fs = pafs.S3FileSystem(region="ap-northeast-2")

    with s3_fs.open_output_stream(transformed_path.replace("s3://", "")) as f:
        pq.write_table(cleaned_table, f, compression="snappy")

    print(f"   ✅ {transformed_path}")

    return cleaned_table, transformed_path


def step3_load_single(
    arrow_table: pa.Table, iso_code: str, target_date, database_url: str, dry_run: bool = True
):
    """Step 3: 단일 티커 데이터 적재 (테스트 모드)"""
    print(f"\n{'='*70}")
    print(f"💾 Step 3: 데이터 적재")
    print(f"{'='*70}")

    if dry_run:
        print(f"\n   ⚠️  DRY-RUN 모드: 실제 적재하지 않음")
        print(f"\n   📊 적재 예정 데이터:")
        print(f"      - iso_code: {iso_code}")
        print(f"      - rows: {len(arrow_table)}")

        # 날짜 범위
        trade_dates = arrow_table.column("trade_date").to_pylist()
        print(f"      - 날짜 범위: {min(trade_dates)} ~ {max(trade_dates)}")

        # 종목
        tickers = list(set(arrow_table.column("ticker").to_pylist()))
        print(f"      - 종목: {tickers}")

        print(f"\n   💡 실제 적재하려면 --no-dry-run 옵션을 사용하세요")
        return 0
    else:
        print(f"\n   ⚠️  실제 Iceberg에 적재합니다!")
        loaded_count = load_to_iceberg(iso_code, arrow_table, target_date, database_url)
        return loaded_count


def main():
    parser = argparse.ArgumentParser(description="단일 티커 ETL 테스트")
    parser.add_argument("--ticker", type=str, required=True, help="테스트할 티커 (예: SPY)")
    parser.add_argument("--date", type=str, default=None, help="대상 날짜 (YYYY-MM-DD)")
    parser.add_argument(
        "--from",
        dest="from_step",
        type=str,
        default="step1",
        choices=["step1", "step2", "step3"],
        help="시작 Step",
    )
    parser.add_argument("--no-dry-run", action="store_true", help="실제 Iceberg 적재 (주의!)")

    args = parser.parse_args()

    print("=" * 70)
    print(f"🧪 단일 티커 ETL 테스트: {args.ticker}")
    print("=" * 70)

    # 환경변수
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL 환경변수가 없습니다!")

    # 날짜
    if args.date:
        target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    else:
        target_date = datetime.now().date() - timedelta(days=1)

    print(f"\n📅 날짜: {target_date}")
    print(f"▶️  시작점: {args.from_step}")
    print(f"🔒 Dry-run: {not args.no_dry_run}")

    try:
        # 메타 정보 조회
        print(f"\n🔍 {args.ticker} 메타 정보 조회 중...")
        meta_info = get_ticker_meta(args.ticker, database_url)
        print(f"   ✅ meta_id: {meta_info['meta_id']}")
        print(f"   ✅ iso_code: {meta_info['iso_code']}")
        print(f"   ✅ name: {meta_info['name']}")
        print(f"   ✅ max_date: {meta_info['max_date']}")

        iso_code = meta_info["iso_code"]
        arrow_table = None

        # Step 1
        if args.from_step == "step1":
            arrow_table, staging_path = step1_ingest_single(args.ticker, meta_info, target_date)

        # Step 2
        if args.from_step in ["step1", "step2"]:
            if arrow_table is None:
                # staging에서 읽기 (테스트용 경로)
                print(f"\n📂 Staging 파일 읽는 중...")
                import s3fs

                s3 = s3fs.S3FileSystem(anon=False)
                pattern = f"{S3_BUCKET}/staging-test/stocks/{iso_code}/{target_date.strftime('%Y-%m-%d')}_*.parquet"
                files = s3.glob(pattern)
                if not files:
                    raise FileNotFoundError(f"No staging-test files found: {pattern}")
                staging_path = f"s3://{sorted(files)[-1]}"
                arrow_table = pq.read_table(staging_path)
                print(f"   ✅ {staging_path}")

            arrow_table, transformed_path = step2_transform_single(
                arrow_table, iso_code, target_date
            )

            if arrow_table is None:
                print(f"\n⚠️  변환할 신규 데이터가 없습니다.")
                return

        # Step 3
        if args.from_step == "step3":
            # transformed에서 읽기 (테스트용 경로)
            print(f"\n📂 Transformed 파일 읽는 중...")
            import s3fs

            s3 = s3fs.S3FileSystem(anon=False)
            pattern = f"{S3_BUCKET}/transformed-test/stocks/{iso_code}/{target_date.strftime('%Y-%m-%d')}_*.parquet"
            files = s3.glob(pattern)
            if not files:
                raise FileNotFoundError(f"No transformed-test files found: {pattern}")
            transformed_path = f"s3://{sorted(files)[-1]}"
            arrow_table = pq.read_table(transformed_path)
            print(f"   ✅ {transformed_path}")

        if arrow_table is not None:
            loaded_count = step3_load_single(
                arrow_table, iso_code, target_date, database_url, dry_run=not args.no_dry_run
            )

        # 완료
        print("\n" + "=" * 70)
        print(f"🎉 테스트 완료: {args.ticker}")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
        import traceback

        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()
