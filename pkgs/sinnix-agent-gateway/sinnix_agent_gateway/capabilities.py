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


PROFILE_CAPABILITIES: dict[str, frozenset[Capability]] = {
    "remote-readonly": frozenset(
        {
            Capability.PROJECT_READ,
            Capability.JOB_READ,
            Capability.AUDIT_READ,
            Capability.ARTIFACT_READ,
            Capability.MACHINE_READ,
            Capability.CAPTURE_READ,
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
            Capability.CAPTURE_READ,
        }
    ),
    "remote-operator": frozenset(Capability),
}


# sinnix-lpuv: per-pipe data-permission model, screenpipe-inspired. Holding
# CAPTURE_READ (above) means "may query SOME capture lanes"; this table is
# the finer-grained per-lane split PROFILE_CAPABILITIES can't express on its
# own (that dict is profile -> broad category, not profile -> specific
# named resource).
#
# `None` = every lane under captures_root, no restriction (the two
# machine-local/full-trust profiles: local-agent-control never leaves the
# tailnet, remote-operator IS the operator).
#
# `remote-readonly` is the one profile actually reached from outside this
# operator's own control: it's served over the OpenAI Secure MCP Tunnel to
# ChatGPT, a channel this operator does not own end-to-end. The curated set
# below is deliberately narrow -- operational/environmental telemetry with
# no personal-content risk (media metadata, network stats, room sensors,
# display state), never anything that carries message/keystroke/screen/
# audio content. Extend this set only for lanes that pass that same bar.
PROFILE_LANE_ACCESS: dict[str, frozenset[str] | None] = {
    "remote-readonly": frozenset(
        {
            "mpris",  # media-player track/status metadata, not audio content
            "router",  # network telemetry (bandwidth, associations), not traffic content
            "awair",  # room air-quality sensor readings
            "monitor",  # display power/brightness/input-source state
        }
    ),
    "local-agent-control": None,
    "remote-operator": None,
}


class PolicyError(ValueError):
    pass


@dataclass(frozen=True)
class Principal:
    profile: str
    capabilities: frozenset[Capability]
    allowed_lanes: frozenset[str] | None

    @classmethod
    def for_profile(cls, profile: str) -> "Principal":
        try:
            capabilities = PROFILE_CAPABILITIES[profile]
        except KeyError as exc:
            raise PolicyError(f"unknown gateway profile: {profile}") from exc
        # Every profile in PROFILE_CAPABILITIES must also have a lane-access
        # entry -- a profile with CAPTURE_READ but no PROFILE_LANE_ACCESS
        # entry would be an oversight, not an intentional "deny all" (which
        # should be an explicit empty frozenset(), not a missing key), so
        # this is a genuine config error, not a normal deny path.
        if profile not in PROFILE_LANE_ACCESS:
            raise PolicyError(
                f"profile {profile} has no PROFILE_LANE_ACCESS entry -- "
                "add one explicitly (frozenset of lane names, or None for unrestricted)"
            )
        return cls(
            profile=profile,
            capabilities=capabilities,
            allowed_lanes=PROFILE_LANE_ACCESS[profile],
        )

    def require(self, capability: Capability) -> None:
        if capability not in self.capabilities:
            raise PolicyError(
                f"profile {self.profile} lacks capability {capability.value}"
            )

    def require_lane(self, lane: str) -> None:
        self.require(Capability.CAPTURE_READ)
        if self.allowed_lanes is not None and lane not in self.allowed_lanes:
            raise PolicyError(
                f"profile {self.profile} may not query capture lane {lane!r} "
                f"(allowed: {sorted(self.allowed_lanes)})"
            )

    def filter_lanes(self, requested: list[str] | None, available: list[str]) -> list[str]:
        """Resolve the effective lane list for a query: explicit request
        intersected with what's allowed, or the full allowed set when no
        lanes were explicitly requested (never silently defaults to
        "every lane on disk" the way the bare CLI does -- that's exactly
        the permission gap this bead exists to close)."""
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
                f"profile {self.profile} may not query capture lane(s) {denied} "
                f"(allowed: {sorted(universe)})"
            )
        return requested
