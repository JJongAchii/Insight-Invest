"""공개됐던 API 키만으로는 개인 데이터를 읽거나 변경할 수 없어야 한다."""

import hashlib

import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from datastore import meta

client = TestClient(app)


def test_protected_route_requires_api_key_and_site_access(monkeypatch, tmp_path):
    access_code = "test-access-code-with-enough-entropy"
    monkeypatch.setenv("API_TOKEN", "test-api-key")
    monkeypatch.setenv("SITE_ACCESS_HASH", hashlib.sha256(access_code.encode()).hexdigest())
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    pd.DataFrame(
        [
            {
                "meta_id": 1,
                "ticker": "SPY",
                "name": "SPDR S&P 500 ETF Trust",
                "isin": None,
                "security_type": "ETF",
                "asset_class": "FUND",
                "sector": None,
                "iso_code": "US",
                "marketcap": None,
                "fee": None,
                "remark": None,
                "min_date": None,
                "max_date": None,
                "as_of": "2026-08-20",
            }
        ]
    ).to_parquet(tmp_path / "asset_master.parquet", index=False)
    meta._meta_for_bucket.cache_clear()

    assert client.get("/meta", headers={"X-API-Key": "test-api-key"}).status_code == 401
    assert client.get("/meta", headers={"X-Site-Access": access_code}).status_code == 401

    response = client.get(
        "/meta",
        headers={"X-API-Key": "test-api-key", "X-Site-Access": access_code},
    )
    assert response.status_code != 401
    meta._meta_for_bucket.cache_clear()


def test_health_remains_public(monkeypatch):
    monkeypatch.setenv("API_TOKEN", "test-api-key")
    assert client.get("/health").status_code == 200
