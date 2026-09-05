"""Where agentctl finds its projects, its agent runner, and its artifacts.

The host renders `/etc/sinnix/agentctl.json`; `AGENTCTL_CONFIG` overrides the
path for tests and checkouts under development. Absent both, the defaults
below describe this workstation.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping

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
class Config:
    project_roots: tuple[Path, ...]
    agent_runner: Path
    # The worker contract compiled into a worker prompt when the project's
    # descriptor names no template of its own.
    worker_contract: Path
    event_spool: Path
    state_dir: Path
    agentctl_executable: str
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
    return replace(
        config,
        config_path=location,
        project_roots=_paths(raw.get("project_roots", []), "project_roots"),
        agent_runner=_path(
            raw.get("agent_runner"), "agent_runner", config.agent_runner
        ),
        worker_contract=_path(
            raw.get("worker_contract"), "worker_contract", config.worker_contract
        ),
        event_spool=_path(raw.get("event_spool"), "event_spool", config.event_spool),
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
