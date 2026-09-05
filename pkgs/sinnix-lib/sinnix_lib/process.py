"""One subprocess wrapper with one return type.

Probes shell out to tools that may be absent, may hang, and may fail, and
every caller that hand-rolled the guard invented a different way to say "no
answer": ``None``, a ``CompletedProcess`` or ``None``, a ``(rc, out, err)``
tuple, a stripped stdout string. ``run`` always returns a :class:`Result`,
so "the command failed" and "the command never ran" are readable from the
same value instead of from a sentinel the caller has to remember.

A missing binary, a spawn failure and a timeout are outcomes, not
exceptions: a collector that raises on an absent tool reports an outage it
invented. They come back with ``error`` set and ``returncode``
``NO_EXIT_STATUS``, carrying whatever output the command produced before it
was killed.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

# No process ever reported this: the command produced no exit status at all.
NO_EXIT_STATUS = -1


def _decoded(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return value if isinstance(value, str) else ""


@dataclass(frozen=True)
class Result:
    """What one command did. ``error`` is set only when it never ran to an
    exit status, which is the one thing an exit code cannot express."""

    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.returncode == 0

    @property
    def text(self) -> str | None:
        """Stripped stdout of a successful command, else None."""
        return self.stdout.strip() if self.ok else None


def run(
    argv: Sequence[str],
    *,
    timeout: float,
    cwd: Path | str | None = None,
) -> Result:
    """Run *argv* to completion or to *timeout*, and always return a Result.

    ``timeout`` is required: an unbounded probe is how a collector becomes
    the outage it was watching.
    """
    args = tuple(argv)
    try:
        completed = subprocess.run(
            list(args),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
    except subprocess.TimeoutExpired as exc:
        return Result(
            args,
            NO_EXIT_STATUS,
            _decoded(exc.stdout),
            _decoded(exc.stderr),
            error=f"timed out after {timeout:g}s",
        )
    except OSError as exc:
        return Result(args, NO_EXIT_STATUS, "", "", error=str(exc))
    return Result(args, completed.returncode, completed.stdout, completed.stderr)
