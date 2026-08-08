def test_health_is_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "cropmind-api"


def test_readiness_when_database_up(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.health.check_database", lambda: True)
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_readiness_when_database_down(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.health.check_database", lambda: False)
    response = client.get("/health/ready")
    assert response.status_code == 503


def test_request_id_is_returned(client):
    response = client.get("/health")
    assert "x-request-id" in response.headers


def test_openapi_is_served(client):
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 200
