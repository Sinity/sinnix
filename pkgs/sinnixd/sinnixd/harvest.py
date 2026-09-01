"""The declared-operation harvest pipeline.

Harvest deliberately has two phases.  The default phase is read-mostly and
produces a durable receipt for coordinator review.  Publication is reachable
only through ``--authorize`` with that receipt, so a successful operation
cannot accidentally publish an unreviewed lane.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import pathlib
import re
import signal
import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .review import route_review

HARVEST_OK = "HARVEST_OK"
REBASE_CONFLICT = "REBASE_CONFLICT"
GATE_RED = "GATE_RED"
HARVEST_ERROR = "HARVEST_ERROR"
HARVEST_EMPTY = "HARVEST_EMPTY"

RECEIPT_SCHEMA_VERSION = 1
MAX_RECEIPT_BYTES = 64_000
MAX_DIFF_BYTES = 2_000_000
MAX_COMMAND_OUTPUT_BYTES = 256_000
DEFAULT_BASE = "origin/master"
DEFAULT_SPOOL = Path("/realm/state/agentctl/events.jsonl")
PACKET_DIRECTORY = "harvest-packets"
LOCK_PATH = Path("/realm/tmp/work/.harvest-git.flock")
PUSH_TIMEOUT_SECONDS = 2_400
AFFECTED_TIMEOUT_SECONDS = 3_600
_TRAILER_FIELDS = (
    "LANE-BRANCH",
    "LANE-COMMIT",
    "LANE-QUICK",
    "LANE-CLASSIFICATION",
)
_SAFE_PACKET_ID = re.compile(r"^harvest-[0-9a-f]{32}$")

Run = Callable[..., subprocess.CompletedProcess[str]]


class HarvestError(ValueError):
    """An invalid harvest input or an unavailable pipeline dependency."""


@dataclass(frozen=True)
class HarvestContext:
    worktree: Path
    project_id: str
    workspace_id: str
    job_id: str
    state_root: Path
    base: str = DEFAULT_BASE
    spool: Path = DEFAULT_SPOOL

    @property
    def packet_root(self) -> Path:
        return self.state_root / PACKET_DIRECTORY


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _bounded_text(value: str, limit: int) -> str:
    encoded = value.encode()
    if len(encoded) <= limit:
        return value
    return encoded[:limit].decode(errors="replace")


def _command(
    run: Run,
    argv: Sequence[str],
    *,
    cwd: Path,
    timeout: float = 60,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    try:
        result = run(
            list(argv),
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=check,
        )
    except subprocess.TimeoutExpired as error:
        raise HarvestError(
            f"command timed out after {timeout:g}s: {' '.join(argv)}"
        ) from error
    except (OSError, subprocess.SubprocessError) as error:
        raise HarvestError(f"command unavailable: {argv[0]} ({error})") from error
    return subprocess.CompletedProcess(
        result.args,
        result.returncode,
        _bounded_text(result.stdout or "", MAX_COMMAND_OUTPUT_BYTES),
        _bounded_text(result.stderr or "", MAX_COMMAND_OUTPUT_BYTES),
    )


def _require_success(result: subprocess.CompletedProcess[str], description: str) -> str:
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or description
        raise HarvestError(detail)
    return result.stdout.strip()


def _git(run: Run, worktree: Path, *args: str, timeout: float = 60) -> str:
    return _require_success(
        _command(run, ["git", *args], cwd=worktree, timeout=timeout),
        f"git {' '.join(args)} failed",
    )


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _repo_slug(run: Run, worktree: Path) -> str:
    """Derive the GitHub owner/name slug from the worktree's origin remote."""
    url = _git(run, worktree, "remote", "get-url", "origin").strip()
    match = re.search(r"github\.com[:/]+([^/]+)/([^/\s]+?)(?:\.git)?/?$", url)
    if match is not None:
        return f"{match.group(1)}/{match.group(2)}"
    # A filesystem remote (fixtures, mirrors) has no hosted slug; label it
    # honestly rather than refusing the whole publication.
    return f"local/{Path(url).name or 'origin'}"


def _latest_lane_job(context: HarvestContext) -> tuple[str | None, str | None]:
    """Find the newest succeeded attested-agent job for this checkout.

    Returns (job_id, bead_id). Publication needs the lane identity for the
    trailer and the bead for closure; requiring the coordinator to restate
    either repeats what the job records already hold.
    """
    best: tuple[str, str, str | None] | None = None
    records_root = context.state_root / "jobs"
    try:
        candidates = list(records_root.glob("*.json"))
    except OSError:
        return None, None
    for path in candidates:
        try:
            record = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        spec = record.get("spec") or {}
        checkout = spec.get("checkout") or {}
        state = record.get("state") or {}
        if (
            spec.get("kind") != "attested-agent"
            or checkout.get("checkout_id") != context.workspace_id
            or state.get("phase") != "succeeded"
        ):
            continue
        created = str(record.get("created_at") or "")
        contract = spec.get("contract") or {}
        binding = contract.get("bead_binding") or {}
        bead = binding.get("bead_id") if isinstance(binding, dict) else None
        if best is None or created > best[0]:
            best = (
                created,
                str(record.get("job_id")),
                bead if isinstance(bead, str) else None,
            )
    if best is None:
        return None, None
    return best[1], best[2]


def _read_text(path: Path, description: str) -> str:
    try:
        return path.read_text()
    except (OSError, UnicodeDecodeError) as error:
        raise HarvestError(f"{description} is unavailable") from error


def _lane_artifact(context: HarvestContext, name: str) -> str | None:
    """Read one of the publication artifacts the worker contract has the lane write.

    A lane writes .lane/title, .lane/body.md and .lane/close-reason.md at a known
    path. Requiring the coordinator to point at those same files by hand makes
    every caller restate what the contract already fixed, and omitting them
    fails the publication for an empty title.
    """
    path = context.worktree / ".lane" / name
    if not path.is_file():
        return None
    text = path.read_text().strip()
    return text or None


def _adopt_open_pull_request(
    context: HarvestContext,
    run: Run,
    *,
    title: str,
    body: str,
) -> str | None:
    """Return the URL of this branch's open pull request, refreshed.

    Returns None when the branch has none, which leaves the caller's original
    creation failure as the reported cause.
    """
    view = _command(
        run,
        ["gh", "pr", "view", "--json", "url,state", "--jq", '.url + " " + .state'],
        cwd=context.worktree,
        timeout=120,
    )
    if view.returncode != 0:
        return None
    parts = view.stdout.strip().split()
    if len(parts) != 2 or parts[1] != "OPEN":
        return None
    url = parts[0]
    edited = _command(
        run,
        ["gh", "pr", "edit", url, "--title", title, "--body", body],
        cwd=context.worktree,
        timeout=120,
    )
    if edited.returncode != 0:
        raise HarvestError(edited.stderr.strip() or "GitHub pull request update failed")
    return url


def _resolve_publication_text(
    parsed: argparse.Namespace, context: HarvestContext
) -> tuple[str, str, str | None]:
    """Resolve the publication text, preferring what the caller named.

    An explicit file wins, then an explicit value, then the artifact the lane
    wrote. `--title` and `--body` default to the empty string rather than to
    None, so absence is falsiness here, not identity.
    """
    title = parsed.title
    if parsed.title_file is not None:
        title = _read_text(parsed.title_file, "publication title file")
    elif not title:
        title = _lane_artifact(context, "title") or title
    body = parsed.body
    if parsed.body_file is not None:
        body = _read_text(parsed.body_file, "publication body file")
    elif not body:
        body = _lane_artifact(context, "body.md") or body
    close_reason = parsed.close_reason
    if parsed.close_reason_file is not None:
        close_reason = _read_text(parsed.close_reason_file, "bead close reason file")
    elif not close_reason:
        close_reason = _lane_artifact(context, "close-reason.md") or close_reason
    return title, body, close_reason


def _safe_json_write(path: Path, value: Mapping[str, Any]) -> None:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    if len(encoded) > MAX_RECEIPT_BYTES:
        raise HarvestError("harvest receipt exceeds its bounded artifact limit")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        descriptor = os.open(
            temporary,
            os.O_CREAT | os.O_TRUNC | os.O_WRONLY | os.O_NOFOLLOW,
            0o600,
        )
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.write(b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _append_event(path: Path, event: Mapping[str, Any]) -> None:
    """Append an advisory event without making the spool a state authority."""
    try:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        line = json.dumps(dict(event), sort_keys=True, separators=(",", ":"))
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        pass


def _trailer_from_text(text: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for line in text.splitlines():
        field, separator, value = line.partition(":")
        if separator and field in _TRAILER_FIELDS and value.strip():
            found[field] = value.strip()
    return found


def _lane_trailer(
    context: HarvestContext,
    *,
    lane_job_id: str | None,
) -> dict[str, str]:
    """Find the successful lane report bound to this registered checkout."""
    if lane_job_id and not re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
        lane_job_id,
    ):
        raise HarvestError("lane job ID is malformed")
    candidates: list[tuple[str, dict[str, str]]] = []
    records_root = context.state_root / "jobs"
    paths = (
        [records_root / f"{lane_job_id}.json"]
        if lane_job_id
        else sorted(records_root.glob("*.json"))
    )
    for record_path in paths:
        try:
            record = json.loads(record_path.read_text())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(record, Mapping):
            continue
        spec = record.get("spec")
        checkout = spec.get("checkout") if isinstance(spec, Mapping) else None
        state = record.get("state")
        if (
            not isinstance(spec, Mapping)
            or spec.get("kind") != "attested-agent"
            or not isinstance(checkout, Mapping)
            or checkout.get("checkout_id") != context.workspace_id
            or not isinstance(state, Mapping)
            or state.get("phase") != "succeeded"
        ):
            continue
        artifacts = record.get("artifacts")
        artifact = artifacts.get("result") if isinstance(artifacts, Mapping) else None
        if not isinstance(artifact, str):
            continue
        try:
            trailer = _trailer_from_text(Path(artifact).read_text())
        except (OSError, UnicodeDecodeError):
            continue
        if all(field in trailer for field in _TRAILER_FIELDS):
            candidates.append((str(record.get("created_at", "")), trailer))
    if not candidates:
        return {}
    return sorted(candidates, key=lambda item: item[0])[-1][1]


def _lane_write_scope(
    context: HarvestContext, *, lane_job_id: str | None
) -> tuple[str, ...]:
    """Read the declared scope from the successful lane packet binding."""
    records_root = context.state_root / "jobs"
    paths = (
        [records_root / f"{lane_job_id}.json"]
        if lane_job_id
        else sorted(records_root.glob("*.json"))
    )
    candidates: list[tuple[str, tuple[str, ...]]] = []
    for record_path in paths:
        try:
            record = json.loads(record_path.read_text())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(record, Mapping):
            continue
        spec = record.get("spec")
        state = record.get("state")
        checkout = spec.get("checkout") if isinstance(spec, Mapping) else None
        contract = spec.get("contract") if isinstance(spec, Mapping) else None
        binding = (
            contract.get("bead_binding") if isinstance(contract, Mapping) else None
        )
        scope = binding.get("write_scope") if isinstance(binding, Mapping) else None
        if (
            not isinstance(spec, Mapping)
            or spec.get("kind") != "attested-agent"
            or not isinstance(checkout, Mapping)
            or checkout.get("checkout_id") != context.workspace_id
            or not isinstance(state, Mapping)
            or state.get("phase") != "succeeded"
            or not isinstance(scope, list)
            or not scope
            or not all(isinstance(path, str) and path for path in scope)
        ):
            continue
        candidates.append((str(record.get("created_at", "")), tuple(scope)))
    return sorted(candidates, key=lambda item: item[0])[-1][1] if candidates else ()


def _lane_oracle_command(
    context: HarvestContext, *, lane_job_id: str | None
) -> str | None:
    """Read the packet-declared oracle from the attested job dimensions."""
    records_root = context.state_root / "jobs"
    paths = (
        [records_root / f"{lane_job_id}.json"]
        if lane_job_id
        else sorted(records_root.glob("*.json"))
    )
    candidates: list[tuple[str, str]] = []
    for record_path in paths:
        try:
            record = json.loads(record_path.read_text())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        spec = record.get("spec") if isinstance(record, Mapping) else None
        checkout = spec.get("checkout") if isinstance(spec, Mapping) else None
        state = record.get("state") if isinstance(record, Mapping) else None
        dimensions = spec.get("dimensions") if isinstance(spec, Mapping) else None
        command = dimensions.get("oracle_command") if isinstance(dimensions, Mapping) else None
        if (
            isinstance(spec, Mapping)
            and spec.get("kind") == "attested-agent"
            and isinstance(checkout, Mapping)
            and checkout.get("checkout_id") == context.workspace_id
            and isinstance(state, Mapping)
            and state.get("phase") == "succeeded"
            and isinstance(command, str)
            and command.strip()
        ):
            candidates.append((str(record.get("created_at", "")), command.strip()))
    return sorted(candidates, key=lambda item: item[0])[-1][1] if candidates else None


def _oracle_evidence(context: HarvestContext, command: str, run: Run) -> dict[str, Any]:
    if len(command.encode()) > 4_096 or "\x00" in command:
        raise HarvestError("harvest oracle command exceeds its bounded limit")
    result = _command(run, ["bash", "-lc", command], cwd=context.worktree, timeout=60)
    stdout = result.stdout or ""
    stderr = result.stderr or ""
    return {
        "command": command,
        "command_sha256": _digest(command),
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": result.returncode,
        "output_sha256": _digest(json.dumps({"stdout": stdout, "stderr": stderr}, sort_keys=True)),
    }


def _valid_oracle_receipt(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    command = value.get("command")
    stdout = value.get("stdout")
    stderr = value.get("stderr")
    exit_code = value.get("exit_code")
    return (
        isinstance(command, str)
        and bool(command.strip())
        and len(command.encode()) <= 4_096
        and "\x00" not in command
        and isinstance(stdout, str)
        and isinstance(stderr, str)
        and isinstance(exit_code, int)
        and not isinstance(exit_code, bool)
        and exit_code == 0
        and value.get("command_sha256") == _digest(command)
        and value.get("output_sha256")
        == _digest(json.dumps({"stdout": stdout, "stderr": stderr}, sort_keys=True))
    )


def _verification_evidence(worktree: Path, head: str) -> dict[str, Any]:
    """Read what the lane's own verification actually did.

    `devtools` writes a receipt per run under `.cache/verify/runs/`. Reading it
    replaces the lane's self-reported trailer with evidence: which command ran,
    whether it passed, how many tests, and against which commit -- so a receipt
    describing a different HEAD is visible as stale rather than counted.
    """
    runs = worktree / ".cache/verify/runs"
    try:
        records = sorted(runs.glob("*/run.json"))
    except OSError:
        return {"state": "unreadable"}
    if not records:
        return {"state": "absent"}
    latest: dict[str, Any] = {}
    for record in records:
        try:
            value = json.loads(record.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(value, Mapping):
            continue
        argv = value.get("argv")
        command = " ".join(argv) if isinstance(argv, list) else "?"
        entry = {
            "status": value.get("status"),
            "exit_code": value.get("exit_code"),
            "git_head": value.get("git_head"),
            "final_git_head": value.get("final_git_head"),
            "git_dirty": value.get("git_dirty"),
            "pytest": value.get("pytest_aggregate"),
            "finished_at": value.get("finished_at"),
            "stale": value.get("final_git_head") not in (None, head)
            and value.get("git_head") != head,
        }
        latest[command] = entry
    if not latest:
        return {"state": "unreadable"}
    tested = any(
        isinstance(e.get("pytest"), Mapping)
        and not e["stale"]
        and e.get("status") == "success"
        for e in latest.values()
    )
    return {
        "state": "tests-run" if tested else "static-only",
        "runs": latest,
    }


def _redflags(
    diff: str,
    write_scope: Sequence[str] = (),
    *,
    changed_paths: Sequence[str] | None = None,
) -> tuple[int, list[str]]:
    """Port the deterministic coordinator red-flag scanner."""
    flags: list[str] = []

    def flag(message: str) -> None:
        flags.append(f"FLAG: {message}")

    production = False
    tests = False
    production_removed = False
    touched_production_modules: set[str] = set()
    test_assertion_removed = False
    new_modules: list[str] = []
    touched_tests: set[str] = set()
    pending_new_file: str | None = None
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            path = line.split(" b/", 1)[-1]
            production = path.startswith("polylogue/")
            tests = path.startswith("tests/")
            pending_new_file = path
            if production and path.endswith(".py"):
                touched_production_modules.add(path)
            if tests:
                touched_tests.add(pathlib.PurePosixPath(path).stem)
        if (
            line.startswith("new file mode ")
            and pending_new_file
            and pending_new_file.startswith("polylogue/")
            and pending_new_file.endswith(".py")
            and not pathlib.PurePosixPath(pending_new_file).name.startswith("__")
        ):
            new_modules.append(pending_new_file)
        if production and line.startswith("-") and not line.startswith("---"):
            if re.search(r"def |self\.|\(\)", line):
                production_removed = True
        if tests and line.startswith("-") and "assert " in line:
            test_assertion_removed = True
        if tests and line.startswith("deleted file mode "):
            flag("test files deleted")
    if production_removed:
        flag("production lines removed (polylogue/)")
    # A new module nothing tests passes every other gate: the scan looks for
    # removals, and affected-test selection has nothing to select.
    for module in new_modules:
        stem = pathlib.PurePosixPath(module).stem
        if not any(stem in name for name in touched_tests):
            flag(f"new production module without a test: {module}")
    # A behaviour change with no test anywhere in the diff passes every other
    # gate too: the lane's own green is a static run that selects nothing, so
    # nothing observes the change it just made.
    if touched_production_modules and not touched_tests:
        flag(
            "production changed with no test in the diff: "
            + ", ".join(sorted(touched_production_modules)[:5])
        )
    if re.search(
        r"^-\s*assert .*== 0\b|^\+\s*assert .*exit_code == 1|^\+.*pytest\.raises",
        diff,
        re.MULTILINE,
    ):
        flag("assertion polarity change")
    if test_assertion_removed:
        flag("test assertions removed")
    if re.search(r"^\+.*(xfail|skipif|pytest\.mark\.skip)", diff, re.MULTILINE):
        flag("new xfail/skip")
    if re.search(
        r"^diff --git a/devtools/(consumer_reachability|verify|patterns/baselines)",
        diff,
        re.MULTILINE,
    ):
        flag("verification gate or baseline edited")
    if re.search(
        r"^diff --git a/polylogue/storage/sqlite/migrations/", diff, re.MULTILINE
    ):
        flag("durable migration touched")
    if re.search(r"^diff --git a/.*train\.json", diff, re.MULTILINE):
        flag("train sidecar touched")
    if write_scope:
        paths = (
            tuple(changed_paths)
            if changed_paths is not None
            else tuple(
                line.split(" b/", 1)[-1]
                for line in diff.splitlines()
                if line.startswith("diff --git ") and " b/" in line
            )
        )
        outside_scope = sorted(
            path
            for path in paths
            if not any(
                path == entry or entry.endswith("/") and path.startswith(entry)
                for entry in write_scope
            )
        )
        if outside_scope:
            flag(
                "changed paths outside declared write scope: "
                + ", ".join(outside_scope[:20])
            )
    lines = sum(1 for line in diff.splitlines() if re.match(r"^[+-][^+-]", line))
    if lines > 1500:
        flag("very large diff")
    return (1 if flags else 0), [f"diff lines: {lines}", *flags]


_CONVENTIONAL_SUBJECT = re.compile(
    r"^(feat|fix|chore|docs|test|refactor|perf|build|ci|style|revert)"
    r"(\([a-z0-9._/-]+\))?!?: \S.{9,}$"
)


def _require_publication_title(title: str) -> None:
    """The title becomes the squash subject on the protected branch.

    A caller's mangled expansion would otherwise be permanent history, so the
    shape is enforced here rather than trusted from the caller.
    """
    subject = title.strip()
    if not subject:
        raise HarvestError("harvest publication title is empty")
    if len(subject) > 72:
        raise HarvestError(
            f"harvest publication title is {len(subject)} characters, max 72"
        )
    if _CONVENTIONAL_SUBJECT.fullmatch(subject) is None:
        raise HarvestError(
            "harvest publication title must be a conventional subject with a "
            f"description of at least ten characters: {subject!r}"
        )


def _packet_id(context: HarvestContext, head: str) -> str:
    digest = hashlib.sha256(
        "\0".join(
            (context.project_id, context.workspace_id, head, context.job_id)
        ).encode()
    ).hexdigest()[:32]
    return f"harvest-{digest}"


def _receipt_path(context: HarvestContext, packet_id: str) -> Path:
    if not _SAFE_PACKET_ID.fullmatch(packet_id):
        raise HarvestError("harvest receipt reference is malformed")
    return context.packet_root / f"{packet_id}.json"


def compile_packet(
    context: HarvestContext,
    *,
    lane_job_id: str | None = None,
    bead_id: str | None = None,
    close_reason: str | None = None,
    oracle_command: str | None = None,
    run: Run = subprocess.run,
) -> dict[str, Any]:
    """Compile a review packet and stop before any publication side effect."""
    head = _git(run, context.worktree, "rev-parse", "HEAD")
    branch = _git(run, context.worktree, "branch", "--show-current")
    unstaged = _git(run, context.worktree, "diff", "HEAD")
    staged = _git(run, context.worktree, "diff", "--cached")
    diff = _git(
        run,
        context.worktree,
        "diff",
        "--no-ext-diff",
        f"{context.base}...HEAD",
        timeout=120,
    )
    if not diff.strip():
        # A lane that found its bead already satisfied on master has nothing to
        # publish. Pushing it would open a pull request with no commits.
        outcome = {
            "outcome": HARVEST_EMPTY,
            "phase": "nothing-to-publish",
            "branch": branch,
            "head": head,
            "bead_id": bead_id,
            "close_reason": close_reason,
            "lane_trailer": _lane_trailer(context, lane_job_id=lane_job_id),
        }
        _append_event(
            context.spool,
            {"kind": "harvest", **outcome, "job_id": context.job_id},
        )
        return outcome
    if len(diff.encode()) > MAX_DIFF_BYTES:
        raise HarvestError("review diff exceeds its bounded artifact limit")
    changed_paths = tuple(
        path
        for path in _git(
            run, context.worktree, "diff", "--name-only", f"{context.base}...HEAD"
        ).splitlines()
        if path
    )
    write_scope = _lane_write_scope(context, lane_job_id=lane_job_id)
    oracle_command = oracle_command or _lane_oracle_command(context, lane_job_id=lane_job_id)
    oracle = _oracle_evidence(context, oracle_command, run) if oracle_command else None
    if oracle is not None and oracle["exit_code"] != 0:
        result = {
            "outcome": GATE_RED,
            "message": "harvest reality oracle is red",
            "oracle": oracle,
        }
        _append_event(context.spool, {"kind": "harvest", **result, "job_id": context.job_id})
        return result
    diffstat = _git(run, context.worktree, "diff", "--stat", f"{context.base}...HEAD")
    redflag_status, redflags = _redflags(
        diff, write_scope=write_scope, changed_paths=changed_paths
    )
    review_route = route_review(
        changed_paths=changed_paths,
        scanner_output="\n".join(redflags),
    )
    trailer = _lane_trailer(context, lane_job_id=lane_job_id)
    packet_id = _packet_id(context, head)
    diff_path = context.packet_root / f"{packet_id}.diff"
    diff_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(
        diff_path,
        os.O_CREAT | os.O_TRUNC | os.O_WRONLY | os.O_NOFOLLOW,
        0o600,
    )
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(diff.encode())
        handle.flush()
        os.fsync(handle.fileno())
    receipt = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "packet_id": packet_id,
        "phase": "review-required",
        "project_id": context.project_id,
        "workspace_id": context.workspace_id,
        "job_id": context.job_id,
        "branch": branch,
        "base": context.base,
        "head": head,
        "diffstat": diffstat,
        "lane_trailer": trailer,
        "write_scope": list(write_scope),
        "verification": _verification_evidence(context.worktree, head),
        "oracle": oracle,
        "redflags": redflags,
        "redflag_status": redflag_status,
        "review_route": review_route.to_dict(),
        "full_diff_ref": f"sinnix://jobs/{context.job_id}/artifacts/{packet_id}.diff",
        "worktree_unstaged_sha256": _digest(unstaged),
        "worktree_staged_sha256": _digest(staged),
        # The reviewed publication text is part of what the receipt binds:
        # .lane/ files are untracked, so HEAD equality alone would let text
        # change between review and publication (sinnix-3ynh).
        "publication_text": {
            "title_sha256": _digest(_lane_artifact(context, "title") or ""),
            "body_sha256": _digest(_lane_artifact(context, "body.md") or ""),
        },
        "bead_id": bead_id,
        "close_reason": close_reason,
        "created_at": _timestamp(),
    }
    _safe_json_write(_receipt_path(context, packet_id), receipt)
    _append_event(
        context.spool,
        {
            "kind": "harvest",
            "outcome": HARVEST_OK,
            "transition": "review-required",
            "project": context.project_id,
            "workspace_id": context.workspace_id,
            "job_id": context.job_id,
            "packet_id": packet_id,
        },
    )
    return {
        "outcome": HARVEST_OK,
        "phase": "review-required",
        "receipt_ref": f"sinnix://harvest/{packet_id}",
        "packet": receipt,
    }


def _load_receipt(context: HarvestContext, reference: str) -> dict[str, Any]:
    prefix = "sinnix://harvest/"
    packet_id = reference[len(prefix) :] if reference.startswith(prefix) else reference
    path = _receipt_path(context, packet_id)
    try:
        receipt = json.loads(path.read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HarvestError("harvest authorization receipt is unavailable") from error
    if (
        not isinstance(receipt, Mapping)
        or receipt.get("schema_version") != RECEIPT_SCHEMA_VERSION
        or receipt.get("packet_id") != packet_id
        or receipt.get("phase") != "review-required"
        or receipt.get("project_id") != context.project_id
        or receipt.get("workspace_id") != context.workspace_id
        or receipt.get("base") != context.base
        or not isinstance(receipt.get("head"), str)
    ):
        raise HarvestError("harvest authorization receipt is invalid")
    return dict(receipt)


def _stale_lock_hygiene(repo: Path) -> None:
    """Remove only the known zero-byte stale Git index locks."""
    git_dir = repo / ".git"
    if git_dir.is_file():
        try:
            git_dir = Path(
                subprocess.run(
                    ["git", "-C", str(repo), "rev-parse", "--git-dir"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=True,
                ).stdout.strip()
            )
            if not git_dir.is_absolute():
                git_dir = (repo / git_dir).resolve()
        except (OSError, subprocess.SubprocessError):
            return
    paths = (git_dir / "index.lock", *git_dir.glob("worktrees/*/index.lock"))
    for path in paths:
        try:
            if (
                path.is_file()
                and path.stat().st_size == 0
                and time.time() - path.stat().st_mtime > 180
            ):
                path.unlink()
        except OSError:
            continue


def _lock(path: Path, timeout: float = 900):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    handle = path.open("a+")
    deadline = time.monotonic() + timeout
    while True:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return handle
        except BlockingIOError:
            if time.monotonic() >= deadline:
                handle.close()
                raise HarvestError("harvest Git lock timeout") from None
            time.sleep(0.1)


def _restore_pre_harvest_state(
    worktree: Path,
    run: Run,
    *,
    branch: str,
    head: str,
) -> None:
    """Restore the checkout after a harvest mutation did not publish."""
    _command(run, ["git", "rebase", "--abort"], cwd=worktree)
    if branch:
        _require_success(
            _command(run, ["git", "switch", "--detach", head], cwd=worktree),
            "detach before restoring harvest branch",
        )
        _require_success(
            _command(run, ["git", "branch", "--force", branch, head], cwd=worktree),
            "restore harvest branch ref",
        )
        _require_success(
            _command(run, ["git", "switch", branch], cwd=worktree),
            "restore harvest branch checkout",
        )
    else:
        _require_success(
            _command(run, ["git", "reset", "--hard", head], cwd=worktree),
            "restore detached harvest checkout",
        )


def _mechanical_baseline_rebase(worktree: Path, output: str) -> bool:
    """Apply the one pure baseline displacement allowed by the reference flow."""
    start = output.find('"new_matches"')
    if start < 0:
        return False
    begin = output.rfind("{", 0, start)
    depth = 0
    end = -1
    for index, character in enumerate(output[begin:], begin):
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                end = index + 1
                break
    if begin < 0 or end < 0:
        return False
    try:
        payload = json.loads(output[begin:end])
    except json.JSONDecodeError:
        return False
    if not isinstance(payload, Mapping):
        return False
    pattern = re.compile(r"^(\S+) (\S+):(\d+)$")
    new: dict[tuple[str, str], list[int]] = {}
    stale: dict[tuple[str, str], list[int]] = {}
    for key, target in (("new_matches", new), ("stale_matches", stale)):
        rows = payload.get(key)
        if not isinstance(rows, list):
            return False
        for row in rows:
            match = pattern.match(row) if isinstance(row, str) else None
            if match is None:
                return False
            target.setdefault((match.group(1), match.group(2)), []).append(
                int(match.group(3))
            )
    if set(new) != set(stale) or any(len(new[key]) != len(stale[key]) for key in new):
        return False
    for (rule, path), new_lines in new.items():
        if not rule or "/" in rule or "\\" in rule or rule in {".", ".."}:
            return False
        baseline = worktree / "devtools" / "patterns" / "baselines" / f"{rule}.txt"
        try:
            text = baseline.read_text()
        except OSError:
            return False
        for old, current in zip(
            sorted(stale[(rule, path)]), sorted(new_lines), strict=True
        ):
            old_row = f"{path}:{old}\n"
            if old_row not in text:
                return False
            text = text.replace(old_row, f"{path}:{current}\n", 1)
        baseline.write_text(text)
    return True


def _gate(context: HarvestContext, run: Run) -> tuple[bool, str]:
    result = _command(
        run,
        ["devtools", "verify", "--quick"],
        cwd=context.worktree,
        timeout=900,
    )
    return result.returncode == 0, result.stdout + result.stderr


_UNAVAILABLE_DIAGNOSES = frozenset({"native_testmon_graph_unavailable"})


def _affected_refusal(worktree: Path) -> str | None:
    """Read the newest affected-run receipt and name a refusal to measure.

    ``devtools verify`` refuses without a compatible testmon graph by exiting
    non-zero and printing nothing, so the refusal is legible only in the typed
    receipt it writes. Returns a human-readable description when the receipt
    shows selection was unavailable, and ``None`` when tests genuinely ran.
    """
    runs = worktree / ".cache/verify/runs"
    try:
        records = sorted(runs.glob("*/run.json"))
    except OSError:
        return None
    for record in reversed(records):
        try:
            value = json.loads(record.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(value, Mapping) or value.get("tier") != "affected":
            continue
        diagnosis = value.get("diagnosis")
        selection = value.get("testmon_selection")
        state_status = (
            selection.get("state_status") if isinstance(selection, Mapping) else None
        )
        aggregate = value.get("pytest_aggregate")
        selection_mode = (
            aggregate.get("selection_mode") if isinstance(aggregate, Mapping) else None
        )
        unavailable = diagnosis in _UNAVAILABLE_DIAGNOSES or (
            state_status == "absent" and selection_mode == "none"
        )
        if not unavailable:
            return None
        reason = (
            selection.get("state_reason") if isinstance(selection, Mapping) else None
        )
        parts = [f"run {value.get('run_id')}: {diagnosis or 'selection unavailable'}"]
        if isinstance(reason, str) and reason:
            parts.append(reason)
        parts.append(
            "the affected selection did not run; this is a refusal to measure, "
            "not a failing test"
        )
        return "\n".join(parts)
    return None


def _affected_tests(context: HarvestContext, run: Run) -> tuple[str, str]:
    """Run the affected-test selection, outside the shared repository lock.

    The quick gate is static: nothing between a lane's own claim of a green
    test run and the protected branch actually executes tests. This does,
    against the lane's worktree, so it needs no lock and does not serialize
    other publications.

    Selection needs a compatible testmon graph and refuses without one. That
    refusal is reported as ``unavailable`` rather than treated as a failure,
    so publication is never blocked by a missing accelerator -- but it is
    named in the receipt instead of passing silently as if tests had run.

    The refusal is read from the typed run receipt, because the command that
    refuses exits non-zero and writes nothing to either stream.
    """
    result = _command(
        run,
        ["devtools", "verify"],
        cwd=context.worktree,
        timeout=AFFECTED_TIMEOUT_SECONDS,
    )
    output = result.stdout + result.stderr
    if result.returncode == 0:
        return "passed", output
    refusal = _affected_refusal(context.worktree)
    if refusal is not None:
        return "unavailable", "\n".join(part for part in (output, refusal) if part)
    if "testmon" in output.lower() and "refus" in output.lower():
        return "unavailable", output
    if not output.strip():
        output = (
            f"devtools verify exited {result.returncode} without output, and no "
            "affected run receipt explained it"
        )
    return "failed", output


def authorize(
    context: HarvestContext,
    *,
    receipt_ref: str,
    title: str,
    body: str,
    bead_id: str | None = None,
    close_reason: str | None = None,
    run: Run = subprocess.run,
) -> dict[str, Any]:
    """Publish only from a reviewed receipt, returning typed stop outcomes."""
    receipt = _load_receipt(context, receipt_ref)
    oracle = receipt.get("oracle")
    if oracle is not None and not _valid_oracle_receipt(oracle):
        raise HarvestError("harvest reality oracle receipt is invalid")
    current_head = _git(run, context.worktree, "rev-parse", "HEAD")
    if current_head != receipt["head"]:
        raise HarvestError(
            "harvest authorization receipt does not match workspace HEAD"
        )
    if any(
        receipt.get(field) != _digest(_git(run, context.worktree, *arguments))
        for field, arguments in (
            ("worktree_unstaged_sha256", ("diff", "HEAD")),
            ("worktree_staged_sha256", ("diff", "--cached")),
        )
    ):
        raise HarvestError(
            "harvest authorization receipt does not match worktree changes"
        )
    if bead_id is None and isinstance(receipt.get("bead_id"), str):
        bead_id = receipt["bead_id"]
    if close_reason is None and isinstance(receipt.get("close_reason"), str):
        close_reason = receipt["close_reason"]
    _require_publication_title(title)
    if len(body.encode()) > 64_000:
        raise HarvestError("harvest publication body is outside bounds")
    bound_text = receipt.get("publication_text")
    if isinstance(bound_text, Mapping):
        # Only text that existed at minting was reviewed; a receipt minted
        # without lane text binds nothing for that field.
        empty = _digest("")
        for field_name, value in (("title_sha256", title), ("body_sha256", body)):
            bound = bound_text.get(field_name)
            if bound not in (None, empty) and bound != _digest(value):
                raise HarvestError(
                    "harvest publication text differs from the reviewed "
                    "receipt; re-mint so the new text is reviewed"
                )

    # Execute tests before contending for the shared repository: this is the
    # only step in the chain that runs them, and it needs no lock.
    tests, tests_output = _affected_tests(context, run)
    if tests == "unavailable":
        # polylogue lanes have shipped static-only green for days because this
        # classification stayed inside the job result. The reactor and the
        # coordinator see it as a spool event from here on.
        _append_event(
            context.spool,
            {
                "kind": "verification-unavailable",
                "project": context.project_id,
                "workspace": context.workspace_id,
                "detail": _bounded_text(tests_output, 4_000),
                "job_id": context.job_id,
            },
        )
    if tests == "failed":
        result = {
            "outcome": GATE_RED,
            "message": "harvest affected verification is red",
            "gate_output": _bounded_text(tests_output, 64_000),
        }
        _append_event(
            context.spool, {"kind": "harvest", **result, "job_id": context.job_id}
        )
        return result

    repo = _repo_slug(run, context.worktree)
    pre_harvest_head = current_head
    pre_harvest_branch = _git(run, context.worktree, "branch", "--show-current")
    lock = _lock(LOCK_PATH)
    previous_sigterm = signal.getsignal(signal.SIGTERM)
    previous_sigint = signal.getsignal(signal.SIGINT)

    def cancel(_signum: int, _frame: Any) -> None:
        raise HarvestError("harvest cancelled")

    signal_handlers_installed = False
    try:
        signal.signal(signal.SIGTERM, cancel)
        signal.signal(signal.SIGINT, cancel)
        signal_handlers_installed = True
    except ValueError:
        # Tests and library callers may invoke authorize outside the main
        # thread. Exception cleanup still restores state in that case.
        pass
    published = False
    try:
        _stale_lock_hygiene(context.worktree)
        _require_success(
            _command(
                run, ["git", "fetch", "-q", "origin"], cwd=context.worktree, timeout=120
            ),
            "git fetch failed",
        )
        status = _command(
            run,
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=context.worktree,
        )
        if status.returncode != 0:
            raise HarvestError(status.stderr.strip() or "git status failed")
        if status.stdout:
            _command(
                run,
                ["ruff", "format", "polylogue/", "tests/", "devtools/"],
                cwd=context.worktree,
                timeout=300,
            )
            _command(
                run,
                ["ruff", "check", "--fix", "polylogue/", "tests/", "devtools/"],
                cwd=context.worktree,
                timeout=300,
            )
            _require_success(
                _command(run, ["git", "add", "-A", "."], cwd=context.worktree),
                "git add failed",
            )
            _require_success(
                _command(
                    run, ["git", "commit", "-q", "-m", title], cwd=context.worktree
                ),
                "git commit failed",
            )
        rebase = _command(
            run,
            ["git", "rebase", "-q", context.base],
            cwd=context.worktree,
            timeout=300,
        )
        if rebase.returncode != 0:
            _command(run, ["git", "rebase", "--abort"], cwd=context.worktree)
            result = {"outcome": REBASE_CONFLICT, "message": "harvest rebase conflict"}
            _append_event(
                context.spool, {"kind": "harvest", **result, "job_id": context.job_id}
            )
            return result
        passed, output = _gate(context, run)
        if not passed and not _mechanical_baseline_rebase(context.worktree, output):
            result = {
                "outcome": GATE_RED,
                "message": "harvest quick gate is red",
                "gate_output": _bounded_text(output, 64_000),
            }
            _append_event(
                context.spool, {"kind": "harvest", **result, "job_id": context.job_id}
            )
            return result
        if not passed:
            _require_success(
                _command(
                    run,
                    ["git", "add", "devtools/patterns/baselines/"],
                    cwd=context.worktree,
                ),
                "git add baseline failed",
            )
            _require_success(
                _command(
                    run,
                    ["git", "commit", "-q", "--amend", "--no-edit"],
                    cwd=context.worktree,
                ),
                "git amend baseline failed",
            )
            passed, output = _gate(context, run)
            if not passed:
                result = {
                    "outcome": GATE_RED,
                    "message": "harvest quick gate remains red",
                    "gate_output": _bounded_text(output, 64_000),
                }
                _append_event(
                    context.spool,
                    {"kind": "harvest", **result, "job_id": context.job_id},
                )
                return result
        _require_success(
            _command(
                run,
                ["git", "push", "-qf", "-u", "origin", "HEAD"],
                cwd=context.worktree,
                # The push runs the repository's pre-push gate, which is a
                # verification run, not a network round trip.
                timeout=PUSH_TIMEOUT_SECONDS,
            ),
            "git push failed",
        )
        created = _command(
            run,
            ["gh", "pr", "create", "--title", title, "--body", body],
            cwd=context.worktree,
            timeout=120,
        )
        if created.returncode != 0:
            # A publication that failed after the push leaves an open pull
            # request behind. Re-running must adopt it rather than refuse,
            # otherwise the lane can never reach master.
            pr_url = _adopt_open_pull_request(context, run, title=title, body=body)
            if pr_url is None:
                raise HarvestError(
                    created.stderr.strip() or "GitHub pull request creation failed"
                )
        else:
            pr_url = (
                created.stdout.strip().splitlines()[-1]
                if created.stdout.strip()
                else ""
            )
        pr = pr_url.rsplit("/", 1)[-1]
        if not pr.isdecimal():
            raise HarvestError("GitHub pull request number is malformed")
        merge = _command(
            run,
            ["gh", "pr", "merge", pr, "--squash", "--auto"],
            cwd=context.worktree,
            timeout=120,
        )
        merge_state = "ARMED" if merge.returncode == 0 else "NEEDS-MERGE"
        # The PR was created moments ago by this job: its own clock is the
        # opened_at authority, and arming exit status is the auto-merge state.
        # No gh pr view here -- releasing without polling is the contract.
        opened_at = _timestamp()
        check_states: list[str] = []
        auto_merge = merge.returncode == 0
        decision_receipt = (
            {
                "receipt_id": receipt["packet_id"],
                "bead_id": bead_id,
                "reason": close_reason,
            }
            if bead_id and close_reason
            else None
        )
        _append_event(
            context.spool,
            {
                "kind": "needs-merge",
                "project": context.project_id,
                "repo": repo,
                "pr": pr,
                "state": merge_state,
                "opened_at": opened_at,
                "check_states": check_states,
                "auto_merge": auto_merge,
                "decision_receipt": decision_receipt,
                "job_id": context.job_id,
                "merge_error": (
                    _bounded_text(merge.stderr or merge.stdout, 8_000)
                    if merge.returncode != 0
                    else None
                ),
            },
        )
        # The reactor owns post-publication merge observation and bead closure.
        # Returning here releases this job and its admission reservation.
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        state = merge_state
        result = {
            "outcome": HARVEST_OK,
            "phase": "published",
            "pr": pr,
            "pr_url": pr_url,
            "merge_state": state,
            "bead_id": bead_id,
            "affected_tests": tests,
        }
        published = True
        if tests != "passed":
            result["affected_tests_output"] = _bounded_text(tests_output, 8_000)
        _append_event(
            context.spool, {"kind": "harvest", **result, "job_id": context.job_id}
        )
        return result
    finally:
        if signal_handlers_installed:
            signal.signal(signal.SIGTERM, previous_sigterm)
            signal.signal(signal.SIGINT, previous_sigint)
        if not published:
            _restore_pre_harvest_state(
                context.worktree,
                run,
                branch=pre_harvest_branch,
                head=pre_harvest_head,
            )
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        lock.close()


def publish(
    context: HarvestContext,
    *,
    close: bool,
    run: Run = subprocess.run,
) -> dict[str, Any]:
    """Mint a fresh receipt and authorize it in one pass.

    The invocation itself is the review decision: the coordinator (or the
    reactor's clean-scan route) has decided to publish, so requiring a second
    job to restate receipt_ref, lane_job_id, bead_id, and publication text
    only re-keys facts the records already hold. Scanner flags are still
    computed and recorded on the receipt for audit.
    """
    lane_job_id, bead_id = _latest_lane_job(context)
    packet = compile_packet(
        context,
        lane_job_id=lane_job_id,
        bead_id=bead_id,
        run=run,
    )
    if packet.get("outcome") != HARVEST_OK:
        return packet
    title = _lane_artifact(context, "title") or ""
    body = _lane_artifact(context, "body.md") or ""
    close_reason = _lane_artifact(context, "close-reason.md") if close else None
    if close and not close_reason:
        raise HarvestError(
            "publish --close requires .lane/close-reason.md in the worktree"
        )
    return authorize(
        context,
        receipt_ref=packet["packet"]["packet_id"],
        title=title,
        body=body,
        bead_id=bead_id,
        close_reason=close_reason,
        run=run,
    )


def _context_from_environment(
    worktree: Path, *, base: str, spool: Path
) -> HarvestContext:
    job_dir = os.environ.get("SINNIXD_JOB_DIR")
    project_id = os.environ.get("SINNIXD_PROJECT_ID")
    workspace_id = os.environ.get("SINNIXD_CHECKOUT_ID")
    job_id = os.environ.get("SINNIXD_JOB_ID")
    if not all(
        isinstance(value, str) and value
        for value in (job_dir, project_id, workspace_id, job_id)
    ):
        raise HarvestError("declared harvest environment identity is incomplete")
    state_root = Path(job_dir).resolve().parent.parent
    return HarvestContext(
        worktree.resolve(strict=True),
        project_id,
        workspace_id,
        job_id,
        state_root,
        base,
        spool,
    )


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sinnixd-harvest")
    parser.add_argument("--authorize", action="store_true")
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--close", action="store_true")
    parser.add_argument("--receipt-ref")
    parser.add_argument("--lane-job-id")
    parser.add_argument("--title", default="")
    parser.add_argument("--title-file", type=Path)
    parser.add_argument("--body", default="")
    parser.add_argument("--body-file", type=Path)
    parser.add_argument("--bead-id")
    parser.add_argument("--close-reason")
    parser.add_argument("--close-reason-file", type=Path)
    parser.add_argument("--base", default=DEFAULT_BASE)
    parser.add_argument("--event-spool", type=Path, default=DEFAULT_SPOOL)
    parsed = parser.parse_args(arguments)
    try:
        context = _context_from_environment(
            Path.cwd(), base=parsed.base, spool=parsed.event_spool
        )
        if parsed.publish:
            result = publish(context, close=parsed.close)
        elif not parsed.authorize:
            result = compile_packet(
                context,
                lane_job_id=parsed.lane_job_id,
                bead_id=parsed.bead_id,
                close_reason=parsed.close_reason,
            )
        else:
            if not parsed.receipt_ref:
                raise HarvestError("--authorize requires --receipt-ref")
            title, body, close_reason = _resolve_publication_text(parsed, context)
            result = authorize(
                context,
                receipt_ref=parsed.receipt_ref,
                title=title,
                body=body,
                bead_id=parsed.bead_id,
                close_reason=close_reason,
            )
        print(json.dumps(result, sort_keys=True))
        return 0
    except HarvestError as error:
        result = {"outcome": HARVEST_ERROR, "message": str(error)}
        print(json.dumps(result, sort_keys=True))
        return 1


def harvest_cli() -> None:
    raise SystemExit(main())
