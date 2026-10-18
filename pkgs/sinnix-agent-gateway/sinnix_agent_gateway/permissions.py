from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Permission(StrEnum):
    PROJECT_READ = "project.read"
    PROJECT_WRITE = "project.write"
    JOB_READ = "job.read"
    JOB_START = "job.start"
    JOB_CANCEL = "job.cancel"
    AUDIT_READ = "audit.read"
    ARTIFACT_READ = "artifact.read"
    MACHINE_READ = "machine.read"
    MACHINE_ACTION = "machine.action"
    DESKTOP_READ = "desktop.read"
    DESKTOP_ACTION = "desktop.action"
    TERMINAL_READ = "terminal.read"
    TERMINAL_ACTION = "terminal.action"
    BROWSER_READ = "browser.read"
    BROWSER_ACTION = "browser.action"
    CAPABILITY_READ = "capability.read"
    CAPTURE_READ = "capture.read"
    FILE_READ = "file.read"
    FILE_WRITE = "file.write"
    SESSION_READ = "session.read"
    SHELL_RUN = "shell.run"
    TASK_READ = "task.read"
    TASK_WRITE = "task.write"
    MCP_READ = "mcp.read"
    MCP_WRITE = "mcp.write"


ROLE_PERMISSIONS: dict[str, frozenset[Permission]] = {
    "operator": frozenset(Permission),
}


# Holding CAPTURE_READ permits capture queries. The runtime inventory's lane
# table carries resource-level authority beyond this permission.
PRINCIPAL_LANE_ACCESS: dict[str, frozenset[str] | None] = {
    "operator": None,
}


class PolicyError(ValueError):
    pass


@dataclass(frozen=True)
class Principal:
    name: str
    permissions: frozenset[Permission]
    allowed_lanes: frozenset[str] | None

    @classmethod
    def for_name(cls, name: str) -> "Principal":
        try:
            permissions = ROLE_PERMISSIONS[name]
        except KeyError as exc:
            raise PolicyError(f"unknown gateway principal: {name}") from exc
        if name not in PRINCIPAL_LANE_ACCESS:
            raise PolicyError(
                f"principal {name} has no PRINCIPAL_LANE_ACCESS entry; "
                "add one explicitly (frozenset of lane names, or None for unrestricted)"
            )
        return cls(
            name=name,
            permissions=permissions,
            allowed_lanes=PRINCIPAL_LANE_ACCESS[name],
        )

    def require(self, permission: Permission) -> None:
        if permission not in self.permissions:
            raise PolicyError(
                f"principal {self.name} lacks permission {permission.value}"
            )

    def require_lane(self, lane: str) -> None:
        self.require(Permission.CAPTURE_READ)
        if self.allowed_lanes is not None and lane not in self.allowed_lanes:
            raise PolicyError(
                f"principal {self.name} may not query capture lane {lane!r} "
                f"(allowed: {sorted(self.allowed_lanes)})"
            )

    def filter_lanes(
        self, requested: list[str] | None, available: list[str]
    ) -> list[str]:
        """Resolve a requested lane list against principal authority."""
        self.require(Permission.CAPTURE_READ)
        if self.allowed_lanes is None:
            universe = available
        else:
            universe = [lane for lane in available if lane in self.allowed_lanes]
        if requested is None:
            return universe
        denied = [lane for lane in requested if lane not in universe]
        if denied:
            raise PolicyError(
                f"principal {self.name} may not query capture lane(s) {denied} "
                f"(allowed: {sorted(universe)})"
            )
        return requested
