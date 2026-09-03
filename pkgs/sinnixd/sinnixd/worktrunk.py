"""The worktrunk (``wt``) adapter: worktree lifecycle and its published facts.

Sinnixd does not create, provision, classify, or remove worktrees. ``wt`` does,
against the project's own ``.config/wt.toml`` hooks, and publishes the result as
JSON. This module is the only place that shells out to it.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

# wt list schema 2 is the contract this module parses. wt still defaults to
# schema 1 and takes 2 only from user config, so every call pins it: sinnixd
# must not read a different shape because the invoking user configured one.
LIST_SCHEMA_VERSION = 2
_LIST_ARGUMENTS = (
    "--config-set",
    f"list.json-schema={LIST_SCHEMA_VERSION}",
    "list",
    "--format=json",
)
# --full adds the per-item `pr` and `checks` fields, at the cost of a forge
# round trip per worktree; only callers that read PR state pay for it.
_LIST_FULL_ARGUMENTS = (*_LIST_ARGUMENTS, "--full")

# wt's own six-check verdict that a branch's content is present on the default
# branch, squash-merge patch-id included. It replaces every local reimplementation
# of "has this landed".
INTEGRATED_STATE = "integrated"

# Removal is asynchronous by default; a caller that drops a workspace and then
# reports it gone must observe the removal, so every call passes --foreground.
_REMOVE_ARGUMENTS = ("--reap", "--foreground", "-y", "--format", "json")

# wt answers from local Git plus, for --prs, the forge. A minute covers a cold
# forge call; longer means wt is wedged, not slow.
CALL_TIMEOUT_SECONDS = 60


class WorktrunkError(RuntimeError):
    """``wt`` refused a request or published output this module cannot read."""


@dataclass(frozen=True)
class PullFacts:
    """A worktree item's ``pr`` field, published only with ``--full``."""

    number: int
    url: str
    mergeable: bool | None
    repo: str | None


@dataclass(frozen=True)
class ChecksFacts:
    """A worktree item's ``checks`` field, published only with ``--full``."""

    status: str | None
    source: str | None
    stale: bool | None


def _pull_facts(value: Any) -> PullFacts | None:
    if not isinstance(value, Mapping):
        return None
    number = value.get("number")
    url = value.get("url")
    if not isinstance(number, int) or not isinstance(url, str):
        return None
    mergeable = value.get("mergeable")
    repo = value.get("repo")
    return PullFacts(
        number=number,
        url=url,
        mergeable=mergeable if isinstance(mergeable, bool) else None,
        repo=repo if isinstance(repo, str) else None,
    )


def _checks_facts(value: Any) -> ChecksFacts | None:
    if not isinstance(value, Mapping):
        return None
    status = value.get("status")
    source = value.get("source")
    stale = value.get("stale")
    return ChecksFacts(
        status=status if isinstance(status, str) else None,
        source=source if isinstance(source, str) else None,
        stale=stale if isinstance(stale, bool) else None,
    )


@dataclass(frozen=True)
class Worktree:
    """One item of ``wt list --format=json``, reduced to what sinnixd reads."""

    # A detached worktree publishes no branch and a branch with no worktree
    # publishes no path. Both are ordinary listing entries, not read failures.
    branch: str | None
    path: Path | None
    head: str
    main: bool
    dirty: bool
    state: str
    # Present only when the caller asked for ``--full``; absent otherwise or
    # when the item carries no open PR.
    pr: PullFacts | None = None
    checks: ChecksFacts | None = None

    @property
    def integrated(self) -> bool:
        return self.state == INTEGRATED_STATE

    @classmethod
    def from_item(cls, item: Mapping[str, Any]) -> Worktree:
        worktree = item.get("worktree") or {}
        path = worktree.get("path")
        branch = item.get("branch")
        if not isinstance(path, str) and not isinstance(branch, str):
            raise WorktrunkError("wt list item has neither a branch nor a path")
        changes = worktree.get("changes") or {}
        return cls(
            branch=branch if isinstance(branch, str) else None,
            path=Path(path) if isinstance(path, str) else None,
            head=str((item.get("head") or {}).get("sha") or ""),
            main=bool(worktree.get("main")),
            dirty=any(
                bool(changes.get(field))
                for field in (
                    "staged",
                    "modified",
                    "untracked",
                    "renamed",
                    "deleted",
                    "conflicted",
                )
            ),
            state=str((item.get("display") or {}).get("state") or ""),
            pr=_pull_facts(item.get("pr")),
            checks=_checks_facts(item.get("checks")),
        )


def _run(root: Path, arguments: Sequence[str]) -> str:
    try:
        completed = subprocess.run(
            ["wt", "-C", str(root), *arguments],
            capture_output=True,
            text=True,
            timeout=CALL_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as error:
        raise WorktrunkError("wt is not installed") from error
    except subprocess.TimeoutExpired as error:
        raise WorktrunkError(f"wt {arguments[0]} timed out") from error
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise WorktrunkError(detail or f"wt {arguments[0]} failed")
    return completed.stdout


def _decode(payload: str, what: str) -> Any:
    # wt pretty-prints its JSON across lines and may precede it with progress
    # output, so the document runs from the first brace to the end of stdout.
    for index, character in enumerate(payload):
        if character in "{[":
            try:
                return json.loads(payload[index:])
            except json.JSONDecodeError:
                break
    raise WorktrunkError(f"wt {what} did not print a JSON document")


def worktrunk_list(root: Path, *, full: bool = False) -> tuple[Worktree, ...]:
    """Every worktree of the repository at ``root``, with wt's own state verdict.

    ``full=True`` also asks the forge for each item's PR and checks state.
    """
    document = _decode(
        _run(root, _LIST_FULL_ARGUMENTS if full else _LIST_ARGUMENTS), "list"
    )
    if not isinstance(document, Mapping):
        raise WorktrunkError("wt list did not print an object")
    schema = document.get("schema")
    if schema != LIST_SCHEMA_VERSION:
        raise WorktrunkError(
            f"wt list schema {schema!r} is not the supported {LIST_SCHEMA_VERSION}"
        )
    items = document.get("items")
    if not isinstance(items, Sequence):
        raise WorktrunkError("wt list published no items")
    return tuple(Worktree.from_item(item) for item in items)


def worktrunk_find(root: Path, branch: str) -> Worktree | None:
    return next((tree for tree in worktrunk_list(root) if tree.branch == branch), None)


def worktrunk_create(
    root: Path, branch: str, *, path: Path, base: str | None = None
) -> Worktree:
    """Create ``branch``'s worktree at ``path``, running the project's own hooks.

    The path is passed explicitly rather than left to the user's worktrunk
    config, because the project descriptor declares where its workspaces live and
    sinnixd validates the result against that declaration.
    """
    arguments = [
        "--config-set",
        f"worktree-path={json.dumps(str(path))}",
        "switch",
        branch,
        "--create",
        "--no-cd",
        "-y",
        "--format",
        "json",
    ]
    if base is not None:
        arguments.extend(["--base", base])
    document = _decode(_run(root, arguments), "switch")
    if not isinstance(document, Mapping) or not document.get("path"):
        raise WorktrunkError("wt switch published no worktree path")
    created = worktrunk_find(root, branch)
    if created is None:
        raise WorktrunkError(f"wt created {branch} but does not list it")
    return created


def worktrunk_remove(root: Path, branch: str, *, force: bool = False) -> None:
    """Remove ``branch``'s worktree and its local branch, killing its processes."""
    arguments = ["remove", branch, *_REMOVE_ARGUMENTS]
    if force:
        arguments.append("--force")
    _run(root, arguments)
