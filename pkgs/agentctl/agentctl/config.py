"""Where agentctl finds its projects, its agent runner, and its artifacts.

The host renders `/etc/sinnix/agentctl.json`; `AGENTCTL_CONFIG` overrides the
path for tests and checkouts under development. Absent both, the defaults
below describe this workstation.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping

from .launch_input import POOL_NAME
from .projects import (
    ProjectAdapter,
    ProjectCatalog,
    ProjectConfigError,
    load_project_adapter,
)
from .prompts import PromptError

DEFAULT_CONFIG_PATH = Path("/etc/sinnix/agentctl.json")
DEFAULT_PROJECT_PARENTS = (Path("/realm/project"), Path("/realm/worktrees"))
# Where this workstation keeps the shared skills when no agentctl.json says.
DEFAULT_SKILLS_DIR = Path("/realm/project/sinnix/dots/_ai/skills")


class ConfigError(ValueError):
    """The configuration file exists but cannot be read as this contract."""


@dataclass(frozen=True)
class PoolPolicy:
    """One pueue group's declared parallelism."""

    parallel: int


@dataclass(frozen=True)
class Config:
    project_roots: tuple[Path, ...]
    agent_runner: Path
    # The worker contract compiled into a worker prompt when the project's
    # descriptor names no template of its own.
    worker_contract: Path
    event_spool: Path
    state_dir: Path
    agentctl_executable: str
    private_project_catalog: Path | None = None
    # Each pueue group's declared width. `pools apply` writes it into the
    # running daemon, whose queue remains the admission authority.
    pools: Mapping[str, PoolPolicy] = field(default_factory=dict)
    # The file this configuration was read from. Every task agentctl queues
    # carries it as AGENTCTL_CONFIG, so the agentctl calls inside a task read
    # the same projects, state directory and event spool as the one that
    # queued it.
    config_path: Path | None = None

    @property
    def inputs_dir(self) -> Path:
        return self.state_dir / "inputs"

    @property
    def jobs_dir(self) -> Path:
        return self.state_dir / "jobs"

    def catalog(self, *, tolerant: bool = True) -> ProjectCatalog:
        return ProjectCatalog(self.project_roots, tolerant=tolerant)


def default_state_dir() -> Path:
    base = Path(
        os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    )
    state_dir = base / "agentctl"
    previous = base / "sinnixd"
    if not state_dir.exists() and previous.is_dir():
        try:
            os.rename(previous, state_dir)
        except OSError as error:
            # A persistence bind mount cannot be renamed; the operator moves it.
            print(
                f"agentctl: could not move {previous} to {state_dir}: {error}",
                file=sys.stderr,
            )
        else:
            print(f"agentctl: moved state {previous} -> {state_dir}", file=sys.stderr)
    return state_dir


def _default(state_dir: Path | None = None) -> Config:
    return Config(
        project_roots=(),
        agent_runner=DEFAULT_SKILLS_DIR / "agent-runtime/scripts/run_agent_prompt.sh",
        worker_contract=DEFAULT_SKILLS_DIR
        / "orchestrate/references/worker-contract.md",
        event_spool=Path("/realm/state/agentctl/events.jsonl"),
        state_dir=state_dir or default_state_dir(),
        agentctl_executable="/run/current-system/sw/bin/agentctl",
        private_project_catalog=None,
    )


def _paths(value: Any, field: str) -> tuple[Path, ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.startswith("/") for item in value
    ):
        raise ConfigError(f"{field} must be a list of absolute paths")
    return tuple(Path(item) for item in value)


def _parallel(name: str, value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ConfigError(f"pools.{name} must run at least one task at a time")
    return value


def _pools(value: Any) -> dict[str, PoolPolicy]:
    """The declared groups and their widths."""
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ConfigError("pools must map a pueue group name to its parallelism")
    parsed: dict[str, PoolPolicy] = {}
    for name, declaration in value.items():
        if not isinstance(name, str) or POOL_NAME.fullmatch(name) is None:
            raise ConfigError(f"pools has an invalid pueue group name: {name!r}")
        if isinstance(declaration, Mapping):
            unknown = set(declaration) - {"parallel"}
            if unknown:
                raise ConfigError(
                    f"pools.{name} declares unknown field(s): "
                    + ", ".join(sorted(unknown))
                )
            parsed[name] = PoolPolicy(
                parallel=_parallel(name, declaration.get("parallel"))
            )
        else:
            parsed[name] = PoolPolicy(parallel=_parallel(name, declaration))
    return parsed


def _path(value: Any, field: str, fallback: Path) -> Path:
    if value is None:
        return fallback
    if not isinstance(value, str) or not value.startswith("/"):
        raise ConfigError(f"{field} must be an absolute path")
    return Path(value)


def load_config(path: Path | None = None) -> Config:
    """The file's settings over the defaults; the state directory is only
    resolved (and moved) when the file does not name one."""
    location = path or Path(os.environ.get("AGENTCTL_CONFIG") or DEFAULT_CONFIG_PATH)
    try:
        raw = json.loads(location.read_text())
    except FileNotFoundError:
        return replace(_default(), config_path=location)
    except (OSError, json.JSONDecodeError) as error:
        raise ConfigError(f"could not read {location}: {error}") from error
    if not isinstance(raw, Mapping):
        raise ConfigError(f"{location} must contain an object")
    state_dir = raw.get("state_dir")
    if state_dir is not None and (
        not isinstance(state_dir, str) or not state_dir.startswith("/")
    ):
        raise ConfigError("state_dir must be an absolute path")
    config = _default(Path(state_dir) if state_dir else None)
    private_catalog = raw.get("private_project_catalog")
    if private_catalog is not None and (
        not isinstance(private_catalog, str) or not private_catalog.startswith("/")
    ):
        raise ConfigError("private_project_catalog must be an absolute path")
    private_catalog_path = Path(private_catalog) if private_catalog else None
    project_roots = list(_paths(raw.get("project_roots", []), "project_roots"))
    if private_catalog_path is not None and private_catalog_path.is_file():
        try:
            private_raw = json.loads(private_catalog_path.read_text())
        except (OSError, json.JSONDecodeError) as error:
            raise ConfigError(
                f"could not read private project catalog {private_catalog_path}: {error}"
            ) from error
        if not isinstance(private_raw, Mapping) or set(private_raw) - {
            "projects",
            "links",
        }:
            raise ConfigError(
                "private project catalog may contain projects and links objects"
            )
        rows = private_raw.get("projects", {})
        if not isinstance(rows, Mapping):
            raise ConfigError("private project catalog projects must be an object")
        for project_id, row in rows.items():
            if (
                not isinstance(project_id, str)
                or not project_id
                or not isinstance(row, Mapping)
            ):
                raise ConfigError(
                    "private project catalog entries must map project IDs to objects"
                )
            enabled = row.get("agentctl", False)
            if not isinstance(enabled, bool):
                raise ConfigError(
                    f"private project {project_id} agentctl must be boolean"
                )
            if not enabled:
                continue
            root = row.get("path")
            if not isinstance(root, str) or not root.startswith("/"):
                raise ConfigError(f"private project {project_id} path must be absolute")
            project_roots.append(Path(root))
    if len(project_roots) != len(set(project_roots)):
        raise ConfigError("public and private project roots must be unique")
    return replace(
        config,
        config_path=location,
        project_roots=tuple(project_roots),
        agent_runner=_path(
            raw.get("agent_runner"), "agent_runner", config.agent_runner
        ),
        worker_contract=_path(
            raw.get("worker_contract"), "worker_contract", config.worker_contract
        ),
        event_spool=_path(raw.get("event_spool"), "event_spool", config.event_spool),
        agentctl_executable=str(raw.get("agentctl") or config.agentctl_executable),
        private_project_catalog=private_catalog_path,
        pools=_pools(raw.get("pools")),
    )


def resolve_project_root(selector: str | None, *, cwd: Path | None = None) -> Path:
    """A project id, a path, or the checkout enclosing ``cwd``."""
    current = (cwd or Path.cwd()).resolve()
    candidates: list[Path] = []
    if selector:
        selected = Path(selector).expanduser()
        if selected.is_dir():
            candidates.append(selected.resolve())
        candidates.extend(
            parent / selector
            for parent in DEFAULT_PROJECT_PARENTS
            if (parent / selector).is_dir()
        )
    else:
        candidates.extend((current, *current.parents))
    for candidate in candidates:
        if (candidate / ".agentctl" / "project.toml").is_file():
            return candidate
    raise PromptError(
        f"could not resolve an AgentCTL project for {selector or current}"
    )


def resolve_project(config: Config, selector: str | None) -> ProjectAdapter:
    """The configured project with that id, else the descriptor at that path."""
    if selector:
        catalog = config.catalog()
        try:
            return catalog.get(selector)
        except KeyError as error:
            if "out of service" in str(error):
                raise ProjectConfigError(str(error.args[0])) from error
    return load_project_adapter(resolve_project_root(selector))
