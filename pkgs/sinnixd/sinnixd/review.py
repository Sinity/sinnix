"""Policy routing for completed implementation lanes.

The scanner supplies evidence; this module owns only the mechanical choice of
where judgment belongs.  It deliberately does not publish, merge, or mutate a
checkout.  That keeps review lanes ordinary AgentCTL jobs and leaves Git and
the task backend to their existing owners.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

ROUTES = frozenset({"auto-publish", "review-lane", "coordinator"})
_ALWAYS_ESCALATE = (
    "verification gate or baseline edited",
    "durable migration touched",
    "new xfail/skip",
    "test files deleted",
    "legacy/compat retained or introduced in production code",
    "very large diff",
)
_SAFE_REVIEW_VERDICTS = frozenset(
    {
        "safe deletion",
        "pure additions; not a polarity change",
        "mechanical baseline reduction",
        "migration metadata is present",
    }
)


def _flag_cleared(flag: str, verdicts: Sequence[str]) -> bool:
    if flag.startswith("production definitions removed") or flag.startswith("production file deleted"):
        return "safe deletion" in verdicts
    if flag.startswith("test assertions removed"):
        return "safe deletion" in verdicts
    if flag.startswith("assertion polarity change"):
        return "pure additions; not a polarity change" in verdicts
    return any(verdict in _SAFE_REVIEW_VERDICTS for verdict in verdicts)


@dataclass(frozen=True)
class ReviewRoute:
    """A reproducible review disposition and its audit inputs."""

    route: str
    reason: str
    flags: tuple[str, ...]
    unresolved: tuple[str, ...]
    reviewer_backend: str | None = None
    reviewer_model: str | None = None

    def __post_init__(self) -> None:
        if self.route not in ROUTES:
            raise ValueError(f"invalid review route: {self.route}")
        if self.route == "review-lane" and not self.reviewer_backend:
            raise ValueError("review lanes require an explicit reviewer backend")

    def to_dict(self) -> dict[str, Any]:
        return {
            "route": self.route,
            "reason": self.reason,
            "flags": list(self.flags),
            "unresolved": list(self.unresolved),
            "reviewer_backend": self.reviewer_backend,
            "reviewer_model": self.reviewer_model,
        }


def _flag_lines(scanner_output: str) -> tuple[str, ...]:
    return tuple(
        line.removeprefix("FLAG: ").strip()
        for line in scanner_output.splitlines()
        if line.startswith("FLAG: ")
    )


def _verdicts(scanner_output: str) -> tuple[str, ...]:
    return tuple(
        line.removeprefix("  VERDICT: ").strip()
        for line in scanner_output.splitlines()
        if line.startswith("  VERDICT: ")
    )


def _is_docs_or_tests(path: str) -> bool:
    return path.startswith(("docs/", "tests/")) or path.endswith((".md", ".rst"))


def route_review(
    *,
    changed_paths: Sequence[str],
    scanner_output: str,
    implementation_backend: str = "codex",
) -> ReviewRoute:
    """Route one scanner result according to the review-fission policy.

    A flag is considered cleared only when the explanation includes a known
    safe verdict.  Missing explanations and novel verdicts go to the
    coordinator queue; they never become an implicit approval.
    """
    flags = _flag_lines(scanner_output)
    verdicts = _verdicts(scanner_output)
    unresolved: list[str] = []
    for flag in flags:
        if any(prefix in flag.lower() for prefix in ("security", "excision")):
            unresolved.append(flag)
        elif any(flag.startswith(prefix) for prefix in _ALWAYS_ESCALATE):
            unresolved.append(flag)
        elif not _flag_cleared(flag, verdicts):
            unresolved.append(flag)

    if unresolved:
        return ReviewRoute(
            "coordinator",
            "risky review class or scanner recipe was not cleared",
            flags,
            tuple(unresolved),
        )

    if (
        changed_paths
        and not flags
        and all(_is_docs_or_tests(path) for path in changed_paths)
    ):
        return ReviewRoute(
            "auto-publish",
            "docs/tests-only change with no scanner flags",
            flags,
            (),
        )

    # Review judgment must cross model families.  The mapping is intentionally
    # small and explicit; adding a backend requires a policy change and tests.
    backend = "claude" if implementation_backend == "codex" else "codex"
    model = "claude-opus-5" if backend == "claude" else "gpt-5.6-sol"
    return ReviewRoute(
        "review-lane",
        "ordinary production change with scanner evidence cleared",
        flags,
        (),
        reviewer_backend=backend,
        reviewer_model=model,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sinnixd-review-route")
    parser.add_argument("worktree", type=Path)
    parser.add_argument("--base", default="origin/master")
    parser.add_argument("--implementation-backend", default="codex")
    args = parser.parse_args(argv)
    try:
        names = subprocess.run(
            ["git", "diff", "--name-only", f"{args.base}...HEAD"],
            cwd=args.worktree,
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        ).stdout.splitlines()
        diff = subprocess.run(
            ["git", "diff", f"{args.base}...HEAD"],
            cwd=args.worktree,
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        ).stdout
        from sinnixd.harvest import _redflags

        _status, flags = _redflags(diff, changed_paths=names)
        output = "\n".join(flags)
        print(
            json.dumps(
                route_review(
                    changed_paths=names,
                    scanner_output=output,
                    implementation_backend=args.implementation_backend,
                ).to_dict(),
                sort_keys=True,
            )
        )
        return 0
    except (OSError, subprocess.SubprocessError, RuntimeError, ValueError) as error:
        print(json.dumps({"error": str(error)}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
