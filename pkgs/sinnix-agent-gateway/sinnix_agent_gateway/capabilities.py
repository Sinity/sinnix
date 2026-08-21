from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Capability(StrEnum):
    PROJECT_READ = "project.read"
    PROJECT_WRITE = "project.write"
    JOB_READ = "job.read"
    JOB_START = "job.start"
    JOB_CANCEL = "job.cancel"
    AUDIT_READ = "audit.read"
    ARTIFACT_READ = "artifact.read"
    MACHINE_READ = "machine.read"
    CAPTURE_READ = "capture.read"
    FILE_READ = "file.read"
    FILE_WRITE = "file.write"
    SESSION_READ = "session.read"
    SHELL_QUERY = "shell.query"
    SHELL_RUN = "shell.run"


PRINCIPAL_CAPABILITIES: dict[str, frozenset[Capability]] = {
    "observer": frozenset(
        {
            Capability.PROJECT_READ,
            Capability.JOB_READ,
            Capability.AUDIT_READ,
            Capability.ARTIFACT_READ,
            Capability.MACHINE_READ,
            Capability.CAPTURE_READ,
            Capability.FILE_READ,
            Capability.SESSION_READ,
            Capability.SHELL_QUERY,
        }
    ),
    "agent-control": frozenset(
        {
            Capability.PROJECT_READ,
            Capability.JOB_READ,
            Capability.JOB_START,
            Capability.JOB_CANCEL,
            Capability.AUDIT_READ,
            Capability.ARTIFACT_READ,
            Capability.MACHINE_READ,
            Capability.CAPTURE_READ,
        }
    ),
    "operator": frozenset(Capability),
}


# Holding CAPTURE_READ permits capture queries. The lane table carries
# resource-level authority beyond the capability. None grants every lane under
# captures_root.
PRINCIPAL_LANE_ACCESS: dict[str, frozenset[str] | None] = {
    "observer": None,
    "agent-control": None,
    "operator": None,
}


class PolicyError(ValueError):
    pass


@dataclass(frozen=True)
class Principal:
    name: str
    capabilities: frozenset[Capability]
    allowed_lanes: frozenset[str] | None

    @classmethod
    def for_name(cls, name: str) -> "Principal":
        try:
            capabilities = PRINCIPAL_CAPABILITIES[name]
        except KeyError as exc:
            raise PolicyError(f"unknown gateway principal: {name}") from exc
        if name not in PRINCIPAL_LANE_ACCESS:
            raise PolicyError(
                f"principal {name} has no PRINCIPAL_LANE_ACCESS entry; "
                "add one explicitly (frozenset of lane names, or None for unrestricted)"
            )
        return cls(
            name=name,
            capabilities=capabilities,
            allowed_lanes=PRINCIPAL_LANE_ACCESS[name],
        )

    def require(self, capability: Capability) -> None:
        if capability not in self.capabilities:
            raise PolicyError(
                f"principal {self.name} lacks capability {capability.value}"
            )

    def require_lane(self, lane: str) -> None:
        self.require(Capability.CAPTURE_READ)
        if self.allowed_lanes is not None and lane not in self.allowed_lanes:
            raise PolicyError(
                f"principal {self.name} may not query capture lane {lane!r} "
                f"(allowed: {sorted(self.allowed_lanes)})"
            )

    def filter_lanes(
        self, requested: list[str] | None, available: list[str]
    ) -> list[str]:
        """Resolve a requested lane list against principal authority."""
        self.require(Capability.CAPTURE_READ)
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
