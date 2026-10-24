"""Retain checkout-only evidence and Git recovery refs before worktree removal."""

from __future__ import annotations

import errno
import fcntl
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Iterator, Mapping, Sequence

from sinnix_lib.atomic import atomic_publish
from sinnix_lib.procfs import held_paths

from . import gitcmd, pueue, worktrunk
from .batch_history import Run, list_runs, load, manifest_path, runs_dir
from .limits import CALL_TIMEOUT_SECONDS
from .projects import ProjectAdapter
from .pueue import PueueError
from .worktrunk import WorktrunkError

if TYPE_CHECKING:
    from .config import Config


class CleanupError(RuntimeError):
    """A checkout or retained artifact cannot be inspected or safely released."""


@contextmanager
def _custody_lock(path: Path) -> Iterator[bool]:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    descriptor = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield True
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def project_locked(config: Config, project_id: str) -> Iterator[bool]:
    # Keep the established lock address while older recovery binaries exist.
    return _custody_lock(runs_dir(config) / f"{project_id}.lock")


def _update_custody(
    config: Config, run_id: str, retain: Callable[[dict[str, Any]], None]
) -> None:
    path = manifest_path(config, run_id)
    with _custody_lock(path.with_suffix(".lock")):
        document = load(config, run_id).to_dict()
        retain(document)
        Run.from_dict(document)
        atomic_publish(
            path,
            (json.dumps(document, indent=2, sort_keys=True) + "\n").encode(),
            fsync=False,
            mode=0o600,
        )


WORKTREE_STATE_DIR = ".agentctl"
_BATCH_BRANCH = re.compile(r"^batch/(?P<run>[^/]+)/[^/]+$")


def _git(
    path: Path,
    *arguments: str,
    timeout: float = CALL_TIMEOUT_SECONDS,
    owned: bool = False,
    main_checkout: bool = False,
) -> str:
    return gitcmd.git(
        path,
        *arguments,
        timeout=timeout,
        error=CleanupError,
        owned=owned,
        main_checkout=main_checkout,
    )


def _dirty_paths(path: Path) -> list[str]:
    return [
        line
        for line in _git(path, "status", "--porcelain=v1").splitlines()
        if not (line.startswith("??") and line[3:].startswith(f"{WORKTREE_STATE_DIR}/"))
    ]


def _empty_tree(path: Path) -> bool:
    pending, visited = [path], 0
    try:
        while pending:
            directory = pending.pop()
            visited += 1
            if visited > 256:
                return False
            for child in directory.iterdir():
                if child.is_symlink() or not child.is_dir():
                    return False
                pending.append(child)
    except OSError:
        return False
    return True


def _cargo_cache(path: Path, *, registered: bool) -> Path | None:
    target = path / "target"
    tag = target / "CACHEDIR.TAG"
    if target.is_symlink() or tag.is_symlink() or not target.is_dir():
        return None
    try:
        tagged = (
            tag.is_file()
            and tag.read_bytes().splitlines()[0]
            == b"Signature: 8a477f597d28d172789f06886806bc55"
        )
    except (OSError, IndexError):
        tagged = False
    if not tagged and not _empty_tree(target):
        return None
    if registered:
        if _git(path, "ls-files", "--", "target"):
            return None
        ignored = gitcmd.git(
            path, "check-ignore", "target", ok_statuses=(0, 1), error=CleanupError
        )
        if not ignored:
            return None
    return target


def _bytecode_cache(path: Path) -> bool:
    if path.name != "__pycache__" or path.is_symlink() or not path.is_dir():
        return False
    try:
        for child in path.iterdir():
            if child.is_symlink() or not child.is_file() or child.suffix != ".pyc":
                return False
            with child.open("rb") as handle:
                header = handle.read(16)
                if len(header) != 16 or header[2:4] != b"\r\n":
                    return False
    except OSError:
        return False
    return True


def _tagged_cache(path: Path) -> bool:
    tag = path / "CACHEDIR.TAG"
    if path.is_symlink() or not path.is_dir() or tag.is_symlink():
        return False
    try:
        return (
            tag.is_file()
            and tag.read_bytes().splitlines()[0]
            == b"Signature: 8a477f597d28d172789f06886806bc55"
        )
    except (OSError, IndexError):
        return False


def _ignored_caches(path: Path) -> tuple[Path, ...]:
    names = _git(
        path,
        "ls-files",
        "--others",
        "--ignored",
        "--exclude-standard",
        "--directory",
        "-z",
    )
    return tuple(
        path / name
        for name in names.split("\0")
        if name
        and path / name != path / "target"
        and (_bytecode_cache(path / name) or _tagged_cache(path / name))
    )


def _remove_cache(target: Path) -> None:
    """Retain the cache tag until a partial deletion is safely retryable."""
    tag = target / "CACHEDIR.TAG"
    for child in target.iterdir():
        if child == tag:
            continue
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()
    tag.unlink(missing_ok=True)
    target.rmdir()


def _external_cache(path: Path) -> Path | None:
    """Only the compiler selector's exact per-checkout cache, never a scan."""
    root = Path(os.environ.get("SINNIX_CARGO_CACHE_ROOT", "/realm/state/cache/cargo"))
    key = hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:32]
    parent = root / str(os.getuid()) / key
    target = parent / "target"
    if not _path_entry_exists(parent):
        return None
    if any(
        candidate.is_symlink() for candidate in (root, parent.parent, parent, target)
    ):
        raise CleanupError(f"compiler cache is symlinked; inspect {target}")
    if any(entry.name != "target" for entry in parent.iterdir()):
        raise CleanupError(f"compiler cache contains other evidence; inspect {parent}")
    if _cargo_cache(parent, registered=False) != target:
        raise CleanupError(f"compiler cache is not tagged or empty; inspect {target}")
    return target


def _under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _process_users(path: Path) -> list[str]:
    """Current-directory and open-file users outside pueue's authority.

    A same-user process whose /proc entries refuse a direct read is read
    through sudo; a foreign one outside our inspection authority is reported
    as neither an observed holder nor an observed non-holder.
    """
    users: list[str] = []
    proc = Path("/proc")
    try:
        entries = tuple(proc.iterdir())
    except OSError as error:
        raise CleanupError(f"cannot inspect process users: {error}") from error
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            cwds = [
                Path(target)
                for _, target in held_paths(
                    str(entry), links=("cwd",), descriptors=False
                )
            ]
        except PermissionError:
            if not _owned_by_us(entry):
                continue
            cwd = _stable_privileged_cwd(entry)
            cwds = [cwd] if cwd is not None else []
        except OSError as error:
            raise CleanupError(
                f"cannot inspect process {entry.name} cwd: {error}"
            ) from error
        if not cwds:
            continue
        if _under(cwds[0], path):
            users.append(f"pid {entry.name} cwd {cwds[0]}")
            continue
        try:
            targets = _process_open_files(entry)
        except PermissionError:
            if not _owned_by_us(entry):
                continue
            targets = _stable_privileged_open_files(entry)
        for target in targets:
            if target.is_absolute() and _under(target, path):
                users.append(f"pid {entry.name} open file {target}")
                break
    return users


def _owned_by_us(entry: Path) -> bool:
    try:
        return entry.stat().st_uid == os.getuid()
    except OSError as error:
        if error.errno in {errno.ENOENT, errno.ESRCH}:
            return False
        raise CleanupError(
            f"cannot inspect process {entry.name} ownership: {error}"
        ) from error


def _process_open_files(entry: Path) -> list[Path]:
    try:
        return [
            Path(target)
            for _, target in held_paths(str(entry), links=(), descriptors=True)
        ]
    except PermissionError:
        raise
    except OSError as error:
        raise CleanupError(
            f"cannot inspect process {entry.name} open files: {error}"
        ) from error


def _privileged_open_files(entry: Path) -> list[Path]:
    try:
        completed = subprocess.run(
            [
                "sudo",
                "-n",
                "find",
                str(entry / "fd"),
                "-maxdepth",
                "1",
                "-type",
                "l",
                "-printf",
                "%l\\0",
            ],
            capture_output=True,
            timeout=CALL_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise CleanupError(
            f"cannot inspect process {entry.name} open files: {error}"
        ) from error
    if completed.returncode != 0:
        raise CleanupError(
            f"cannot inspect process {entry.name} open files: {os.fsdecode(completed.stderr).strip()}"
        )
    return [
        Path(os.fsdecode(target)) for target in completed.stdout.split(b"\0") if target
    ]


def _stable_privileged_open_files(entry: Path) -> list[Path]:
    start = _process_starttime(entry)
    if start is None:
        return []
    try:
        targets = _privileged_open_files(entry)
    except CleanupError:
        if _process_starttime(entry) is None:
            return []
        raise
    end = _process_starttime(entry)
    if end is None:
        return []
    if end != start:
        raise CleanupError(f"process {entry.name} changed during open-file probe")
    return targets


def _process_starttime(entry: Path) -> str | None:
    try:
        payload = (entry / "stat").read_text()
        return payload.rsplit(")", 1)[1].split()[19]
    except OSError as error:
        if error.errno in {errno.ENOENT, errno.ESRCH}:
            return None
        raise CleanupError(f"cannot identify process {entry.name}: {error}") from error
    except IndexError as error:
        raise CleanupError(f"cannot identify process {entry.name}: {error}") from error


def _privileged_cwd(entry: Path) -> Path:
    try:
        completed = subprocess.run(
            ["sudo", "-n", "readlink", str(entry / "cwd")],
            capture_output=True,
            text=True,
            timeout=CALL_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise CleanupError(
            f"cannot inspect process {entry.name} cwd: {error}"
        ) from error
    if completed.returncode != 0 or not completed.stdout.strip():
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise CleanupError(f"cannot inspect process {entry.name} cwd: {detail}")
    return Path(completed.stdout.strip())


def _stable_privileged_cwd(entry: Path) -> Path | None:
    start = _process_starttime(entry)
    if start is None:
        return None
    try:
        cwd = _privileged_cwd(entry)
    except CleanupError:
        if _process_starttime(entry) is None:
            return None
        raise
    end = _process_starttime(entry)
    if end is None:
        return None
    if end != start:
        raise CleanupError(f"process {entry.name} changed during cwd probe")
    return cwd


def _task_users(path: Path) -> list[str]:
    try:
        tasks = pueue.tasks().values()
    except PueueError as error:
        raise CleanupError(f"cannot inspect pueue users: {error}") from error
    users = []
    for task in tasks:
        if task.terminal:
            continue
        try:
            task_path = Path(task.path)
        except TypeError:
            continue
        if task_path.is_absolute() and _under(task_path, path):
            users.append(f"task {task.task_id} {task.status.lower()} cwd {task_path}")
    return users


def _artifact_paths(path: Path, patterns: Sequence[str]) -> list[Path]:
    found: dict[Path, Path] = {}
    root = path.resolve()
    for pattern in patterns:
        for candidate in path.glob(pattern):
            if candidate.is_symlink():
                raise CleanupError(f"artifact path escapes checkout: {candidate}")
            if candidate.is_dir():
                continue
            if not _under(candidate, root):
                raise CleanupError(f"artifact path escapes checkout: {candidate}")
            try:
                mode = candidate.stat().st_mode
            except OSError as error:
                raise CleanupError(
                    f"cannot read artifact {candidate}: {error}"
                ) from error
            if not stat.S_ISREG(mode):
                raise CleanupError(f"artifact is not a regular file: {candidate}")
            found[candidate.relative_to(path)] = candidate
    return [found[key] for key in sorted(found)]


def _artifact_destination(
    config: Config, run_id: str, worktree: Path, relative: Path, digest: str
) -> Path:
    token = hashlib.sha256(str(worktree).encode()).hexdigest()[:16]
    return (
        config.state_dir
        / "artifacts"
        / run_id
        / token
        / relative.parent
        / f"{relative.name}.{digest[:16]}"
    )


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _preserve_artifacts(
    config: Config,
    project: ProjectAdapter,
    run_id: str | None,
    path: Path,
    *,
    artifacts: list[dict[str, str]],
) -> dict[str, str]:
    patterns = (
        f"{WORKTREE_STATE_DIR}/**/*",
        "target/nextest/**/*",
        *(project.workspace.retain_artifacts if project.workspace else ()),
    )
    replacements: dict[str, str] = {}
    for source in _artifact_paths(path, patterns):
        relative = source.relative_to(path)
        before = _digest(source)
        destination = _artifact_destination(
            config, run_id or "orphan", path, relative, before
        )
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(destination.parent, 0o700)
        if destination.exists():
            if _digest(destination) != before:
                raise CleanupError(f"artifact destination differs: {destination}")
        else:
            temporary = destination.with_suffix(destination.suffix + ".tmp")
            shutil.copyfile(source, temporary)
            if _digest(temporary) != before:
                temporary.unlink(missing_ok=True)
                raise CleanupError(f"artifact verification failed: {destination}")
            os.replace(temporary, destination)
        replacements[str(source)] = str(destination)
        artifacts.append({"source": str(source), "destination": str(destination)})
    return replacements


def _replace_paths(value: Any, replacements: Mapping[str, str]) -> Any:
    if isinstance(value, str):
        return replacements.get(value, value)
    if isinstance(value, list):
        return [_replace_paths(item, replacements) for item in value]
    if isinstance(value, dict):
        return {key: _replace_paths(item, replacements) for key, item in value.items()}
    return value


def _recovery_ref(root: Path, run_id: str | None, path: Path, head: str) -> str:
    token = hashlib.sha256(str(path).encode()).hexdigest()[:16]
    ref = f"refs/agentctl/recovery/{run_id or 'orphan'}/{token}/{head}"
    existing = gitcmd.git(
        root,
        "rev-parse",
        "--verify",
        "--quiet",
        f"{ref}^{{commit}}",
        ok_statuses=(0, 1),
        error=CleanupError,
    )
    if existing and existing != head:
        raise CleanupError(f"recovery ref differs: {ref}")
    if not existing:
        _git(root, "update-ref", ref, head)
    verified = _git(root, "rev-parse", "--verify", f"{ref}^{{commit}}")
    if verified != head:
        raise CleanupError(f"recovery ref did not retain {head}: {ref}")
    return ref


def _cleanup_obstacle(
    project: ProjectAdapter,
    path: Path,
    preserved: Mapping[str, str] | None = None,
    disposable: Sequence[Path] = (),
) -> str | None:
    """Git status alone cannot prove that checkout-only bytes are retained."""
    common = ("rev-parse", "--path-format=absolute", "--git-common-dir")
    if (
        Path(_git(path, *common)).resolve()
        != Path(_git(project.root, *common)).resolve()
    ):
        return "worktree kept; checkout belongs to another Git repository"
    for record in _git(path, "ls-files", "-v", "-z").split("\0"):
        if not record:
            continue
        if len(record) < 3 or record[1] != " ":
            raise CleanupError("cannot inspect checkout index flags")
        if record[0].islower() or record[0] == "S":
            return f"worktree kept; index flags hide tracked state: {record[2:]!r}"
    if preserved is None:
        return None
    sources = {Path(source) for source in preserved}
    covered_dirs = set()
    for source, destination in preserved.items():
        src, dst = Path(source), Path(destination)
        if not all(stat.S_ISREG(item.lstat().st_mode) for item in (src, dst)):
            return f"worktree kept; retained artifact is no longer a regular file: {source!r}"
        if _digest(src) != _digest(dst):
            return f"worktree kept; artifact changed after preservation: {source!r}"
        parent = src.parent
        while parent.is_relative_to(path):
            covered_dirs.add(parent)
            if parent == path:
                break
            parent = parent.parent
    pending = []
    for kind, flags in (("ignored", ("--ignored",)), ("untracked", ())):
        listing = _git(
            path,
            "ls-files",
            "--others",
            *flags,
            "--exclude-standard",
            "--directory",
            "-z",
        )
        pending.extend((path / name, kind) for name in listing.split("\0") if name)
    while pending:
        candidate, kind = pending.pop()
        if candidate in disposable:
            continue
        mode = candidate.lstat().st_mode
        if stat.S_ISDIR(mode):
            if candidate not in covered_dirs and _empty_tree(candidate):
                continue
            if candidate not in covered_dirs:
                return f"worktree kept; {kind} directory is not preserved: {str(candidate)!r}"
            with os.scandir(candidate) as children:
                for child in children:
                    child_path = Path(child.path)
                    if child.is_dir(follow_symlinks=False):
                        if child_path not in covered_dirs:
                            return f"worktree kept; {kind} directory is not preserved: {str(child_path)!r}"
                        pending.append((child_path, kind))
                    elif child_path not in sources:
                        return f"worktree kept; {kind} path is not preserved: {str(child_path)!r}"
        elif candidate not in sources:
            return f"worktree kept; {kind} path is not preserved: {str(candidate)!r}"
    return None


def _path_entry_exists(path: Path) -> bool:
    """Only a confirmed missing entry proves absence; preserve lookup errors."""
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    return True


def _drop_branch(
    config: Config,
    project: ProjectAdapter,
    branch: str,
    *,
    base: str,
    recorded_path: Path | None = None,
    run_id: str | None = None,
    artifacts: list[dict[str, str]] | None = None,
    delete_branch: bool = False,
    registry: Sequence[worktrunk.Worktree] | None = None,
    process_users: Callable[[Path], list[str]] | None = None,
    disposable: Sequence[Path] = (),
    expected_head: str | None = None,
    preserved_artifacts: Mapping[str, str] | None = None,
) -> str | None:
    """Release one terminal checkout while retaining its Git history.

    Returns why it was kept, or None once it is gone.
    """

    def retire_branch() -> None:
        head = gitcmd.git(
            project.root,
            "rev-parse",
            "--verify",
            "--quiet",
            f"refs/heads/{branch}^{{commit}}",
            ok_statuses=(0, 1),
            error=CleanupError,
        )
        if head:
            if expected_head is not None and head != expected_head:
                raise CleanupError("branch moved after publication proof")
            _recovery_ref(project.root, run_id, recorded_path or project.root, head)
            _git(project.root, "update-ref", "-d", f"refs/heads/{branch}", head)

    registry = (
        registry if registry is not None else worktrunk.worktrunk_list(project.root)
    )
    tree = next((tree for tree in registry if tree.branch == branch), None)
    if tree is None and recorded_path is None:
        tree = worktrunk.worktrunk_find(project.root, branch)
    process_users = process_users or _process_users
    if tree is not None and tree.locked:
        return "worktree kept; explicitly locked"
    path = tree.path if tree is not None else None
    removal_target = branch
    detached = False
    if recorded_path is not None:
        detached_tree = next(
            (
                item
                for item in registry
                if not item.main and item.branch is None and item.path == recorded_path
            ),
            None,
        )
        if detached_tree is not None:
            path = detached_tree.path
            removal_target = str(path)
            detached = True
    if path is None:
        try:
            if recorded_path is not None and _path_entry_exists(recorded_path):
                return f"worktree kept; checkout path is unregistered: {recorded_path}"
        except OSError as error:
            return f"worktree kept; cannot inspect recorded checkout: {error}"
        if delete_branch:
            try:
                retire_branch()
            except CleanupError as error:
                return f"branch kept; {error}"
        return None
    try:
        mode = path.stat().st_mode
    except FileNotFoundError:
        try:
            path.lstat()
        except FileNotFoundError:
            mode = None
        except OSError as error:
            return f"worktree kept; cannot inspect checkout: {error}"
        else:
            return "worktree kept; checkout path is a broken link"
    except OSError as error:
        return f"worktree kept; cannot inspect checkout: {error}"
    if mode is None:
        if removal_target == branch:
            return "worktree kept; checkout path is unavailable"
    elif not stat.S_ISDIR(mode):
        return "worktree kept; checkout path is not a directory"
    else:
        try:
            obstacle = _cleanup_obstacle(project, path)
            if obstacle:
                return obstacle
            dirty = _dirty_paths(path)
            users = [*_task_users(path), *process_users(path)]
        except (CleanupError, OSError) as error:
            return f"worktree kept; {error}"
        if dirty:
            return "worktree kept; uncommitted changes"
        if users:
            return f"worktree kept; active user: {users[0]}"
        try:
            head = _git(path, "rev-parse", "HEAD")
            if expected_head is not None and head != expected_head:
                return "worktree kept; HEAD changed after publication proof"
            branch_head = gitcmd.git(
                project.root,
                "rev-parse",
                "--verify",
                "--quiet",
                f"refs/heads/{branch}^{{commit}}",
                ok_statuses=(0, 1),
                error=CleanupError,
            )
            if detached or delete_branch:
                _recovery_ref(project.root, run_id, path, head)
            if not detached and branch_head != head:
                return "worktree kept; branch no longer names checkout HEAD"
            copied = (
                dict(preserved_artifacts)
                if preserved_artifacts is not None
                else _preserve_artifacts(
                    config,
                    project,
                    run_id,
                    path,
                    artifacts=artifacts if artifacts is not None else [],
                )
            )
            if copied and run_id is not None:

                def retain(document: dict[str, Any]) -> None:
                    replacements = dict(copied)
                    for artifact in document.get("artifacts", []):
                        source = artifact.get("source")
                        destination = artifact.get("destination")
                        if source in copied and isinstance(destination, str):
                            replacements[destination] = copied[source]
                    history = list(document.get("artifacts", []))
                    updated = _replace_paths(
                        {
                            key: value
                            for key, value in document.items()
                            if key != "artifacts"
                        },
                        replacements,
                    )
                    document.clear()
                    document.update(updated)
                    document["artifacts"] = [
                        *history,
                        *(
                            {"source": source, "destination": destination}
                            for source, destination in copied.items()
                        ),
                    ]

                _update_custody(config, run_id, retain)
            obstacle = _cleanup_obstacle(project, path, copied, disposable)
            if obstacle:
                return obstacle
            if _dirty_paths(path):
                return "worktree kept; uncommitted changes"
            if detached and _git(path, "rev-parse", "HEAD") != head:
                return "worktree kept; detached checkout HEAD changed"
            if not detached:
                branch_head = gitcmd.git(
                    project.root,
                    "rev-parse",
                    "--verify",
                    "--quiet",
                    f"refs/heads/{branch}^{{commit}}",
                    ok_statuses=(0, 1),
                    error=CleanupError,
                )
                if branch_head != head or branch_head != _git(
                    path, "rev-parse", "HEAD"
                ):
                    return "worktree kept; branch no longer names checkout HEAD"
            users = [*_task_users(path), *process_users(path)]
            if users:
                return f"worktree kept; active user: {users[0]}"
        except (CleanupError, OSError) as error:
            return f"worktree kept; {error}"
    try:
        for output in disposable:
            if (
                output.is_relative_to(path)
                and output != path / "target"
                and (_bytecode_cache(output) or _tagged_cache(output))
            ):
                _remove_cache(output)
                continue
            local = output.parent == path
            if (not local and _external_cache(path) != output) or _cargo_cache(
                output.parent, registered=local
            ) != output:
                raise CleanupError(f"build output changed before removal: {output}")
            print(f"removing build output {output}", file=sys.stderr, flush=True)
            _remove_cache(output)
            if not local:
                output.parent.rmdir()
        worktrunk.worktrunk_remove(
            project.root, removal_target, keep_branch=True, reap=False
        )
    except (WorktrunkError, CleanupError, OSError) as error:
        return str(error)
    try:
        if _path_entry_exists(path):
            return f"worktree kept; checkout path remains after removal: {path}"
    except OSError as error:
        return f"worktree kept; cannot verify checkout removal: {error}"
    if delete_branch:
        # The checkout is gone (or was already absent), so this ref can now be
        # removed without invalidating a registered worktree.
        try:
            retire_branch()
        except CleanupError as error:
            return f"branch kept; {error}"
    return None


def _drop_worktrees(
    config: Config, project: ProjectAdapter, run: Run, *, published: str | None = None
) -> list[str]:
    with project_locked(config, project.project_id):
        return _drop_worktrees_locked(config, project, run, published=published)


def _drop_worktrees_locked(
    config: Config, project: ProjectAdapter, run: Run, *, published: str | None = None
) -> list[str]:
    """Drop the run's worker and integration worktrees; name the ones kept.

    ``published`` is the candidate a landing published. The integration
    worktree is measured against it rather than against the run's base: its
    commits are out, so only uncommitted changes in it are still work.
    """
    branches = [
        (
            worker["branch"],
            run.base_commit,
            Path(worker["worktree"]) if worker.get("worktree") else None,
        )
        for worker in run.workers
    ]
    branches.append(
        (
            run.landing["integration_branch"],
            published or run.base_commit,
            (
                Path(run.landing["integration_worktree"])
                if run.landing.get("integration_worktree")
                else None
            ),
        )
    )
    residual: list[str] = []
    for branch, base, recorded_path in branches:
        kept = _drop_branch(
            config,
            project,
            branch,
            base=base,
            recorded_path=recorded_path,
            run_id=run.run_id,
        )
        if kept:
            residual.append(f"{branch}: {kept}")
    return residual


def _branch_reachable_from(root: Path, branch: str, base: str) -> bool:
    """Whether the branch tip is already preserved by the default branch."""
    try:
        gitcmd.git(
            root,
            "merge-base",
            "--is-ancestor",
            f"refs/heads/{branch}",
            base,
            error=CleanupError,
        )
    except CleanupError:
        return False
    return True


def clean(
    config: Config, project: ProjectAdapter, *, paths: Sequence[Path] | None = None
) -> dict[str, Any]:
    """Remove the worktrees of runs that are over. Run state, never age.

    A worktree is a candidate only when its branch names a batch run of this
    project that no longer holds its beads: landed, abandoned, or with no
    manifest left at all. It is removed only when nothing would be lost with
    it, and one that is kept is named with the reason.
    """
    try:
        default_base = _git(
            project.root,
            "rev-parse",
            "--verify",
            (
                f"{project.workspace.default_base}^{{commit}}"
                if project.workspace
                else "refs/remotes/origin/HEAD^{commit}"
            ),
        )
    except CleanupError:
        # Without a base every commit is judged by the refs that hold it,
        # which is the check that decides preservation anyway.
        default_base = ""
    selected = {path.absolute() for path in paths} if paths is not None else None
    removed: list[str] = []
    absent: list[str] = []
    kept: list[dict[str, str]] = []
    retained_artifacts: list[dict[str, str]] = []
    with project_locked(config, project.project_id):
        # Preparation holds this lock while creating checkouts. Read their
        # owners after acquiring it, including starts that just finished.
        runs = {
            run.run_id: run
            for run in list_runs(config, project.project_id, strict=True)
        }
        targets: list[tuple[str, Run | None, Path | None]] = []
        for owner in runs.values():
            if owner.live:
                continue
            targets.extend(
                (worker["branch"], owner, Path(worker["worktree"]))
                for worker in owner.workers
                if worker.get("worktree")
            )
            integration = owner.landing.get("integration_worktree")
            if integration:
                targets.append(
                    (owner.landing["integration_branch"], owner, Path(integration))
                )
        for tree in worktrunk.worktrunk_list(project.root):
            match = _BATCH_BRANCH.match(tree.branch or "")
            if tree.main or match is None:
                continue
            owner = runs.get(match.group("run"))
            if owner is not None:
                continue
            if owner is None and not match.group("run").startswith(
                f"{project.project_id}-"
            ):
                continue
            targets.append((str(tree.branch), owner, None))
        seen: set[tuple[str, Path | None]] = set()
        for branch, owner, recorded_path in targets:
            if selected is not None:
                target = recorded_path or next(
                    (
                        tree.path
                        for tree in worktrunk.worktrunk_list(project.root)
                        if tree.branch == branch
                    ),
                    None,
                )
                if target not in selected:
                    continue
            key = (branch, recorded_path)
            if key in seen:
                continue
            seen.add(key)
            registered = worktrunk.worktrunk_find(project.root, branch)
            if recorded_path is not None:
                registered = registered or next(
                    (
                        tree
                        for tree in worktrunk.worktrunk_list(project.root)
                        if not tree.main
                        and tree.branch is None
                        and tree.path == recorded_path
                    ),
                    None,
                )
            try:
                recorded_present = recorded_path is not None and _path_entry_exists(
                    recorded_path
                )
            except OSError as error:
                kept.append(
                    {
                        "branch": branch,
                        "reason": f"worktree kept; cannot inspect recorded checkout: {error}",
                    }
                )
                continue
            checkout_absent = (
                registered is None or registered.path is None
            ) and not recorded_present
            if registered is None or registered.path is None:
                if not recorded_present:
                    # A terminal manifest still owns the branch when its
                    # checkout has already disappeared.
                    may_delete = owner is not None and (
                        owner.acceptance is not None
                        or (
                            owner.abandoned is not None
                            and bool(default_base)
                            and _branch_reachable_from(
                                project.root, branch, default_base
                            )
                        )
                    )
                    if not may_delete:
                        if owner is not None and owner.abandoned is not None:
                            kept.append(
                                {
                                    "branch": branch,
                                    "reason": (
                                        "branch kept; commits are not reachable from default branch"
                                        if default_base
                                        else "branch kept; default branch could not be resolved"
                                    ),
                                }
                            )
                            continue
                        absent.append(branch)
                        continue
            copied: list[dict[str, str]] = []
            reason = _drop_branch(
                config,
                project,
                branch,
                base=owner.base_commit if owner else default_base,
                recorded_path=recorded_path,
                run_id=owner.run_id if owner else None,
                artifacts=copied,
                delete_branch=(
                    owner is not None
                    and (
                        owner.acceptance is not None
                        or (
                            owner.abandoned is not None
                            and bool(default_base)
                            and _branch_reachable_from(
                                project.root, branch, default_base
                            )
                        )
                    )
                ),
            )
            if reason:
                kept.append({"branch": branch, "reason": reason})
            elif checkout_absent:
                absent.append(branch)
            else:
                removed.append(branch)
            retained_artifacts.extend(copied)
    from .native_worktrees import clean_native

    native = clean_native(config, project, selected)
    removed.extend(native["removed"])
    kept.extend(native["kept"])
    retained_artifacts.extend(native["artifacts"])
    return {
        "project": project.project_id,
        "removed": removed,
        "absent": absent,
        "kept": kept,
        "artifacts": retained_artifacts,
    }


def clean_published(config: Config) -> list[dict[str, Any]]:
    """The existing queue maintenance also closes completed native checkouts."""
    from .native_worktrees import clean_native

    catalog = config.catalog()
    outcomes = []
    for row in catalog.list():
        project = catalog.get(row["id"])
        if next(config.inputs_dir.glob(project.project_id + "-*.json"), None) is None:
            continue
        try:
            outcomes.append(
                {"project": project.project_id, **clean_native(config, project)}
            )
        except (CleanupError, WorktrunkError, PueueError, OSError, ValueError) as error:
            outcomes.append({"project": project.project_id, "error": str(error)})
    return outcomes
