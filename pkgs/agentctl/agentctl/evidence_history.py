"""Bounded, read-only discovery of explicit task links in Git history.

This route is deliberately association-only.  A commit mentioning a bead is
useful historical evidence, but it is not a worker result, an acceptance
decision, or proof that any acceptance criterion was satisfied.
"""

from __future__ import annotations

import os
import re
import selectors
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .limits import CALL_TIMEOUT_SECONDS

# These are safety ceilings, not an attempt to estimate how much history a
# project has.  Callers can request less with ``limit``; they cannot ask this
# read route to materialize an unbounded history or output document.
DEFAULT_HISTORY_LIMIT = 100
MAX_HISTORY_LIMIT = 1_000
MAX_GIT_OUTPUT_BYTES = 4 * 1024 * 1024
MAX_GIT_ERROR_BYTES = 64 * 1024
MAX_IDENTIFIER_LENGTH = 128
MAX_REFERENCE_LENGTH = 256

_IDENTIFIER = re.compile(r"[A-Za-z0-9._-]+\Z")
_REF_FORBIDDEN = re.compile(r"[\x00-\x1f\x7f\s]")


class GitHistoryError(RuntimeError):
    """The bounded Git history read was invalid, unavailable, or too large."""


def _identifier(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise GitHistoryError(f"{name} must be a non-empty string")
    if len(value) > MAX_IDENTIFIER_LENGTH or _IDENTIFIER.fullmatch(value) is None:
        raise GitHistoryError(
            f"{name} must contain only ASCII letters, digits, '.', '_' or '-' "
            f"and be at most {MAX_IDENTIFIER_LENGTH} characters"
        )
    if value in {".", ".."}:
        raise GitHistoryError(f"{name} cannot be a relative path segment")
    return value


def _reference(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise GitHistoryError("ref must be a non-empty string")
    if len(value) > MAX_REFERENCE_LENGTH:
        raise GitHistoryError(f"ref exceeds {MAX_REFERENCE_LENGTH} characters")
    # Passing argv separately prevents shell injection, but a leading dash
    # would still be interpreted as a Git option.  Ref names containing
    # whitespace/control characters are not useful to this explicit reader.
    if value.startswith("-") or _REF_FORBIDDEN.search(value):
        raise GitHistoryError(
            "ref must be one explicit Git revision without options or whitespace"
        )
    return value


def _limit(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise GitHistoryError("limit must be an integer")
    if not 1 <= value <= MAX_HISTORY_LIMIT:
        raise GitHistoryError(f"limit must be between 1 and {MAX_HISTORY_LIMIT}")
    return value


def _canonical_reference(project: str, bead: str) -> str:
    # Project and bead identifiers are deliberately restricted above, so the
    # canonical form needs no URL encoding and remains easy to audit in logs.
    return f"sinnix://projects/{project}/beads/{bead}"


def _run_git(root: Path, reference: str, limit: int) -> bytes:
    # NUL delimiters keep line wrapping in a commit message from changing the
    # parser.  Git commit messages cannot contain NUL through normal commit
    # creation, and the trailing delimiter makes empty messages unambiguous.
    format_string = "%H%x00%cI%x00%B%x00"
    argv = [
        "git",
        "-C",
        str(root),
        "log",
        "--no-color",
        "--no-decorate",
        "--no-renames",
        f"--max-count={limit}",
        # ``pretty=format:`` (rather than ``format=``/tformat) avoids Git's
        # implicit newline between records; the explicit trailing NUL above
        # is the sole record delimiter consumed by ``_records``.
        f"--pretty=format:{format_string}",
        "--end-of-options",
        reference,
    ]
    try:
        process = subprocess.Popen(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        )
    except OSError as error:
        raise GitHistoryError(f"git history read failed in {root}: {error}") from error

    assert process.stdout is not None and process.stderr is not None
    limits = {process.stdout: MAX_GIT_OUTPUT_BYTES, process.stderr: MAX_GIT_ERROR_BYTES}
    buffers = {process.stdout: bytearray(), process.stderr: bytearray()}
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    selector.register(process.stderr, selectors.EVENT_READ)
    deadline = time.monotonic() + CALL_TIMEOUT_SECONDS
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise GitHistoryError(f"git history read timed out in {root}")
            ready = selector.select(remaining)
            if not ready:
                raise GitHistoryError(f"git history read timed out in {root}")
            for key, _event in ready:
                stream = key.fileobj
                chunk = os.read(stream.fileno(), 65_536)
                if not chunk:
                    selector.unregister(stream)
                    continue
                buffer = buffers[stream]
                buffer.extend(chunk)
                if len(buffer) > limits[stream]:
                    label = "history" if stream is process.stdout else "error"
                    bound = limits[stream]
                    raise GitHistoryError(
                        f"git history {label} output exceeds {bound} bytes"
                    )
        try:
            returncode = process.wait(timeout=max(0.001, deadline - time.monotonic()))
        except subprocess.TimeoutExpired as error:
            raise GitHistoryError(f"git history read timed out in {root}") from error
    finally:
        selector.close()
        if process.poll() is None:
            process.kill()
        process.wait(timeout=1)
        process.stdout.close()
        process.stderr.close()
    stdout = bytes(buffers[process.stdout])
    stderr = bytes(buffers[process.stderr])
    if returncode != 0:
        detail = stderr.decode("utf-8", "replace").strip() or "unknown git error"
        raise GitHistoryError(f"git log failed in {root}: {detail}")
    return stdout


def _records(raw: bytes) -> list[tuple[str, str, str]]:
    fields = raw.split(b"\0")
    records: list[tuple[str, str, str]] = []
    # Every record consists of SHA, committer timestamp, and body, followed by
    # one NUL delimiter.
    # A malformed stream is rejected rather than silently returning partial
    # historical evidence.
    if not raw:
        return records
    if len(fields) % 3 != 1 or fields[-1] != b"":
        raise GitHistoryError("git history output has an invalid record boundary")
    for index in range(0, len(fields) - 1, 3):
        sha, timestamp, body = fields[index : index + 3]
        # Pretty-format emits one separator newline before the next record;
        # it is outside the SHA field and is safe to discard here.
        sha = sha.lstrip(b"\n")
        try:
            sha_text = sha.decode("ascii")
            timestamp_text = timestamp.decode("ascii")
            body_text = body.decode("utf-8")
        except UnicodeDecodeError as error:
            raise GitHistoryError("git history output is not valid UTF-8") from error
        if re.fullmatch(r"[0-9a-fA-F]{40,64}", sha_text) is None:
            raise GitHistoryError("git history output contains an invalid commit SHA")
        if not timestamp_text:
            raise GitHistoryError(
                "git history output contains an empty commit timestamp"
            )
        records.append((sha_text, timestamp_text, body_text))
    return records


def _matches(body: str, bead: str, canonical: str) -> list[str]:
    # A task token is bounded by the same identifier characters accepted in a
    # bead id.  Thus ``sinnix-1`` does not match ``sinnix-10`` or a larger
    # identifier embedded in punctuation-free text.  Canonical references are
    # matched as complete URI tokens for the same reason.
    token = re.compile(rf"(?<![A-Za-z0-9._-]){re.escape(bead)}(?![A-Za-z0-9._-])")
    uri = re.compile(rf"(?<![A-Za-z0-9._-]){re.escape(canonical)}(?![A-Za-z0-9._/-])")
    # Do not reinterpret a foreign project's canonical URI as a bare bead
    # token.  It is an explicit reference, but not to the requested project.
    uri_prefix = re.compile(r"sinnix://projects/[A-Za-z0-9._-]+/beads/\Z")
    matches: list[str] = []
    if uri.search(body):
        matches.append(canonical)
    if any(
        not uri_prefix.search(body[: match.start()]) for match in token.finditer(body)
    ):
        matches.append(bead)
    return matches


def discover_git_history(
    root: Path,
    *,
    project: str,
    bead: str,
    reference: str = "HEAD",
    limit: int = DEFAULT_HISTORY_LIMIT,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    """Find explicit ``bead`` links in at most ``limit`` reachable commits.

    ``reference`` is an explicit Git revision (``HEAD`` by default).  The
    result is a JSON-ready document; all matching rows are associations only,
    and acceptance remains unknown regardless of commit contents.
    """
    if not isinstance(root, Path):
        raise GitHistoryError("root must be a pathlib.Path")
    if not root.is_dir():
        raise GitHistoryError(f"Git checkout does not exist: {root}")
    project_id = _identifier(project, "project")
    bead_id = _identifier(bead, "bead")
    ref = _reference(reference)
    count = _limit(limit)
    if observed_at is None:
        observed_at = datetime.now(UTC)
    if observed_at.tzinfo is None:
        raise GitHistoryError("observed_at must include a timezone")
    observed = observed_at.astimezone(UTC).isoformat()
    canonical = _canonical_reference(project_id, bead_id)
    parsed = _records(_run_git(root, ref, count))

    links: list[dict[str, Any]] = []
    for sha, timestamp, body in parsed:
        matched = _matches(body, bead_id, canonical)
        if not matched:
            continue
        links.append(
            {
                "commit_sha": sha,
                "timestamp": timestamp,
                "matched_reference": matched[0],
                "matched_references": matched,
                "observed_at": observed,
                "association_only": True,
                "acceptance": "unknown",
            }
        )

    return {
        "schema_version": 1,
        "kind": "git_history_discovery",
        "project": project_id,
        "bead": bead_id,
        "reference": ref,
        "links": links,
        "observed_at": observed,
        "association_only": True,
        "acceptance": "unknown",
        "coverage": {
            "source": "git",
            "reachable_from": ref,
            "commits_scanned": len(parsed),
            "max_commits": count,
            "complete": len(parsed) < count,
        },
        "bounds": {
            "limit": count,
            "max_limit": MAX_HISTORY_LIMIT,
            "max_output_bytes": MAX_GIT_OUTPUT_BYTES,
            "timeout_seconds": CALL_TIMEOUT_SECONDS,
        },
    }


# ``discover`` is the small callable name used by evidence route adapters;
# keep the descriptive name above available for direct callers and tests.
discover = discover_git_history
