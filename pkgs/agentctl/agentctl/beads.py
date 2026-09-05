"""Beads: the reads a prompt needs and the four writes a batch makes."""

from __future__ import annotations

import subprocess
from typing import Any, Mapping, Protocol, Sequence

from .limits import CALL_TIMEOUT_SECONDS
from .manifest import BatchError
from .prompts import SubprocessBdReader


class Beads(Protocol):
    def show(self, bead_id: str) -> Mapping[str, Any]: ...

    def list(self) -> Sequence[Mapping[str, Any]]: ...

    def claim(self, bead_id: str, *, actor: str) -> None: ...

    def unclaim(self, bead_id: str, *, actor: str) -> None: ...

    def close(self, bead_id: str, *, reason: str, actor: str) -> None: ...

    def comment(self, bead_id: str, text: str, *, actor: str) -> None: ...


class SubprocessBeads(SubprocessBdReader):
    """`bd` reads and the four writes a batch makes, run in the project root."""

    def _write(self, arguments: Sequence[str], *, actor: str) -> None:
        try:
            completed = subprocess.run(
                [self.executable, "--actor", actor, *arguments],
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=CALL_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise BatchError(
                f"bd {' '.join(arguments)} failed in {self.root}"
            ) from error
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise BatchError(f"bd {' '.join(arguments[:2])}: {detail}")

    def claim(self, bead_id: str, *, actor: str) -> None:
        self._write(("update", bead_id, "--claim"), actor=actor)

    def unclaim(self, bead_id: str, *, actor: str) -> None:
        self._write(("unclaim", bead_id, "--if-assignee", actor), actor=actor)

    def close(self, bead_id: str, *, reason: str, actor: str) -> None:
        self._write(("close", bead_id, "--reason", reason), actor=actor)

    def comment(self, bead_id: str, text: str, *, actor: str) -> None:
        self._write(("comment", bead_id, text), actor=actor)
