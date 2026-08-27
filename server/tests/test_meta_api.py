"""종목 목록은 Lambda 동기 응답 한도 아래의 검색용 계약만 반환한다."""

import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from app.routers import meta


client = TestClient(app)


def test_meta_list_keeps_detail_fields_out_and_payload_bounded(monkeypatch):
    rows = pd.DataFrame(
        [
            {
                "meta_id": i,
                "ticker": f"T{i:05d}",
                "name": f"Example Security {i}",
                "isin": None,
                "security_type": "ETF" if i % 4 == 0 else "STOCK",
                "security_subtype": "ETF" if i % 4 == 0 else "CS",
                "asset_class": "FUND" if i % 4 == 0 else "EQUITY",
                "sector": None,
                "iso_code": "US",
                "marketcap": 1_000_000_000,
                "marketcap_source": "massive_close_x_weighted_shares",
                "marketcap_as_of": "2026-08-26",
                "shares_outstanding": 100_000_000,
                "weighted_shares_outstanding": 99_000_000,
                "fund_size": 1_000_000_000 if i % 4 == 0 else None,
                "fund_size_source": "estimate_close_x_share_class_shares",
                "fund_size_as_of": "2026-08-26",
                "reference_as_of": "2026-08-27",
                "fee": None,
                "remark": None,
            }
            for i in range(16_000)
        ]
    )
    monkeypatch.delenv("API_TOKEN", raising=False)
    monkeypatch.setattr(meta.datastore, "meta_df", lambda: rows)

    response = client.get("/meta")

    assert response.status_code == 200
    assert len(response.content) < 4 * 1024 * 1024
    first = response.json()[0]
    assert first["security_subtype"] in {"ETF", "CS"}
    assert "fund_size" in first
    assert "shares_outstanding" not in first
    assert "marketcap_source" not in first
    assert "reference_as_of" not in first
