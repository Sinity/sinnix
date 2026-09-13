from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_MCP_CALL_TIMEOUT_SECONDS = 30
MAX_MCP_CALL_TIMEOUT_SECONDS = 3_600


def validate_mcp_call_timeout(value: Any) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or not 1 <= value <= MAX_MCP_CALL_TIMEOUT_SECONDS
    ):
        raise ValueError(
            "callTimeoutSeconds must be an integer "
            f"between 1 and {MAX_MCP_CALL_TIMEOUT_SECONDS}"
        )
    return value


def default_state_dir() -> Path:
    base = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state")))
    return base / "sinnix" / "agent-gateway"


def default_ops_socket_path() -> Path:
    return (
        Path(os.environ.get("XDG_RUNTIME_DIR", "/run/user/1000"))
        / "sinnix"
        / "ops.sock"
    )


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
    runtime_transitions: Path = Path("/run/sinnix/health-transitions.jsonl")
    event_spool: Path = Path("/realm/state/agentctl/events.jsonl")
    capability_index: Path = Path("/etc/sinnix/capability-index.json")
    observe_command: str = "sinnix-observe"
    max_result_bytes: int = 262_144
    package_manifest_path: Path | None = None
    approved_manifest_hash: str | None = None
    approved_manifest_principal: str = "observer"
    connector_snapshot_path: Path | None = None
    systemd_run_command: str = "systemd-run"
    systemctl_command: str = "systemctl"
    journalctl_command: str = "journalctl"
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
        project_rows = raw.get("projects", {})
        if not isinstance(project_rows, Mapping):
            raise ValueError("projects must be an object")
        private_catalog = raw.get("privateProjectCatalogFile")
        if private_catalog is not None:
            if not isinstance(private_catalog, str) or not private_catalog.startswith(
                "/"
            ):
                raise ValueError("privateProjectCatalogFile must be an absolute path")
            private_path = Path(private_catalog)
            if private_path.is_file():
                private_raw = json.loads(private_path.read_text())
                if not isinstance(private_raw, Mapping) or set(private_raw) - {
                    "projects",
                    "links",
                }:
                    raise ValueError(
                        "private project catalog may contain projects and links objects"
                    )
                private_rows = private_raw.get("projects", {})
                if not isinstance(private_rows, Mapping):
                    raise ValueError(
                        "private project catalog projects must be an object"
                    )
                collisions = sorted(set(project_rows).intersection(private_rows))
                if collisions:
                    raise ValueError(
                        "private project catalog duplicates public projects: "
                        + ", ".join(collisions)
                    )
                project_rows = {**project_rows, **private_rows}
        projects: dict[str, ProjectConfig] = {}
        for project_id, row in project_rows.items():
            if not isinstance(project_id, str) or not project_id:
                raise ValueError("project IDs must be non-empty strings")
            if not isinstance(row, Mapping):
                raise ValueError(f"project {project_id} must be an object")
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
                    raise ValueError(
                        f"project {project_id} taskAuthority must be an object"
                    )
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
                publication_policy = task_authority_row.get(
                    "publicationPolicy", "local"
                )
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
        normalized_broker_servers: dict[str, dict[str, Any]] = {}
        for name, server in broker_servers.items():
            timeout = server.get("callTimeoutSeconds", DEFAULT_MCP_CALL_TIMEOUT_SECONDS)
            try:
                timeout = validate_mcp_call_timeout(timeout)
            except ValueError as exc:
                raise ValueError(f"mcpBrokerServers.{name}.{exc}") from exc
            normalized_broker_servers[name] = {
                **server,
                "callTimeoutSeconds": timeout,
            }
        return cls(
            state_dir=state_dir,
            projects=projects,
            runtime_inventory=Path(
                raw.get("runtimeInventory", "/etc/sinnix/runtime-inventory.json")
            ),
            runtime_transitions=Path(
                raw.get("runtimeTransitions", "/run/sinnix/health-transitions.jsonl")
            ),
            event_spool=Path(
                raw.get("eventSpool", "/realm/state/agentctl/events.jsonl")
            ),
            capability_index=Path(
                raw.get("capabilityIndex", "/etc/sinnix/capability-index.json")
            ),
            observe_command=raw.get("observeCommand", "sinnix-observe"),
            max_result_bytes=int(raw.get("maxResultBytes", 262_144)),
            package_manifest_path=Path(raw["packageManifestPath"])
            if raw.get("packageManifestPath")
            else None,
            approved_manifest_hash=raw.get("approvedManifestHash"),
            approved_manifest_principal=raw.get(
                "approvedManifestPrincipal", "observer"
            ),
            connector_snapshot_path=Path(raw["connectorSnapshotPath"])
            if "connectorSnapshotPath" in raw
            else None,
            systemd_run_command=raw.get("systemdRunCommand", "systemd-run"),
            systemctl_command=raw.get("systemctlCommand", "systemctl"),
            journalctl_command=raw.get("journalctlCommand", "journalctl"),
            ops_socket_path=Path(raw.get("opsSocketPath", default_ops_socket_path())),
            hypr_control_command=raw.get("hyprControlCommand", "sinnix-hypr-control"),
            screenshot_control_command=raw.get(
                "screenshotControlCommand", "sinnix-screenshot-control"
            ),
            kitty_control_command=raw.get(
                "kittyControlCommand", "sinnix-kitty-control"
            ),
            chrome_control_command=raw.get(
                "chromeControlCommand", "sinnix-chrome-control"
            ),
            beads_command=raw.get("beadsCommand", "bd"),
            mcp_broker_servers=normalized_broker_servers,
            capture_command=raw.get("captureCommand", "sinnix-capture"),
        )

    def initialize_state(self) -> None:
        for path in (
            self.state_dir,
            self.state_dir / "audit",
            self.state_dir / "artifacts",
            self.state_dir / "captures",
            self.state_dir / "contexts",
            self.state_dir / "diagnostics",
            self.state_dir / "legacy",
            self.state_dir / "results",
        ):
            path.mkdir(mode=0o700, parents=True, exist_ok=True)
            path.chmod(0o700)
