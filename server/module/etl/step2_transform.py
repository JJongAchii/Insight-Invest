"""
ETL Step 2: 데이터 변환 (Transform)
- Staging 데이터 읽기
- Iceberg 기준으로 adj_close 재계산
- gross_return 계산
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/../..")

from datetime import date, datetime, timedelta
from typing import Dict, Tuple

import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from module.etl.config import (
    TABLE_KR_STOCKS,
    TABLE_US_STOCKS,
    get_latest_staging_file,
    get_transformed_path,
)


def get_last_iceberg_data(iso_code: str, meta_ids: list) -> Dict[int, dict]:
    """
    Athena로 meta_id별 최신 데이터 조회 (날짜 제한 없음)

    Args:
        iso_code: "US" 또는 "KR"
        meta_ids: 종목 ID 리스트

    Returns:
        {meta_id: {'trade_date': date, 'adj_close': float}}
    """
    import time
    from datetime import datetime as dt

    import boto3

    # 빈 리스트 체크
    if not meta_ids:
        print(f"   ⚠️  조회할 meta_id가 없습니다")
        return {}

    athena = boto3.client("athena", region_name="ap-northeast-2")

    table_name = "us_stocks_price" if iso_code == "US" else "kr_stocks_price"
    meta_id_list = ",".join(map(str, meta_ids))

    # Athena 쿼리: meta_id별 최신 데이터
    query = f"""
        SELECT
            meta_id,
            MAX(trade_date) as last_date,
            MAX_BY(adj_close, trade_date) as adj_close
        FROM market.{table_name}
        WHERE meta_id IN ({meta_id_list})
        GROUP BY meta_id
    """

    print(f"   🔍 Athena 쿼리 실행 중... ({len(meta_ids)} 종목)")

    # 쿼리 실행 (결과는 datalake 버킷에 저장)
    try:
        response = athena.start_query_execution(
            QueryString=query,
            QueryExecutionContext={"Database": "market"},
            ResultConfiguration={"OutputLocation": "s3://insight-invest-datalake/athena-results/"},
        )
    except Exception as e:
        print(f"   ❌ Athena 쿼리 시작 실패: {e}")
        return {}

    query_id = response["QueryExecutionId"]

    # 대기 (최대 300초로 증가 - 대량 데이터 대응)
    query_succeeded = False
    max_wait_time = 300  # 5분
    for i in range(max_wait_time):
        status_response = athena.get_query_execution(QueryExecutionId=query_id)
        status = status_response["QueryExecution"]["Status"]["State"]

        if status == "SUCCEEDED":
            query_succeeded = True
            break
        elif status in ["FAILED", "CANCELLED"]:
            reason = status_response["QueryExecution"]["Status"].get("StateChangeReason", "")
            print(f"   ❌ Athena 쿼리 실패: {reason}")
            return {}

        if i % 10 == 0 and i > 0:
            print(f"      대기 중... ({i}초)")
        time.sleep(1)

    # 타임아웃 체크
    if not query_succeeded:
        print(f"   ❌ Athena 쿼리 타임아웃 ({max_wait_time}초)")
        return {}

    # 결과 조회 (페이징 처리)
    last_data = {}
    next_token = None

    while True:
        if next_token:
            result_response = athena.get_query_results(
                QueryExecutionId=query_id, NextToken=next_token
            )
        else:
            result_response = athena.get_query_results(QueryExecutionId=query_id)

        # 첫 번째 호출에서만 헤더 건너뜀
        rows = result_response["ResultSet"]["Rows"]
        start_idx = 1 if next_token is None else 0

        for row in rows[start_idx:]:
            try:
                meta_id = int(row["Data"][0]["VarCharValue"])
                last_date_str = row["Data"][1]["VarCharValue"]
                adj_close = float(row["Data"][2]["VarCharValue"])

                # 날짜 파싱
                last_date = dt.strptime(last_date_str, "%Y-%m-%d").date()

                last_data[meta_id] = {"trade_date": last_date, "adj_close": adj_close}
            except (KeyError, ValueError, IndexError):
                continue

        # 다음 페이지 확인
        next_token = result_response.get("NextToken")
        if not next_token:
            break

    print(f"   ✅ Athena: {len(last_data)}/{len(meta_ids)} 종목")

    return last_data


def recalculate_adj_close_and_returns(
    arrow_table: pa.Table, last_iceberg_data: Dict[int, dict]
) -> pa.Table:
    """
    Iceberg 기준으로 adj_close 재계산 + 중복 데이터 제거

    로직:
    1. Iceberg 마지막 날짜의 adj_close = 기준점
    2. Yahoo 소싱 데이터에서 같은 날짜의 adj_close = Yahoo 기준
    3. adj_close_new = adj_close_iceberg * (adj_close_yf / adj_close_yf_base)
    4. gross_return = (adj_close_new - adj_close_prev) / adj_close_prev
    5. Iceberg 마지막 날짜 이후 데이터만 유지 (중복 방지)

    Args:
        arrow_table: Staging 데이터 (Yahoo Finance)
        last_iceberg_data: Iceberg의 마지막 데이터

    Returns:
        재계산된 Arrow Table (Iceberg 마지막 날짜 이후만)
    """
    from datetime import date as date_type

    try:
        # Pandas 변환 (메모리 효율을 위해 필요한 컬럼만)
        needed_cols = [
            "meta_id",
            "trade_date",
            "ticker",
            "name",
            "close",
            "adj_close",
            "volume",
            "updated_at",
        ]
        df = arrow_table.select(needed_cols).to_pandas()

        # trade_date를 datetime.date로 통일 (타입 불일치 방지)
        if pd.api.types.is_datetime64_any_dtype(df["trade_date"]):
            df["trade_date"] = df["trade_date"].dt.date
        elif not df["trade_date"].apply(lambda x: isinstance(x, date_type)).all():
            df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date

        df = df.sort_values(["meta_id", "trade_date"]).reset_index(drop=True)

        df["adj_close_recalc"] = None
        df["gross_return"] = None
        df["_keep"] = True  # 유지할 행 표시

        # 종목별 처리
        for meta_id in df["meta_id"].unique():
            mask = df["meta_id"] == meta_id
            meta_df = df[mask].copy()

            # Iceberg 기준점
            if meta_id in last_iceberg_data:
                last_date = last_iceberg_data[meta_id]["trade_date"]
                adj_close_iceberg = last_iceberg_data[meta_id]["adj_close"]

                # Yahoo 데이터에서 같은 날짜 찾기 (타입 통일됨)
                same_date_row = meta_df[meta_df["trade_date"] == last_date]

                if not same_date_row.empty:
                    # Yahoo의 같은 날짜 adj_close
                    adj_close_yf_base = same_date_row.iloc[0]["adj_close"]
                else:
                    # 같은 날짜 없으면 Yahoo 첫 값 사용
                    adj_close_yf_base = meta_df.iloc[0]["adj_close"]

                # 중복 제거: Iceberg 마지막 날짜 이전/동일 데이터는 제외
                df.loc[mask & (df["trade_date"] <= last_date), "_keep"] = False
            else:
                # Iceberg에 데이터 없음 → Yahoo 첫 값이 기준 (신규 종목)
                adj_close_iceberg = meta_df.iloc[0]["adj_close"]
                adj_close_yf_base = meta_df.iloc[0]["adj_close"]
                last_date = None  # 신규 종목은 모든 데이터 유지

            # 계산
            adj_closes = []
            gross_returns = []

            # Iceberg에 데이터 있으면 prev = Iceberg 마지막, 없으면 None (신규 종목 첫 행은 None)
            prev_adj_close = adj_close_iceberg if meta_id in last_iceberg_data else None

            for idx, row in meta_df.iterrows():
                adj_close_yf = row["adj_close"]

                # Yahoo 변화율을 Iceberg 기준에 적용
                if adj_close_yf_base and adj_close_yf_base > 0:
                    adj_close_recalc = adj_close_iceberg * (adj_close_yf / adj_close_yf_base)
                else:
                    adj_close_recalc = adj_close_yf

                # gross_return 계산
                if prev_adj_close and prev_adj_close > 0:
                    gross_return = (adj_close_recalc - prev_adj_close) / prev_adj_close
                else:
                    gross_return = None

                adj_closes.append(adj_close_recalc)
                gross_returns.append(gross_return)

                # 다음을 위한 업데이트
                prev_adj_close = adj_close_recalc

            # DataFrame에 반영
            df.loc[mask, "adj_close_recalc"] = adj_closes
            df.loc[mask, "gross_return"] = gross_returns

        # adj_close 교체
        df["adj_close"] = df["adj_close_recalc"]
        df = df.drop(columns=["adj_close_recalc"])

        # 중복 데이터 제거: Iceberg 마지막 날짜 이후만 유지
        df = df[df["_keep"]].drop(columns=["_keep"])

        if df.empty:
            return None

        # Arrow Table로 변환
        return pa.Table.from_pandas(df[arrow_table.column_names], schema=arrow_table.schema)

    except Exception as e:
        print(f"      ❌ 재계산 중 에러: {e}")
        import traceback

        traceback.print_exc()
        return None


def validate_data(arrow_table: pa.Table) -> Tuple[pa.Table, list]:
    """
    데이터 검증 및 이상치 제거

    검증 항목:
        1. 결측치 체크 (close, adj_close, volume)
        2. 가격 이상치 (adj_close <= 0)
        3. 수익률 이상치 (gross_return > ±50%)
        4. 거래량 0 체크
        5. 거래일 연속성 체크 (5일 이상 갭)

    Returns:
        (cleaned_table, warnings)
    """
    warnings = []
    total_rows = len(arrow_table)

    # 1. 결측치 체크
    null_counts = {
        col: pc.sum(pc.is_null(arrow_table[col])).as_py()
        for col in ["close", "adj_close", "volume"]
    }

    for col, count in null_counts.items():
        if count > 0:
            warnings.append(f"⚠️ {col}: {count} null values ({count/total_rows*100:.1f}%)")

    # 2. 이상치 체크 (adj_close <= 0)
    invalid_prices = pc.sum(pc.less_equal(arrow_table["adj_close"], 0)).as_py()

    if invalid_prices > 0:
        warnings.append(f"❌ Invalid prices (<=0): {invalid_prices}")

    # 3. gross_return 이상치 체크 (±50% 초과)
    if "gross_return" in arrow_table.column_names:
        gross_returns = arrow_table.column("gross_return")

        # ±50% 초과 체크
        extreme_positive = pc.sum(pc.greater(gross_returns, 0.5)).as_py()
        extreme_negative = pc.sum(pc.less(gross_returns, -0.5)).as_py()

        if extreme_positive > 0:
            warnings.append(f"⚠️ Extreme positive returns (>50%): {extreme_positive}")

        if extreme_negative > 0:
            warnings.append(f"⚠️ Extreme negative returns (<-50%): {extreme_negative}")

    # 4. volume 0 체크
    zero_volume = pc.sum(pc.equal(arrow_table["volume"], 0)).as_py()

    if zero_volume > 0:
        pct = zero_volume / total_rows * 100
        # 10% 이상이면 경고, 아니면 정보
        if pct > 10:
            warnings.append(f"⚠️ Zero volume: {zero_volume} ({pct:.1f}%)")
        else:
            warnings.append(f"ℹ️ Zero volume: {zero_volume} ({pct:.1f}%)")

    # 5. 거래일 연속성 체크 (종목별 5일 이상 갭)
    df = arrow_table.to_pandas()
    df["trade_date"] = pd.to_datetime(df["trade_date"])

    gap_warnings = []
    for meta_id, group in df.groupby("meta_id"):
        if len(group) < 2:
            continue

        sorted_dates = group["trade_date"].sort_values()
        gaps = sorted_dates.diff().dropna()

        # 5 영업일 이상 갭 (약 7일)
        large_gaps = gaps[gaps > pd.Timedelta(days=7)]
        if len(large_gaps) > 0:
            ticker = group["ticker"].iloc[0]
            gap_warnings.append(f"{ticker}: {len(large_gaps)} large gaps")

    if gap_warnings:
        warnings.append(f"ℹ️ Trading day gaps (>7 days): {len(gap_warnings)} tickers")

    # 6. 데이터 정제: adj_close > 0인 것만
    mask = pc.greater(arrow_table["adj_close"], 0)
    cleaned_table = arrow_table.filter(mask)

    removed_count = total_rows - len(cleaned_table)
    if removed_count > 0:
        warnings.append(f"🗑️ Removed {removed_count} invalid rows")

    return cleaned_table, warnings


def transform_daily_data(iso_code: str, date: date) -> Tuple[pa.Table, int]:
    """
    일별 데이터 변환 (Iceberg 기준 재계산)

    Args:
        iso_code: "US" 또는 "KR"
        date: 대상 날짜

    Returns:
        (transformed_table, row_count)
    """
    import gc

    print(f"\n{'='*70}")
    print(f"🔄 [{iso_code}] {date} 데이터 변환 (Iceberg 기준)")
    print(f"{'='*70}")

    # 1. Staging 데이터 읽기
    print("\n1️⃣ Staging 데이터 읽기 중...")

    try:
        staging_path = get_latest_staging_file(iso_code, date.strftime("%Y-%m-%d"))
        arrow_table = pq.read_table(staging_path)
        print(f"   ✅ {len(arrow_table)} rows")
        print(f"   📂 {staging_path}")
    except FileNotFoundError as e:
        print(f"   ❌ Staging 파일 없음: {e}")
        return None, 0

    # 2. Staging 데이터 날짜 범위
    trade_dates = arrow_table.column("trade_date").to_pylist()
    min_date = min(trade_dates)
    max_date = max(trade_dates)

    print(f"   📅 Staging 범위: {min_date} ~ {max_date}")

    # 3. 전체 meta_id에 대해 Iceberg 기준점 1회 조회 (최적화)
    print(f"\n2️⃣ Iceberg 기준점 조회 (1회)...")

    all_meta_ids = list(set(arrow_table.column("meta_id").to_pylist()))
    print(f"   📊 총 {len(all_meta_ids)} 종목")

    # 전체 meta_id에 대해 한 번에 Athena 쿼리 (캐싱)
    last_iceberg_data = get_last_iceberg_data(iso_code, all_meta_ids)
    print(f"   ✅ Iceberg 기준점: {len(last_iceberg_data)}/{len(all_meta_ids)} 종목")

    # 4. 배치별 처리 (메모리 효율화, Athena 호출 없이 캐시 사용)
    print(f"\n3️⃣ 배치별 처리 시작 (캐시 사용)...")

    batch_size = 500  # 배치 크기: 500개 종목씩
    processed_tables = []

    for i in range(0, len(all_meta_ids), batch_size):
        batch_meta_ids = all_meta_ids[i : i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(all_meta_ids) + batch_size - 1) // batch_size

        print(f"\n   📦 배치 {batch_num}/{total_batches} ({len(batch_meta_ids)} 종목)")

        try:
            # 배치 필터링
            batch_filter = pc.is_in(arrow_table["meta_id"], pa.array(batch_meta_ids))
            batch_table = arrow_table.filter(batch_filter)

            print(f"      데이터: {len(batch_table)} rows")

            # 캐시된 Iceberg 기준점 사용 (Athena 호출 없음)
            batch_iceberg_data = {
                mid: last_iceberg_data[mid] for mid in batch_meta_ids if mid in last_iceberg_data
            }
            print(f"      Iceberg: {len(batch_iceberg_data)}/{len(batch_meta_ids)} 종목 (캐시)")

            # 재계산 + 중복 제거
            batch_table = recalculate_adj_close_and_returns(batch_table, batch_iceberg_data)

            if batch_table is not None and len(batch_table) > 0:
                processed_tables.append(batch_table)
                print(f"      ✅ {len(batch_table)} rows 처리 완료 (신규 데이터)")
            else:
                print(f"      ⏭️  신규 데이터 없음 (모두 기존 데이터)")

        except Exception as e:
            print(f"      ❌ 배치 {batch_num} 처리 실패: {e}")
            import traceback

            traceback.print_exc()
            # 배치 실패해도 계속 진행
            continue

        # 메모리 정리
        gc.collect()

    # 5. 모든 배치 합치기
    print(f"\n4️⃣ 배치 병합 중...")

    if not processed_tables:
        print(f"   ⚠️  신규 데이터 없음")
        return None, 0

    transformed_table = pa.concat_tables(processed_tables)
    print(f"   ✅ {len(transformed_table)} rows 병합 완료")

    # 통계 (메모리 효율적으로)
    gross_return_col = transformed_table.column("gross_return")
    non_null_count = pc.sum(pc.is_valid(gross_return_col)).as_py()

    if non_null_count > 0:
        print(f"   ✅ {non_null_count}/{len(transformed_table)} rows 계산됨")

        # min/max/mean (null 제외)
        filtered = gross_return_col.filter(pc.is_valid(gross_return_col))
        mean_val = pc.mean(filtered).as_py()
        min_val = pc.min(filtered).as_py()
        max_val = pc.max(filtered).as_py()

        print(f"   📊 평균: {mean_val:.4f}")
        print(f"   📊 범위: [{min_val:.4f}, {max_val:.4f}]")
    else:
        print(f"   ⚠️  모두 최초 데이터 (이전 가격 없음)")

    # 6. 데이터 검증
    print(f"\n5️⃣ 데이터 검증 중...")

    cleaned_table, warnings = validate_data(transformed_table)

    if warnings:
        print(f"   ⚠️  경고:")
        for warning in warnings[:10]:  # 최대 10개만 출력
            print(f"      - {warning}")
        if len(warnings) > 10:
            print(f"      ... 외 {len(warnings) - 10}개")

    removed = len(transformed_table) - len(cleaned_table)
    if removed > 0:
        print(f"   🗑️  제거: {removed} rows (이상치)")

    print(f"   ✅ 최종: {len(cleaned_table)} rows")

    # 7. Transformed 데이터 S3 저장 (실패 복구용)
    print(f"\n6️⃣ Transformed 데이터 저장 중...")

    import pyarrow.fs as pafs

    transformed_path = get_transformed_path(iso_code, date.strftime("%Y-%m-%d"))
    s3_fs = pafs.S3FileSystem(region="ap-northeast-2")

    with s3_fs.open_output_stream(transformed_path.replace("s3://", "")) as f:
        pq.write_table(cleaned_table, f, compression="snappy")

    print(f"   ✅ {transformed_path}")
    print(f"   📊 {len(cleaned_table)} rows, {cleaned_table.nbytes / 1024 / 1024:.2f} MB")

    return cleaned_table, len(cleaned_table)


if __name__ == "__main__":
    """
    테스트 실행
    """
    print("=" * 70)
    print("🚀 Step 2: Transform (Iceberg 기준)")
    print("=" * 70)

    target_date = datetime.now().date() - timedelta(days=1)

    print(f"\n📅 날짜: {target_date}")
    print(f"🌍 국가: US\n")

    try:
        transformed_table, row_count = transform_daily_data("US", target_date)

        if transformed_table is not None:
            print("\n" + "=" * 70)
            print(f"✅ 변환 완료: {row_count} rows")
            print("=" * 70)

            # 샘플 출력
            sample = transformed_table.slice(0, min(5, len(transformed_table)))
            print(f"\n📊 데이터 샘플:")
            print(
                sample.to_pandas()[
                    ["meta_id", "ticker", "trade_date", "close", "adj_close", "gross_return"]
                ]
            )
        else:
            print("\n❌ 변환 실패")

    except Exception as e:
        print(f"\n❌ 실패: {e}")
        import traceback

        traceback.print_exc()
        exit(1)
