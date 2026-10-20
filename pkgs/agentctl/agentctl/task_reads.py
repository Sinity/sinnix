"""Read Beads tasks through its native CLI in the owning repository."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from .limits import CALL_TIMEOUT_SECONDS


class TaskReadError(ValueError):
    """A native task read failed or returned an invalid response."""


class BdReader(Protocol):
    def show(self, bead_id: str) -> Mapping[str, Any]: ...

    def list(self) -> Sequence[Mapping[str, Any]]: ...

    def ready(self) -> Sequence[Mapping[str, Any]]: ...


@dataclass(frozen=True)
class SubprocessBdReader:
    """`bd` resolves its database from the working directory: run it in the project."""

    root: Path
    executable: str = "bd"

    def _run(self, arguments: Sequence[str]) -> Any:
        try:
            result = subprocess.run(
                [self.executable, *arguments],
                cwd=self.root,
                check=True,
                capture_output=True,
                text=True,
                timeout=CALL_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise TaskReadError(
                f"bd {' '.join(arguments)} failed in {self.root}"
            ) from error
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise TaskReadError("bd returned invalid JSON") from error

    def show(self, bead_id: str) -> Mapping[str, Any]:
        return _one_bead(self._run(("show", bead_id, "--json")), bead_id)

    def list(self) -> Sequence[Mapping[str, Any]]:
        return _bead_list(
            self._run(("list", "--all", "--limit", "0", "--json")), "list"
        )

    def ready(self) -> Sequence[Mapping[str, Any]]:
        return _bead_list(self._run(("ready", "--limit", "0", "--json")), "ready")


def _bead_list(value: Any, what: str) -> Sequence[Mapping[str, Any]]:
    if not isinstance(value, list) or any(
        not isinstance(item, Mapping) for item in value
    ):
        raise TaskReadError(f"bd {what} returned an invalid bead list")
    return value


def _one_bead(value: Any, bead_id: str) -> Mapping[str, Any]:
    if isinstance(value, Mapping) and "error" not in value:
        bead = value
    elif isinstance(value, list) and len(value) == 1 and isinstance(value[0], Mapping):
        bead = value[0]
    else:
        raise TaskReadError(f"bd show {bead_id} returned an invalid bead")
    if bead.get("id") != bead_id:
        raise TaskReadError(f"bd show {bead_id} returned the wrong bead")
    return bead
