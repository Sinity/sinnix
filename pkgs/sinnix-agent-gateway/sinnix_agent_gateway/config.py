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
class TaskAuthorityConfig:
    owner: str
    workspace: Path
    database: Path
    project_uuid: str | None = None
    publication_policy: str = "local"


@dataclass(frozen=True)
class ProjectConfig:
    project_id: str
    path: Path
    remote: str | None = None
    default_ref: str = "master"
    observer_read: bool = False
    checkout_discovery: str = "git-worktree"
    devtools_entrypoint: str | None = None
    task_authority: TaskAuthorityConfig | None = None


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
            task_authority_row = row.get("taskAuthority")
            task_authority: TaskAuthorityConfig | None = None
            if task_authority_row is not None:
                if not isinstance(task_authority_row, dict):
                    raise ValueError(f"project {project_id} taskAuthority must be an object")
                allowed_authority_fields = {
                    "owner",
                    "workspace",
                    "database",
                    "projectUuid",
                    "publicationPolicy",
                }
                unsupported_authority_fields = set(task_authority_row).difference(
                    allowed_authority_fields
                )
                if unsupported_authority_fields:
                    fields = ", ".join(sorted(unsupported_authority_fields))
                    raise ValueError(
                        f"project {project_id} taskAuthority has unsupported field(s): {fields}"
                    )
                owner = task_authority_row.get("owner")
                workspace = task_authority_row.get("workspace")
                database = task_authority_row.get("database")
                if owner != "beads":
                    raise ValueError(
                        f"project {project_id} taskAuthority owner must be 'beads'"
                    )
                if not isinstance(workspace, str) or not workspace:
                    raise ValueError(
                        f"project {project_id} taskAuthority workspace must be a path"
                    )
                if not isinstance(database, str) or not database:
                    raise ValueError(
                        f"project {project_id} taskAuthority database must be a path"
                    )
                project_uuid = task_authority_row.get("projectUuid")
                if project_uuid is not None and (
                    not isinstance(project_uuid, str) or not project_uuid
                ):
                    raise ValueError(
                        f"project {project_id} taskAuthority projectUuid must be a string"
                    )
                publication_policy = task_authority_row.get("publicationPolicy", "local")
                if publication_policy not in {"local", "dolt-sync"}:
                    raise ValueError(
                        f"project {project_id} taskAuthority publicationPolicy is invalid"
                    )
                task_authority = TaskAuthorityConfig(
                    owner=owner,
                    workspace=Path(workspace).resolve(),
                    database=Path(database).resolve(),
                    project_uuid=project_uuid,
                    publication_policy=publication_policy,
                )
            checkout_discovery = row.get("checkoutDiscovery", "git-worktree")
            if checkout_discovery != "git-worktree":
                raise ValueError(
                    f"project {project_id} checkoutDiscovery must be 'git-worktree'"
                )
            devtools_entrypoint = row.get("devtoolsEntrypoint")
            if devtools_entrypoint is not None and (
                not isinstance(devtools_entrypoint, str) or not devtools_entrypoint
            ):
                raise ValueError(
                    f"project {project_id} devtoolsEntrypoint must be a string"
                )
            projects[project_id] = ProjectConfig(
                project_id=project_id,
                path=Path(row["path"]).resolve(),
                remote=row.get("remote"),
                default_ref=row.get("defaultRef", "master"),
                observer_read=bool(row.get("observerRead", False)),
                checkout_discovery=checkout_discovery,
                devtools_entrypoint=devtools_entrypoint,
                task_authority=task_authority,
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
        )

    def initialize_state(self) -> None:
        for path in (
            self.state_dir,
            self.state_dir / "audit",
            self.state_dir / "artifacts",
            self.state_dir / "captures",
            self.state_dir / "diagnostics",
            self.state_dir / "jobs",
            self.state_dir / "legacy",
            self.state_dir / "results",
        ):
            path.mkdir(mode=0o700, parents=True, exist_ok=True)
            path.chmod(0o700)
