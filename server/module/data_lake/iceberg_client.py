"""
Iceberg Catalog 싱글톤 클라이언트
"""

import logging
from datetime import date
from typing import List, Optional

import pandas as pd
from pyiceberg.catalog import load_catalog
from pyiceberg.expressions import And, EqualTo, GreaterThanOrEqual, In, LessThanOrEqual

logger = logging.getLogger(__name__)


class IcebergClient:
    _instance = None
    _catalog = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def catalog(self):
        if self._catalog is None:
            self._catalog = load_catalog(
                "glue",
                **{
                    "type": "glue",
                    "s3.region": "ap-northeast-2",
                    "warehouse": "s3://insight-invest-datalake/warehouse",
                },
            )
        return self._catalog

    def get_table(self, table_name: str):
        """
        테이블 로드

        Args:
            table_name: "schema.table" 형식 (예: "market.us_stocks_price")
        """
        return self.catalog.load_table(table_name)

    def create_table(self, table_name: str, schema, partition_spec=None):
        """
        새 Iceberg 테이블 생성

        Args:
            table_name: "schema.table" 형식 (예: "market.portfolio_nav")
            schema: PyArrow 스키마
            partition_spec: 파티션 스펙 (선택)

        Returns:
            생성된 테이블
        """
        if partition_spec is None:
            return self.catalog.create_table(table_name, schema=schema)
        else:
            return self.catalog.create_table(
                table_name, schema=schema, partition_spec=partition_spec
            )

    def table_exists(self, table_name: str) -> bool:
        """
        테이블 존재 여부 확인

        Args:
            table_name: "schema.table" 형식

        Returns:
            True if exists, False otherwise
        """
        try:
            self.catalog.load_table(table_name)
            return True
        except Exception:
            return False

    def read_price_data(
        self,
        iso_code: str,
        meta_ids: Optional[List[int]] = None,
        tickers: Optional[List[str]] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> pd.DataFrame:
        """
        Iceberg에서 가격 데이터 조회 (PyIceberg 직접 읽기)

        Args:
            iso_code: "US" 또는 "KR"
            meta_ids: 조회할 meta_id 리스트 (선택)
            tickers: 조회할 ticker 리스트 (선택)
            start_date: 시작 날짜 (선택)
            end_date: 종료 날짜 (선택)

        Returns:
            DataFrame [meta_id, trade_date, ticker, adj_close, gross_return]
        """
        table_name = f"market.{'us' if iso_code == 'US' else 'kr'}_stocks_price"

        try:
            table = self.get_table(table_name)
        except Exception as e:
            logger.error(f"Iceberg 테이블 로드 실패: {table_name}, {e}")
            return pd.DataFrame()

        # 필터 조건 구성
        filters = []

        if meta_ids:
            filters.append(In("meta_id", meta_ids))

        if tickers:
            filters.append(In("ticker", tickers))

        if start_date:
            filters.append(GreaterThanOrEqual("trade_date", start_date))

        if end_date:
            filters.append(LessThanOrEqual("trade_date", end_date))

        # 스캔 실행
        try:
            if filters:
                combined_filter = filters[0]
                for f in filters[1:]:
                    combined_filter = And(combined_filter, f)
                scan = table.scan(row_filter=combined_filter)
            else:
                scan = table.scan()

            # Arrow 테이블로 읽고 Pandas로 변환
            arrow_table = scan.to_arrow()
            df = arrow_table.to_pandas()

            logger.info(f"Iceberg 가격 데이터 조회: {len(df)} rows from {table_name}")
            return df

        except Exception as e:
            logger.error(f"Iceberg 가격 데이터 조회 실패: {e}", exc_info=True)
            return pd.DataFrame()

    def get_latest_prices(self, iso_code: str) -> pd.DataFrame:
        """
        종목별 최신 가격 조회

        Args:
            iso_code: "US" 또는 "KR"

        Returns:
            DataFrame [meta_id, ticker, trade_date, adj_close]
        """
        table_name = f"market.{'us' if iso_code == 'US' else 'kr'}_stocks_price"

        try:
            table = self.get_table(table_name)
            arrow_table = table.scan(
                selected_fields=("meta_id", "ticker", "trade_date", "adj_close")
            ).to_arrow()

            df = arrow_table.to_pandas()

            if df.empty:
                return pd.DataFrame(columns=["meta_id", "ticker", "trade_date", "adj_close"])

            # 종목별 최신 날짜 데이터만 추출
            idx = df.groupby("meta_id")["trade_date"].idxmax()
            latest_df = df.loc[idx].reset_index(drop=True)

            logger.info(f"최신 가격 조회: {len(latest_df)} 종목 from {table_name}")
            return latest_df

        except Exception as e:
            logger.error(f"최신 가격 조회 실패: {e}", exc_info=True)
            return pd.DataFrame(columns=["meta_id", "ticker", "trade_date", "adj_close"])


# 싱글톤 인스턴스
iceberg_client = IcebergClient()
