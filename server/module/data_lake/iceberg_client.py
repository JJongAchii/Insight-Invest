"""
Iceberg Catalog 싱글톤 클라이언트
"""

from pyiceberg.catalog import load_catalog


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
                }
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


# 싱글톤 인스턴스
iceberg_client = IcebergClient()
