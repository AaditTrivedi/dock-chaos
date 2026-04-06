"""
Fault Injectors — Each class implements a specific type of chaos injection.
"""

from abc import ABC, abstractmethod
from docker.models.containers import Container
from dock_chaos.docker_client import DockerManager


class BaseFault(ABC):
    """Base class for all fault types."""

    name: str = "base"
    description: str = ""
    recovery_wait_seconds: float = 3

    def __init__(self, docker_manager: DockerManager):
        self.docker = docker_manager

    @abstractmethod
    def inject(self, container: Container) -> None:
        """Inject the fault into the target container."""
        pass

    def recover(self, container: Container) -> None:
        """Recover from the fault (override if explicit recovery needed)."""
        pass


class ContainerKillFault(BaseFault):
    """Kills a container with SIGKILL, simulating a sudden crash."""

    name = "container_kill"
    description = "Kills the container process (SIGKILL), simulating a sudden crash"
    recovery_wait_seconds = 2

    def inject(self, container: Container) -> None:
        self.docker.kill_container(container)

    def recover(self, container: Container) -> None:
        # Docker Compose restart policy should handle this
        # If not, we restart manually
        try:
            container.reload()
            if container.status != "running":
                self.docker.restart_container(container)
        except Exception:
            self.docker.restart_container(container)


class PauseFault(BaseFault):
    """Pauses all processes in a container, simulating a freeze/hang."""

    name = "process_pause"
    description = "Freezes all processes in the container, simulating a hang"
    recovery_wait_seconds = 5

    def inject(self, container: Container) -> None:
        self.docker.pause_container(container)

    def recover(self, container: Container) -> None:
        try:
            container.reload()
            if container.status == "paused":
                self.docker.unpause_container(container)
        except Exception:
            pass


class MemoryStressFault(BaseFault):
    """
    Allocates memory inside the container to simulate memory pressure.
    Falls back to a no-op if the container doesn't have the required tools.
    """

    name = "memory_stress"
    description = "Allocates memory inside the container to simulate memory pressure"
    recovery_wait_seconds = 5

    def inject(self, container: Container) -> None:
        # Try to stress memory using Python (most containers have it)
        # or dd as a fallback. If neither works, this is a soft fault.
        try:
            self.docker.exec_in_container(
                container,
                "sh -c 'head -c 50M /dev/urandom > /tmp/chaos_mem_stress 2>/dev/null || true'"
            )
        except Exception:
            pass  # Soft fault — some containers won't support this

    def recover(self, container: Container) -> None:
        try:
            self.docker.exec_in_container(
                container,
                "sh -c 'rm -f /tmp/chaos_mem_stress 2>/dev/null || true'"
            )
        except Exception:
            pass


class NetworkPartitionFault(BaseFault):
    """
    Disconnects a container from its network, simulating a network partition.
    """

    name = "network_partition"
    description = "Disconnects the container from its Docker network"
    recovery_wait_seconds = 5

    def __init__(self, docker_manager: DockerManager):
        super().__init__(docker_manager)
        self._disconnected_networks: list[str] = []

    def inject(self, container: Container) -> None:
        container.reload()
        networks = container.attrs.get("NetworkSettings", {}).get("Networks", {})
        self._disconnected_networks = []

        for net_name in networks:
            if net_name == "bridge":
                continue  # Don't disconnect from default bridge
            try:
                network = self.docker.client.networks.get(net_name)
                network.disconnect(container)
                self._disconnected_networks.append(net_name)
            except Exception:
                pass

    def recover(self, container: Container) -> None:
        container.reload()
        for net_name in self._disconnected_networks:
            try:
                network = self.docker.client.networks.get(net_name)
                network.connect(container)
            except Exception:
                pass
        self._disconnected_networks = []
