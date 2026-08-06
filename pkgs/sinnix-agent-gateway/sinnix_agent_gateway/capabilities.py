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


PROFILE_CAPABILITIES: dict[str, frozenset[Capability]] = {
    "remote-readonly": frozenset(
        {
            Capability.PROJECT_READ,
            Capability.JOB_READ,
            Capability.AUDIT_READ,
            Capability.ARTIFACT_READ,
            Capability.MACHINE_READ,
        }
    ),
    "local-agent-control": frozenset(
        {
            Capability.PROJECT_READ,
            Capability.JOB_READ,
            Capability.JOB_START,
            Capability.JOB_CANCEL,
            Capability.AUDIT_READ,
            Capability.ARTIFACT_READ,
            Capability.MACHINE_READ,
        }
    ),
    "remote-operator": frozenset(Capability),
}


class PolicyError(ValueError):
    pass


@dataclass(frozen=True)
class Principal:
    profile: str
    capabilities: frozenset[Capability]

    @classmethod
    def for_profile(cls, profile: str) -> "Principal":
        try:
            capabilities = PROFILE_CAPABILITIES[profile]
        except KeyError as exc:
            raise PolicyError(f"unknown gateway profile: {profile}") from exc
        return cls(profile=profile, capabilities=capabilities)

    def require(self, capability: Capability) -> None:
        if capability not in self.capabilities:
            raise PolicyError(
                f"profile {self.profile} lacks capability {capability.value}"
            )
