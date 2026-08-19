"""로컬 변형과 Vercel preview는 허용하되 임의 도메인은 허용하지 않는다."""

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _preflight(origin: str):
    return client.options(
        "/holdings",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )


def test_cors_allows_local_and_vercel_preview_origins():
    for origin in (
        "http://127.0.0.1:3001",
        "http://localhost:3000",
        "https://insight-invest-git-review-example.vercel.app",
    ):
        response = _preflight(origin)
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin


def test_cors_rejects_non_vercel_origin():
    for origin in (
        "https://vercel.app.evil.example",
        "https://unrelated-project.vercel.app",
    ):
        response = _preflight(origin)
        assert response.status_code == 400
        assert "access-control-allow-origin" not in response.headers
