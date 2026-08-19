"""공개됐던 API 키만으로는 개인 데이터를 읽거나 변경할 수 없어야 한다."""

import hashlib

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_protected_route_requires_api_key_and_site_access(monkeypatch):
    access_code = "test-access-code-with-enough-entropy"
    monkeypatch.setenv("API_TOKEN", "test-api-key")
    monkeypatch.setenv("SITE_ACCESS_HASH", hashlib.sha256(access_code.encode()).hexdigest())

    assert client.get("/meta", headers={"X-API-Key": "test-api-key"}).status_code == 401
    assert client.get("/meta", headers={"X-Site-Access": access_code}).status_code == 401

    response = client.get(
        "/meta",
        headers={"X-API-Key": "test-api-key", "X-Site-Access": access_code},
    )
    assert response.status_code != 401


def test_health_remains_public(monkeypatch):
    monkeypatch.setenv("API_TOKEN", "test-api-key")
    assert client.get("/health").status_code == 200
