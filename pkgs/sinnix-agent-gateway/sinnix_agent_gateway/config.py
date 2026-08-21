from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
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


def default_ops_socket_path() -> Path:
    return Path(os.environ.get("XDG_RUNTIME_DIR", "/run/user/1000")) / "sinnix" / "ops.sock"


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
    capability_index: Path = Path("/etc/sinnix/capability-index.json")
    agent_runner: Path = DEFAULT_AGENT_RUNNER
    agent_controller: Path = DEFAULT_AGENT_CONTROLLER
    agent_scope_exec_command: str = "sinnix-agent-scope-exec"
    execution_job_command: str = "sinnix-agent-gateway-execution-job"
    observe_command: str = "sinnix-observe"
    max_result_bytes: int = 262_144
    approved_manifest_hash: str | None = None
    approved_manifest_principal: str = "observer"
    connector_snapshot_path: Path | None = None
    systemd_run_command: str = "systemd-run"
    systemctl_command: str = "systemctl"
    ops_socket_path: Path = field(default_factory=default_ops_socket_path)
    hypr_control_command: str = "sinnix-hypr-control"
    screenshot_control_command: str = "sinnix-screenshot-control"
    kitty_control_command: str = "sinnix-kitty-control"
    chrome_control_command: str = "sinnix-chrome-control"
    beads_command: str = "bd"
    mcp_broker_servers: dict[str, dict[str, Any]] = field(default_factory=dict)
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
        broker_servers = raw.get("mcpBrokerServers", {})
        if not isinstance(broker_servers, dict) or any(
            not isinstance(name, str) or not isinstance(server, dict)
            for name, server in broker_servers.items()
        ):
            raise ValueError("mcpBrokerServers must map names to objects")
        return cls(
            state_dir=state_dir,
            projects=projects,
            runtime_inventory=Path(
                raw.get("runtimeInventory", "/etc/sinnix/runtime-inventory.json")
            ),
            capability_index=Path(
                raw.get("capabilityIndex", "/etc/sinnix/capability-index.json")
            ),
            agent_runner=Path(raw.get("agentRunner", DEFAULT_AGENT_RUNNER)),
            agent_controller=Path(raw.get("agentController", DEFAULT_AGENT_CONTROLLER)),
            agent_scope_exec_command=raw.get(
                "agentScopeExecCommand", "sinnix-agent-scope-exec"
            ),
            execution_job_command=raw.get(
                "executionJobCommand", "sinnix-agent-gateway-execution-job"
            ),
            observe_command=raw.get("observeCommand", "sinnix-observe"),
            max_result_bytes=int(raw.get("maxResultBytes", 262_144)),
            approved_manifest_hash=raw.get("approvedManifestHash"),
            approved_manifest_principal=raw.get(
                "approvedManifestPrincipal", "observer"
            ),
            connector_snapshot_path=Path(raw["connectorSnapshotPath"])
            if "connectorSnapshotPath" in raw
            else None,
            systemd_run_command=raw.get("systemdRunCommand", "systemd-run"),
            systemctl_command=raw.get("systemctlCommand", "systemctl"),
            ops_socket_path=Path(raw.get("opsSocketPath", default_ops_socket_path())),
            hypr_control_command=raw.get("hyprControlCommand", "sinnix-hypr-control"),
            screenshot_control_command=raw.get(
                "screenshotControlCommand", "sinnix-screenshot-control"
            ),
            kitty_control_command=raw.get("kittyControlCommand", "sinnix-kitty-control"),
            chrome_control_command=raw.get("chromeControlCommand", "sinnix-chrome-control"),
            beads_command=raw.get("beadsCommand", "bd"),
            mcp_broker_servers=broker_servers,
            capture_command=raw.get("captureCommand", "sinnix-capture"),
            captures_root=Path(raw.get("capturesRoot", "/realm/data/captures")),
        )

    def initialize_state(self) -> None:
        for path in (
            self.state_dir,
            self.state_dir / "audit",
            self.state_dir / "artifacts",
            self.state_dir / "captures",
            self.state_dir / "jobs",
            self.state_dir / "legacy",
        ):
            path.mkdir(mode=0o700, parents=True, exist_ok=True)
            path.chmod(0o700)
