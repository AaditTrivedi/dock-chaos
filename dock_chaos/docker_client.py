"""
Docker Manager — Wraps the Docker SDK for container discovery and manipulation.
"""

import docker
from docker.models.containers import Container


class DockerManager:
    """Manages Docker API interactions."""

    def __init__(self):
        try:
            self.client = docker.from_env()
            self.client.ping()
        except docker.errors.DockerException as e:
            raise RuntimeError(
                "Cannot connect to Docker. Make sure Docker Desktop is running."
            ) from e

    def list_compose_containers(self, project_name: str = None) -> list[Container]:
        """List all containers belonging to a Docker Compose project."""
        filters = {}
        if project_name:
            filters["label"] = [f"com.docker.compose.project={project_name}"]
        else:
            # Get all compose-managed containers
            filters["label"] = ["com.docker.compose.project"]

        return self.client.containers.list(filters=filters)

    def get_container(self, name: str) -> Container:
        """Get a container by name, refreshing its state."""
        containers = self.client.containers.list(all=True, filters={"name": name})
        if not containers:
            raise ValueError(f"Container '{name}' not found")
        # Reload to get fresh state
        containers[0].reload()
        return containers[0]

    def kill_container(self, container: Container) -> None:
        """Kill a container with SIGKILL."""
        container.kill()

    def restart_container(self, container: Container) -> None:
        """Restart a container."""
        container.restart(timeout=10)

    def pause_container(self, container: Container) -> None:
        """Pause a container (freeze all processes)."""
        container.pause()

    def unpause_container(self, container: Container) -> None:
        """Unpause a container."""
        container.unpause()

    def exec_in_container(self, container: Container, command: str) -> str:
        """Execute a command inside a running container."""
        exit_code, output = container.exec_run(command)
        return output.decode("utf-8", errors="replace")
