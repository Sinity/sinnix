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


def _redflags(diff: str) -> tuple[int, list[str]]:
    """Port the deterministic coordinator red-flag scanner."""
    flags: list[str] = []

    def flag(message: str) -> None:
        flags.append(f"FLAG: {message}")

    production = False
    tests = False
    production_removed = False
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
    if len(diff.encode()) > MAX_DIFF_BYTES:
        raise HarvestError("review diff exceeds its bounded artifact limit")
    diffstat = _git(run, context.worktree, "diff", "--stat", f"{context.base}...HEAD")
    redflag_status, redflags = _redflags(diff)
    changed_paths = tuple(
        path
        for path in _git(
            run, context.worktree, "diff", "--name-only", f"{context.base}...HEAD"
        ).splitlines()
        if path
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
        "verification": _verification_evidence(context.worktree, head),
        "redflags": redflags,
        "redflag_status": redflag_status,
        "review_route": review_route.to_dict(),
        "full_diff_ref": f"sinnix://jobs/{context.job_id}/artifacts/{packet_id}.diff",
        "worktree_unstaged_sha256": _digest(unstaged),
        "worktree_staged_sha256": _digest(staged),
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


def _watch_and_close(
    context: HarvestContext,
    *,
    repo: str,
    pr: str,
    bead_id: str | None,
    close_reason: str | None,
    run: Run,
    watch_attempts: int = 240,
    watch_delay: float = 30,
) -> str:
    state = ""
    for attempt in range(watch_attempts):
        result = _command(
            run,
            ["gh", "pr", "view", pr, "-R", repo, "--json", "state", "--jq", ".state"],
            cwd=context.worktree,
        )
        state = result.stdout.strip() if result.returncode == 0 else ""
        if state in {"MERGED", "CLOSED"}:
            break
        if attempt + 1 < watch_attempts:
            time.sleep(watch_delay)
    if state == "OPEN":
        state = "TIMEOUT"
    closed: bool | str = "skipped"
    if state == "MERGED" and bead_id and close_reason:
        result = _command(
            run,
            [
                "bd",
                "close",
                bead_id,
                "--force",
                "--actor",
                "claude-overseer",
                "--reason",
                close_reason,
            ],
            cwd=context.worktree,
        )
        closed = result.returncode == 0
    _append_event(
        context.spool,
        {
            "kind": "merge_close",
            "repo": repo,
            "pr": pr,
            "state": state or "TIMEOUT",
            "bead": bead_id,
            "bead_closed": closed,
            "job_id": context.job_id,
        },
    )
    return state or "TIMEOUT"


def authorize(
    context: HarvestContext,
    *,
    receipt_ref: str,
    title: str,
    body: str,
    bead_id: str | None = None,
    close_reason: str | None = None,
    run: Run = subprocess.run,
    watch: bool = True,
    watch_attempts: int = 240,
    watch_delay: float = 30,
) -> dict[str, Any]:
    """Publish only from a reviewed receipt, returning typed stop outcomes."""
    receipt = _load_receipt(context, receipt_ref)
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

    # Execute tests before contending for the shared repository: this is the
    # only step in the chain that runs them, and it needs no lock.
    tests, tests_output = _affected_tests(context, run)
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

    lock = _lock(LOCK_PATH)
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
            raise HarvestError(
                created.stderr.strip() or "GitHub pull request creation failed"
            )
        pr_url = (
            created.stdout.strip().splitlines()[-1] if created.stdout.strip() else ""
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
        _ = merge  # Auto-merge refusal is handled by the bounded watcher.
        # The watcher polls GitHub and closes a bead; it touches nothing in the
        # shared repository, so holding the lock through it would serialize
        # every other publication behind one merge.
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        state = (
            _watch_and_close(
                context,
                repo="Sinity/polylogue",
                pr=pr,
                bead_id=bead_id,
                close_reason=close_reason,
                run=run,
                watch_attempts=watch_attempts,
                watch_delay=watch_delay,
            )
            if watch
            else "ARMED"
        )
        result = {
            "outcome": HARVEST_OK,
            "phase": "published",
            "pr": pr,
            "pr_url": pr_url,
            "merge_state": state,
            "bead_id": bead_id,
            "affected_tests": tests,
        }
        if tests != "passed":
            result["affected_tests_output"] = _bounded_text(tests_output, 8_000)
        _append_event(
            context.spool, {"kind": "harvest", **result, "job_id": context.job_id}
        )
        return result
    finally:
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        lock.close()


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
    parser.add_argument("--no-watch", action="store_true")
    parsed = parser.parse_args(arguments)
    try:
        context = _context_from_environment(
            Path.cwd(), base=parsed.base, spool=parsed.event_spool
        )
        if not parsed.authorize:
            result = compile_packet(
                context,
                lane_job_id=parsed.lane_job_id,
                bead_id=parsed.bead_id,
                close_reason=parsed.close_reason,
            )
        else:
            if not parsed.receipt_ref:
                raise HarvestError("--authorize requires --receipt-ref")
            title = parsed.title
            if parsed.title_file is not None:
                title = _read_text(parsed.title_file, "publication title file")
            elif title is None:
                title = _lane_artifact(context, "title")
            body = parsed.body
            if parsed.body_file is not None:
                body = _read_text(parsed.body_file, "publication body file")
            elif body is None:
                body = _lane_artifact(context, "body.md")
            close_reason = parsed.close_reason
            if parsed.close_reason_file is not None:
                close_reason = _read_text(
                    parsed.close_reason_file, "bead close reason file"
                )
            elif close_reason is None:
                close_reason = _lane_artifact(context, "close-reason.md")
            result = authorize(
                context,
                receipt_ref=parsed.receipt_ref,
                title=title,
                body=body,
                bead_id=parsed.bead_id,
                close_reason=close_reason,
                watch=not parsed.no_watch,
            )
        print(json.dumps(result, sort_keys=True))
        return 0
    except HarvestError as error:
        result = {"outcome": HARVEST_ERROR, "message": str(error)}
        print(json.dumps(result, sort_keys=True))
        return 1


def harvest_cli() -> None:
    raise SystemExit(main())
