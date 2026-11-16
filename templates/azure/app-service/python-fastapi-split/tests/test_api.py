from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health_reports_the_revision():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "revision": "development"}


def test_ready():
    assert client.get("/ready").json() == {"status": "ready"}


def test_hello_runs_the_use_case():
    body = client.get("/hello", params={"name": "Ada"}).json()
    assert body["message"] == "Hello, Ada!" and body["name"] == "Ada" and body["at"].endswith("+00:00")


def test_hello_rejects_an_invalid_name():
    assert client.get("/hello", params={"name": "x" * 65}).status_code == 422
