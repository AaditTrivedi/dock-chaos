"""
Test Suite for Dock Chaos
==========================
Unit tests with mocked Docker interactions.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from dock_chaos.engine import ChaosEngine, ChaosResult
from dock_chaos.faults import ContainerKillFault, PauseFault, MemoryStressFault, NetworkPartitionFault
from dock_chaos.reporter import ReportGenerator
from dock_chaos.docker_client import DockerManager


# ─── Mock Helpers ────────────────────────────────────────────────────────────

def make_mock_container(name="test-app-1", status="running", image_tags=None, ports=None):
    container = MagicMock()
    container.name = name
    container.status = status
    container.short_id = "abc123"
    container.ports = ports or {}
    container.image.tags = image_tags or ["test-image:latest"]
    container.attrs = {"State": {"Health": {"Status": "none"}}, "NetworkSettings": {"Networks": {}}}
    container.reload = MagicMock()
    return container


def make_mock_docker_manager():
    mgr = MagicMock(spec=DockerManager)
    mgr.client = MagicMock()
    return mgr


# ─── Tests: ChaosResult ─────────────────────────────────────────────────────

class TestChaosResult:
    def test_to_dict_recovered(self):
        r = ChaosResult(fault_name="container_kill", target="redis")
        r.recovered = True
        r.recovery_time_ms = 150.5
        d = r.to_dict()
        assert d["fault"] == "container_kill"
        assert d["target"] == "redis"
        assert d["recovered"] is True
        assert d["recovery_time_ms"] == 150.5

    def test_to_dict_failed(self):
        r = ChaosResult(fault_name="network_partition", target="db")
        r.recovered = False
        r.error = "Timeout"
        d = r.to_dict()
        assert d["recovered"] is False
        assert d["error"] == "Timeout"


# ─── Tests: ContainerKillFault ───────────────────────────────────────────────

class TestContainerKillFault:
    def test_inject_calls_kill(self):
        mgr = make_mock_docker_manager()
        fault = ContainerKillFault(mgr)
        container = make_mock_container()
        fault.inject(container)
        mgr.kill_container.assert_called_once_with(container)

    def test_recover_restarts_if_not_running(self):
        mgr = make_mock_docker_manager()
        fault = ContainerKillFault(mgr)
        container = make_mock_container(status="exited")
        fault.recover(container)
        mgr.restart_container.assert_called_once_with(container)

    def test_name(self):
        mgr = make_mock_docker_manager()
        fault = ContainerKillFault(mgr)
        assert fault.name == "container_kill"


# ─── Tests: PauseFault ───────────────────────────────────────────────────────

class TestPauseFault:
    def test_inject_calls_pause(self):
        mgr = make_mock_docker_manager()
        fault = PauseFault(mgr)
        container = make_mock_container()
        fault.inject(container)
        mgr.pause_container.assert_called_once_with(container)

    def test_recover_unpauses(self):
        mgr = make_mock_docker_manager()
        fault = PauseFault(mgr)
        container = make_mock_container(status="paused")
        fault.recover(container)
        mgr.unpause_container.assert_called_once_with(container)

    def test_recover_skips_if_not_paused(self):
        mgr = make_mock_docker_manager()
        fault = PauseFault(mgr)
        container = make_mock_container(status="running")
        fault.recover(container)
        mgr.unpause_container.assert_not_called()


# ─── Tests: MemoryStressFault ────────────────────────────────────────────────

class TestMemoryStressFault:
    def test_inject_execs_command(self):
        mgr = make_mock_docker_manager()
        fault = MemoryStressFault(mgr)
        container = make_mock_container()
        fault.inject(container)
        mgr.exec_in_container.assert_called_once()

    def test_recover_cleans_up(self):
        mgr = make_mock_docker_manager()
        fault = MemoryStressFault(mgr)
        container = make_mock_container()
        fault.recover(container)
        mgr.exec_in_container.assert_called_once()


# ─── Tests: NetworkPartitionFault ────────────────────────────────────────────

class TestNetworkPartitionFault:
    def test_inject_disconnects_networks(self):
        mgr = make_mock_docker_manager()
        fault = NetworkPartitionFault(mgr)
        container = make_mock_container()
        container.attrs = {
            "State": {"Health": {"Status": "none"}},
            "NetworkSettings": {"Networks": {"mynet": {}}}
        }
        mock_network = MagicMock()
        mgr.client.networks.get.return_value = mock_network

        fault.inject(container)

        mock_network.disconnect.assert_called_once_with(container)
        assert "mynet" in fault._disconnected_networks

    def test_recover_reconnects(self):
        mgr = make_mock_docker_manager()
        fault = NetworkPartitionFault(mgr)
        fault._disconnected_networks = ["mynet"]
        container = make_mock_container()
        mock_network = MagicMock()
        mgr.client.networks.get.return_value = mock_network

        fault.recover(container)

        mock_network.connect.assert_called_once_with(container)
        assert fault._disconnected_networks == []

    def test_skips_bridge_network(self):
        mgr = make_mock_docker_manager()
        fault = NetworkPartitionFault(mgr)
        container = make_mock_container()
        container.attrs = {
            "State": {"Health": {"Status": "none"}},
            "NetworkSettings": {"Networks": {"bridge": {}}}
        }

        fault.inject(container)
        mgr.client.networks.get.assert_not_called()


# ─── Tests: ChaosEngine Discovery ───────────────────────────────────────────

class TestChaosEngineDiscovery:
    def test_discover_services(self):
        with patch.object(DockerManager, "__init__", lambda self: None):
            engine = ChaosEngine()
            engine.docker = make_mock_docker_manager()
            engine.docker.list_compose_containers.return_value = [
                make_mock_container("app-1"),
                make_mock_container("redis-1"),
            ]

            services = engine.discover_services()
            assert len(services) == 2
            assert services[0]["name"] == "app-1"
            assert services[1]["name"] == "redis-1"

    def test_discover_empty(self):
        with patch.object(DockerManager, "__init__", lambda self: None):
            engine = ChaosEngine()
            engine.docker = make_mock_docker_manager()
            engine.docker.list_compose_containers.return_value = []

            services = engine.discover_services()
            assert len(services) == 0


# ─── Tests: ReportGenerator ──────────────────────────────────────────────────

class TestReportGenerator:
    def _make_results(self):
        r1 = ChaosResult("container_kill", "app-1")
        r1.recovered = True
        r1.recovery_time_ms = 150
        r2 = ChaosResult("network_partition", "redis-1")
        r2.recovered = False
        r2.error = "Timeout after 30s"
        return [r1, r2]

    def _make_services(self):
        return [
            {"name": "app-1", "image": "app:latest", "status": "running"},
            {"name": "redis-1", "image": "redis:7", "status": "running"},
        ]

    def test_summary_output(self):
        rg = ReportGenerator(self._make_results(), self._make_services())
        summary = rg.generate_summary()
        assert "Total faults injected:  2" in summary
        assert "Services recovered:     1/2" in summary
        assert "Services failed:        1/2" in summary

    def test_markdown_contains_table(self):
        rg = ReportGenerator(self._make_results(), self._make_services())
        md = rg.generate_markdown()
        assert "# Dock Chaos" in md
        assert "container_kill" in md
        assert "network_partition" in md
        assert "Timeout after 30s" in md

    def test_score_excellent(self):
        r = ChaosResult("kill", "app")
        r.recovered = True
        r.recovery_time_ms = 100
        rg = ReportGenerator([r], [])
        assert "A" in rg._score()

    def test_score_critical(self):
        r = ChaosResult("kill", "app")
        r.recovered = False
        rg = ReportGenerator([r], [])
        assert "F" in rg._score()

    def test_score_no_results(self):
        rg = ReportGenerator([], [])
        assert rg._score() == "N/A"

    def test_empty_results_summary(self):
        rg = ReportGenerator([], [])
        assert "No faults" in rg.generate_summary()

    def test_recommendations_all_passed(self):
        r = ChaosResult("kill", "app")
        r.recovered = True
        r.recovery_time_ms = 100
        rg = ReportGenerator([r], [])
        md = rg.generate_markdown()
        assert "All services recovered" in md

    def test_recommendations_with_failures(self):
        r = ChaosResult("kill", "app")
        r.recovered = False
        r.error = "Crashed"
        rg = ReportGenerator([r], [])
        md = rg.generate_markdown()
        assert "health checks" in md
