"""
Chaos Engine — Core orchestration for fault injection and recovery monitoring.
"""

import asyncio
import time
import random
from typing import Optional
from dock_chaos.docker_client import DockerManager
from dock_chaos.faults import (
    ContainerKillFault,
    PauseFault,
    MemoryStressFault,
    NetworkPartitionFault,
)


FAULT_CLASSES = [ContainerKillFault, PauseFault, MemoryStressFault, NetworkPartitionFault]

INTENSITY_MAP = {
    "low": 1,
    "medium": 3,
    "high": 999,  # continuous
}


class ChaosResult:
    """Stores the result of a single fault injection."""

    def __init__(self, fault_name: str, target: str):
        self.fault_name = fault_name
        self.target = target
        self.injected_at: float = 0
        self.recovered_at: Optional[float] = None
        self.recovery_time_ms: Optional[float] = None
        self.recovered: bool = False
        self.error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "fault": self.fault_name,
            "target": self.target,
            "recovery_time_ms": self.recovery_time_ms,
            "recovered": self.recovered,
            "error": self.error,
        }


class ChaosEngine:
    """Orchestrates fault injection against Docker Compose services."""

    def __init__(self, project_name: Optional[str] = None, target_service: Optional[str] = None):
        self.docker = DockerManager()
        self.project_name = project_name
        self.target_service = target_service
        self.results: list[ChaosResult] = []

    def discover_services(self) -> list[dict]:
        """Find all running Docker Compose services."""
        containers = self.docker.list_compose_containers(self.project_name)
        services = []
        for c in containers:
            services.append({
                "name": c.name,
                "image": c.image.tags[0] if c.image.tags else "unknown",
                "status": c.status,
                "id": c.short_id,
                "ports": str(c.ports) if c.ports else "none",
            })
        return services

    def _pick_targets(self, services: list[dict]) -> list[dict]:
        """Select target services for fault injection."""
        if self.target_service:
            targets = [s for s in services if self.target_service in s["name"]]
            if not targets:
                raise ValueError(f"Target service '{self.target_service}' not found")
            return targets
        return services

    async def run_chaos(self, duration: int = 60, intensity: str = "medium") -> list[ChaosResult]:
        """Run a chaos attack for the specified duration."""
        services = self.discover_services()
        targets = self._pick_targets(services)
        max_faults = INTENSITY_MAP[intensity]
        fault_count = 0
        start_time = time.time()

        while time.time() - start_time < duration and fault_count < max_faults:
            # Pick random target and fault type
            target = random.choice(targets)
            fault_class = random.choice(FAULT_CLASSES)
            fault = fault_class(self.docker)

            result = ChaosResult(fault_name=fault.name, target=target["name"])
            result.injected_at = time.time()

            try:
                container = self.docker.get_container(target["name"])

                # Inject fault
                fault.inject(container)

                # Wait briefly then check recovery
                await asyncio.sleep(fault.recovery_wait_seconds)

                # Recover (if fault requires explicit recovery)
                fault.recover(container)

                # Monitor recovery
                recovery_start = time.time()
                recovered = await self._wait_for_recovery(
                    target["name"], timeout=30
                )

                if recovered:
                    result.recovered = True
                    result.recovered_at = time.time()
                    result.recovery_time_ms = round(
                        (result.recovered_at - recovery_start) * 1000, 2
                    )
                else:
                    result.recovered = False
                    result.error = "Service did not recover within 30s timeout"

            except Exception as e:
                result.recovered = False
                result.error = str(e)

            self.results.append(result)
            fault_count += 1

            # Brief pause between faults
            if fault_count < max_faults and time.time() - start_time < duration:
                await asyncio.sleep(2)

        return self.results

    async def _wait_for_recovery(self, container_name: str, timeout: int = 30) -> bool:
        """Poll container health until it recovers or times out."""
        start = time.time()
        while time.time() - start < timeout:
            try:
                container = self.docker.get_container(container_name)
                if container.status == "running":
                    # Check if container is actually responding
                    health = container.attrs.get("State", {}).get("Health", {})
                    health_status = health.get("Status", "none")

                    # If no health check configured, running = recovered
                    if health_status == "none" or health_status == "healthy":
                        return True
                    # If health check exists but unhealthy, keep waiting
                    elif health_status == "unhealthy":
                        await asyncio.sleep(0.5)
                        continue
                    else:
                        return True
                else:
                    await asyncio.sleep(0.5)
            except Exception:
                await asyncio.sleep(0.5)
        return False
