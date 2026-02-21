from fastapi.testclient import TestClient
from api_server import app

client = TestClient(app)

def test_read_metrics():
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "miniwow_online_devices" in response.text

def test_read_status():
    response = client.get("/api/v1/status")
    assert response.status_code == 200
    data = response.json()
    assert "rows" in data
    assert "summary" in data
