"""
일별 ETL 전체 파이프라인
Step 1 (Ingest) → Step 2 (Transform) → Step 3 (Load)

실패 복구 지원:
- from_step="step1": 전체 실행 (기본값)
- from_step="step2": staging에서 시작 (Step1 건너뜀)
- from_step="step3": transformed에서 시작 (Step1, 2 건너뜀)
"""

import os
import sys
from typing import Literal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/../..")

from datetime import datetime, timedelta

import pyarrow.parquet as pq
from module.etl.config import get_latest_transformed_file
from module.etl.step1_ingest import ingest_daily_data
from module.etl.step2_transform import transform_daily_data
from module.etl.step3_load import load_to_iceberg

StepType = Literal["step1", "step2", "step3"]


def run_daily_etl(
    iso_code: str, target_date: datetime.date, database_url: str, from_step: StepType = "step1"
):
    """
    일별 ETL 전체 실행

    Args:
        iso_code: "US" 또는 "KR"
        target_date: 대상 날짜
        database_url: PostgreSQL 연결 URL
        from_step: 시작할 Step ("step1", "step2", "step3")
    """
    print("\n" + "=" * 80)
    print(f"🚀 일별 ETL 파이프라인 시작")
    print(f"   국가: {iso_code}")
    print(f"   날짜: {target_date}")
    print(f"   시작점: {from_step}")
    print("=" * 80)

    success_count = 0
    failed_tickers = []
    row_count = 0
    transformed_table = None

    try:
        # Step 1: Ingest (소싱)
        if from_step == "step1":
            print("\n" + "▶" * 40)
            print("Step 1: Ingest (데이터 수집)")
            print("▶" * 40)

            success_count, failed_tickers = ingest_daily_data(iso_code, target_date, database_url)

            if success_count == 0:
                print(f"\n⚠️  소싱된 데이터 없음. ETL 종료.")
                return

            print(f"\n✅ Step 1 완료: {success_count} 종목")

            if failed_tickers:
                print(f"⚠️  실패: {len(failed_tickers)} 종목")
        else:
            print("\n" + "⏭️" * 20)
            print(f"Step 1: 건너뜀 (from_step={from_step})")
            print("⏭️" * 20)

        # Step 2: Transform (변환)
        if from_step in ["step1", "step2"]:
            print("\n" + "▶" * 40)
            print("Step 2: Transform (데이터 변환)")
            print("▶" * 40)

            transformed_table, row_count = transform_daily_data(iso_code, target_date)

            if transformed_table is None or row_count == 0:
                print(f"\n⚠️  변환된 데이터 없음. ETL 종료.")
                return

            print(f"\n✅ Step 2 완료: {row_count} rows")
        else:
            print("\n" + "⏭️" * 20)
            print(f"Step 2: 건너뜀 (from_step={from_step})")
            print("⏭️" * 20)

        # Step 3: Load (적재)
        print("\n" + "▶" * 40)
        print("Step 3: Load (데이터 적재)")
        print("▶" * 40)

        # Step 3부터 시작하는 경우 transformed 파일 읽기
        if from_step == "step3":
            print(f"\n📂 Transformed 파일 읽는 중...")
            try:
                transformed_path = get_latest_transformed_file(
                    iso_code, target_date.strftime("%Y-%m-%d")
                )
                transformed_table = pq.read_table(transformed_path)
                row_count = len(transformed_table)
                print(f"   ✅ {transformed_path}")
                print(f"   📊 {row_count} rows")
            except FileNotFoundError as e:
                print(f"   ❌ Transformed 파일 없음: {e}")
                print(f"   💡 Step 2부터 실행하세요: --from step2")
                return

        loaded_count = load_to_iceberg(iso_code, transformed_table, target_date, database_url)

        print(f"\n✅ Step 3 완료: {loaded_count} rows")

        # 최종 결과
        print("\n" + "=" * 80)
        print(f"🎉 일별 ETL 완료!")
        if from_step == "step1":
            print(f"   소싱: {success_count} 종목")
        if from_step in ["step1", "step2"]:
            print(f"   변환: {row_count} rows")
        print(f"   적재: {loaded_count} rows")

        if failed_tickers:
            print(f"   실패: {len(failed_tickers)} 종목")

        print("=" * 80)

    except Exception as e:
        print("\n" + "=" * 80)
        print(f"❌ ETL 실패!")
        print(f"   에러: {e}")
        print("=" * 80)
        import traceback

        traceback.print_exc()
        raise


if __name__ == "__main__":
    """
    실행
    """
    import argparse

    parser = argparse.ArgumentParser(description="일별 ETL 파이프라인")
    parser.add_argument(
        "--iso-code", type=str, default="US", choices=["US", "KR"], help="국가 코드"
    )
    parser.add_argument(
        "--from",
        dest="from_step",
        type=str,
        default="step1",
        choices=["step1", "step2", "step3"],
        help="시작할 Step",
    )
    parser.add_argument("--date", type=str, default=None, help="대상 날짜 (YYYY-MM-DD)")

    args = parser.parse_args()

    print("=" * 80)
    print("🚀 일별 ETL 파이프라인")
    print("=" * 80)

    # 환경변수
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL 환경변수가 없습니다!")

    # 날짜 파싱
    if args.date:
        target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    else:
        target_date = datetime.now().date() - timedelta(days=1)

    print(f"\n📅 날짜: {target_date}")
    print(f"🌍 국가: {args.iso_code}")
    print(f"▶️  시작점: {args.from_step}")
    print(f"⏱️  예상: 20~40분\n")

    try:
        run_daily_etl(args.iso_code, target_date, database_url, from_step=args.from_step)

    except Exception as e:
        print(f"\n❌ 실패: {e}")
        exit(1)
