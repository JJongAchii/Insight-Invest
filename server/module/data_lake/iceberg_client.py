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


# 싱글톤 인스턴스
iceberg_client = IcebergClient()
