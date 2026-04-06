"""
Tests for the Dock Chaos WebSocket Dashboard.
"""

import pytest
from starlette.testclient import TestClient
from dock_chaos.dashboard import dashboard_app, event_log, connected_clients, broadcast_event


@pytest.fixture(autouse=True)
def clear_state():
    event_log.clear()
    connected_clients.clear()
    yield
    event_log.clear()
    connected_clients.clear()


@pytest.fixture
def client():
    return TestClient(dashboard_app)


class TestDashboardHTTP:
    def test_serves_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Dock Chaos" in resp.text

    def test_contains_websocket_js(self, client):
        resp = client.get("/")
        assert "new WebSocket" in resp.text

    def test_contains_stat_boxes(self, client):
        resp = client.get("/")
        assert "Faults Injected" in resp.text
        assert "Recovered" in resp.text
        assert "Avg Recovery" in resp.text

    def test_contains_event_feed(self, client):
        resp = client.get("/")
        assert "Event Feed" in resp.text
        assert "dock-chaos attack --dashboard" in resp.text


class TestDashboardWebSocket:
    def test_websocket_connects(self, client):
        with client.websocket_connect("/ws") as ws:
            assert ws is not None

    def test_websocket_receives_existing_events(self, client):
        event_log.append({"type": "injection", "fault": "container_kill", "target": "app-1"})
        with client.websocket_connect("/ws") as ws:
            data = ws.receive_json()
            assert data["type"] == "injection"
            assert data["fault"] == "container_kill"


class TestBroadcast:
    @pytest.mark.asyncio
    async def test_broadcast_adds_to_log(self):
        assert len(event_log) == 0
        await broadcast_event({"type": "test", "fault": "kill", "target": "x"})
        assert len(event_log) == 1
        assert event_log[0]["type"] == "test"
