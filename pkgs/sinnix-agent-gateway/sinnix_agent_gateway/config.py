from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_AGENT_RUNNER = Path(
    "/home/sinity/.config/hermes/skills/agent-orchestration/scripts/run_agent_prompt.sh"
)
DEFAULT_AGENT_CONTROLLER = Path(
    "/home/sinity/.config/hermes/skills/agent-orchestration/scripts/agent_job_control.sh"
)


def default_state_dir() -> Path:
    base = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state")))
    return base / "sinnix" / "agent-gateway"


@dataclass(frozen=True)
class ProjectConfig:
    project_id: str
    path: Path
    remote: str | None = None
    default_ref: str = "master"
    observer_read: bool = False


@dataclass(frozen=True)
class GatewayConfig:
    state_dir: Path
    projects: dict[str, ProjectConfig]
    runtime_inventory: Path = Path("/etc/sinnix/runtime-inventory.json")
    agent_runner: Path = DEFAULT_AGENT_RUNNER
    agent_controller: Path = DEFAULT_AGENT_CONTROLLER
    observe_command: str = "sinnix-observe"
    max_result_bytes: int = 262_144
    approved_manifest_hash: str | None = None
    capture_command: str = "sinnix-capture"
    captures_root: Path = Path("/realm/data/captures")

    @classmethod
    def load(cls, path: Path | None) -> "GatewayConfig":
        if path is None:
            raw: dict[str, Any] = {}
        else:
            raw = json.loads(path.read_text())
        projects: dict[str, ProjectConfig] = {}
        for project_id, row in raw.get("projects", {}).items():
            obsolete = {"remoteRead", "remoteWrite"}.intersection(row)
            if obsolete:
                fields = ", ".join(sorted(obsolete))
                raise ValueError(
                    f"project {project_id} uses retired gateway field(s): {fields}; "
                    "use observerRead"
                )
            projects[project_id] = ProjectConfig(
                project_id=project_id,
                path=Path(row["path"]).resolve(),
                remote=row.get("remote"),
                default_ref=row.get("defaultRef", "master"),
                observer_read=bool(row.get("observerRead", False)),
            )
        state_dir = Path(raw.get("stateDir", default_state_dir())).expanduser()
        return cls(
            state_dir=state_dir,
            projects=projects,
            runtime_inventory=Path(
                raw.get("runtimeInventory", "/etc/sinnix/runtime-inventory.json")
            ),
            agent_runner=Path(raw.get("agentRunner", DEFAULT_AGENT_RUNNER)),
            agent_controller=Path(raw.get("agentController", DEFAULT_AGENT_CONTROLLER)),
            observe_command=raw.get("observeCommand", "sinnix-observe"),
            max_result_bytes=int(raw.get("maxResultBytes", 262_144)),
            approved_manifest_hash=raw.get("approvedManifestHash"),
            capture_command=raw.get("captureCommand", "sinnix-capture"),
            captures_root=Path(raw.get("capturesRoot", "/realm/data/captures")),
        )

    def initialize_state(self) -> None:
        for path in (
            self.state_dir,
            self.state_dir / "audit",
            self.state_dir / "artifacts",
            self.state_dir / "jobs",
            self.state_dir / "legacy",
        ):
            path.mkdir(mode=0o700, parents=True, exist_ok=True)
            path.chmod(0o700)
