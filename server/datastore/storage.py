"""parquet 저장소 헬퍼 — APP_DATA 루트(로컬 경로 또는 s3://) 아래 읽기/쓰기.

쓰기는 read-modify-write(파일 통째 교체)다. 포트폴리오 기록은 KB~MB 규모이고
단일 사용자 앱이라 동시성 제어가 필요 없다 — DB를 두지 않는 근거.
"""

import os
from pathlib import Path

import pandas as pd

DEFAULT_APP_DATA = "s3://insight-invest-datalake/app"


def app_data_root() -> str:
    return os.environ.get("APP_DATA", DEFAULT_APP_DATA).rstrip("/")


def path(*parts: str) -> str:
    root = app_data_root()
    joined = "/".join(parts)
    if root.startswith("s3://"):
        return f"{root}/{joined}"
    p = Path(root).expanduser() / joined
    return str(p)


def read_parquet(*parts: str, columns=None, filters=None) -> pd.DataFrame:
    return pd.read_parquet(path(*parts), columns=columns, filters=filters)


def write_parquet(df: pd.DataFrame, *parts: str) -> str:
    target = path(*parts)
    if not target.startswith("s3://"):
        Path(target).parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(target, index=False)
    return target


def exists(*parts: str) -> bool:
    target = path(*parts)
    if target.startswith("s3://"):
        import s3fs

        return s3fs.S3FileSystem().exists(target)
    return Path(target).exists()
