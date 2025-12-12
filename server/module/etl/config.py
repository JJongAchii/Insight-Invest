"""
ETL 공통 설정
"""

import pyarrow as pa

# S3 경로
S3_BUCKET = "insight-invest-datalake"
S3_WAREHOUSE = f"s3://{S3_BUCKET}/warehouse"
S3_STAGING = f"s3://{S3_BUCKET}/staging"
S3_TRANSFORMED = f"s3://{S3_BUCKET}/transformed"

# Iceberg 테이블 이름
TABLE_US_STOCKS = "market.us_stocks_price"
TABLE_KR_STOCKS = "market.kr_stocks_price"
TABLE_MACRO_DATA = "market.macro_data"

# Arrow 스키마 (US/KR 주식)
STOCK_SCHEMA = pa.schema(
    [
        pa.field("meta_id", pa.int32(), nullable=False),
        pa.field("trade_date", pa.date32(), nullable=False),
        pa.field("ticker", pa.string(), nullable=True),
        pa.field("name", pa.string(), nullable=True),
        pa.field("close", pa.float64(), nullable=True),
        pa.field("adj_close", pa.float64(), nullable=True),
        pa.field("gross_return", pa.float64(), nullable=True),
        pa.field("volume", pa.int64(), nullable=True),
        pa.field("updated_at", pa.timestamp("us"), nullable=True),
    ]
)

# Arrow 스키마 (매크로 데이터)
MACRO_SCHEMA = pa.schema(
    [
        pa.field("macro_id", pa.int32(), nullable=False),
        pa.field("base_date", pa.date32(), nullable=False),
        pa.field("value", pa.float64(), nullable=True),
        pa.field("fred_series_id", pa.string(), nullable=True),
        pa.field("updated_at", pa.timestamp("us"), nullable=False),
    ]
)


def get_staging_path(iso_code: str, date_str: str) -> str:
    """
    Staging 경로 생성 (타임스탬프 포함)

    Args:
        iso_code: "US" 또는 "KR"
        date_str: "YYYY-MM-DD" 형식

    Returns:
        S3 경로 (예: "s3://insight-invest-datalake/staging/stocks/US/2025-11-23_143025.parquet")
    """
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{S3_STAGING}/stocks/{iso_code}/{date_str}_{timestamp}.parquet"


def get_latest_staging_file(iso_code: str, date_str: str) -> str:
    """
    해당 날짜의 가장 최신 Staging 파일 경로 조회

    Args:
        iso_code: "US" 또는 "KR"
        date_str: "YYYY-MM-DD" 형식

    Returns:
        최신 파일의 S3 경로

    Raises:
        FileNotFoundError: 파일이 없을 경우
    """
    import s3fs

    s3 = s3fs.S3FileSystem(anon=False)
    pattern = f"{S3_BUCKET}/staging/stocks/{iso_code}/{date_str}_*.parquet"

    files = s3.glob(pattern)

    if not files:
        raise FileNotFoundError(f"No staging files found for {iso_code} on {date_str}")

    # 파일명 정렬 (타임스탬프 기준 최신)
    latest_file = sorted(files)[-1]

    return f"s3://{latest_file}"


def get_transformed_path(iso_code: str, date_str: str) -> str:
    """
    Transformed 경로 생성 (타임스탬프 포함)

    Args:
        iso_code: "US" 또는 "KR"
        date_str: "YYYY-MM-DD" 형식

    Returns:
        S3 경로 (예: "s3://insight-invest-datalake/transformed/stocks/US/2025-11-23_143025.parquet")
    """
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{S3_TRANSFORMED}/stocks/{iso_code}/{date_str}_{timestamp}.parquet"


def get_latest_transformed_file(iso_code: str, date_str: str) -> str:
    """
    해당 날짜의 가장 최신 Transformed 파일 경로 조회

    Args:
        iso_code: "US" 또는 "KR"
        date_str: "YYYY-MM-DD" 형식

    Returns:
        최신 파일의 S3 경로

    Raises:
        FileNotFoundError: 파일이 없을 경우
    """
    import s3fs

    s3 = s3fs.S3FileSystem(anon=False)
    pattern = f"{S3_BUCKET}/transformed/stocks/{iso_code}/{date_str}_*.parquet"

    files = s3.glob(pattern)

    if not files:
        raise FileNotFoundError(f"No transformed files found for {iso_code} on {date_str}")

    # 파일명 정렬 (타임스탬프 기준 최신)
    latest_file = sorted(files)[-1]

    return f"s3://{latest_file}"
