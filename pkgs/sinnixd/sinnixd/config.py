"""Where agentctl finds its projects, its agent runner, and its artifacts.

The host renders `/etc/sinnix/agentctl.json`; `AGENTCTL_CONFIG` overrides the
path for tests and checkouts under development. Absent both, the defaults
below describe this workstation.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping

from .packets import PacketError
from .projects import ProjectAdapter, ProjectCatalog, load_project_adapter

DEFAULT_CONFIG_PATH = Path("/etc/sinnix/agentctl.json")
DEFAULT_PROJECT_PARENTS = (Path("/realm/project"), Path("/realm/worktrees"))


class ConfigError(ValueError):
    """The configuration file exists but cannot be read as this contract."""


@dataclass(frozen=True)
class Config:
    project_roots: tuple[Path, ...]
    agent_runner: Path
    event_spool: Path
    state_dir: Path
    agentctl_executable: str

    @property
    def inputs_dir(self) -> Path:
        return self.state_dir / "inputs"

    @property
    def jobs_dir(self) -> Path:
        return self.state_dir / "jobs"

    def catalog(self, *, tolerant: bool = True) -> ProjectCatalog:
        return ProjectCatalog(self.project_roots, tolerant=tolerant)


def default_state_dir() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / "sinnixd"


def _default() -> Config:
    return Config(
        project_roots=(),
        agent_runner=Path(
            "/realm/project/sinnix/dots/_ai/skills/agent-runtime/scripts/run_agent_prompt.sh"
        ),
        event_spool=Path("/realm/state/agentctl/events.jsonl"),
        state_dir=default_state_dir(),
        agentctl_executable="/run/current-system/sw/bin/agentctl",
    )


def _paths(value: Any, field: str) -> tuple[Path, ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.startswith("/") for item in value
    ):
        raise ConfigError(f"{field} must be a list of absolute paths")
    return tuple(Path(item) for item in value)


def _path(value: Any, field: str, fallback: Path) -> Path:
    if value is None:
        return fallback
    if not isinstance(value, str) or not value.startswith("/"):
        raise ConfigError(f"{field} must be an absolute path")
    return Path(value)


def load_config(path: Path | None = None) -> Config:
    config = _default()
    location = path or Path(os.environ.get("AGENTCTL_CONFIG") or DEFAULT_CONFIG_PATH)
    try:
        raw = json.loads(location.read_text())
    except FileNotFoundError:
        return config
    except (OSError, json.JSONDecodeError) as error:
        raise ConfigError(f"could not read {location}: {error}") from error
    if not isinstance(raw, Mapping):
        raise ConfigError(f"{location} must contain an object")
    return replace(
        config,
        project_roots=_paths(raw.get("project_roots", []), "project_roots"),
        agent_runner=_path(
            raw.get("agent_runner"), "agent_runner", config.agent_runner
        ),
        event_spool=_path(raw.get("event_spool"), "event_spool", config.event_spool),
        state_dir=_path(raw.get("state_dir"), "state_dir", config.state_dir),
        agentctl_executable=str(raw.get("agentctl") or config.agentctl_executable),
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
    raise PacketError(
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
                raise
    return load_project_adapter(resolve_project_root(selector))
