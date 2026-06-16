"""
pytest conftest — backend smoke tests용 공통 fixture.

backend 서버가 port 8000에서 실행 중이어야 함.
fixture는 httpx Client 제공 + 새 session 생성.
"""
import pytest
import httpx


BASE_URL = "http://localhost:8000"


@pytest.fixture(scope="session")
def client():
    """전체 session 동안 공유되는 httpx Client."""
    with httpx.Client(base_url=BASE_URL, timeout=10) as c:
        yield c


@pytest.fixture
def session_id(client):
    """각 테스트마다 새 session_id 발급."""
    r = client.post("/api/analysis/sessions", json={"user_id": "pytest"})
    assert r.status_code == 200, f"session 생성 실패: {r.status_code}"
    return r.json()["session_id"]
