"""Host filesystem actions: paths in, canonical refs and typed content out."""

from __future__ import annotations

import base64
import binascii
import os
import stat as stat_module
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import Field
from ..owner_execution import (
    ExecutionProfile,
    ExecutionResult,
    OwnerExecution,
    OwnerRoute,
)

from .. import files as host_files
from ..action import (
    OBSERVER_OPERATOR,
    OPERATOR_ONLY,
    Action,
    ActionResult,
    Example,
    MutationControls,
    RequestControls,
)
from ..capabilities import Capability
from ..content import Artifact, attach, is_text, sha256_of, sniff_media_type
from ..contracts import VerbFamily
from ..files import FileError
from ..locators import FileLocator, encode_file_ref
from ..results import ProtocolError
from ..schemas import GatewayModel

if TYPE_CHECKING:
    from ..runtime import Runtime

Kind = Literal["file", "directory", "symlink", "other"]


def _kind(path: Path, *, follow: bool = True) -> Kind:
    if not follow and path.is_symlink():
        return "symlink"
    if path.is_dir():
        return "directory"
    if path.is_file():
        return "file"
    return "other"


def _iso(ns: int) -> str:
    return datetime.fromtimestamp(ns / 1e9, tz=timezone.utc).isoformat()


def _authorized(runtime: Runtime, locator: FileLocator, *, existing: bool) -> Path:
    path, _ref = locator.resolve()
    try:
        return runtime.files._resolve(path, existing=existing)
    except FileError as exc:
        code = "not_found" if "not exist" in str(exc) else "policy_denied"
        raise ProtocolError(code, str(exc)) from exc


def _secret_descendant_globs(runtime: Runtime, roots: list[Path]) -> list[str]:
    """Return ripgrep exclusions for observer-visible roots where possible."""
    if runtime.principal.name == "operator":
        return []
    globs: list[str] = []
    for root in roots:
        for secret_root in host_files._SECRET_ROOTS:
            try:
                relative = secret_root.resolve(strict=False).relative_to(root)
            except (ValueError, binascii.Error):
                continue
            if relative != Path("."):
                globs.append(f"!{relative.as_posix()}/**")
    return globs


class FileEntry(GatewayModel):
    ref: str
    path: str
    name: str
    kind: Kind
    bytes: int | None = None
    mtime: str | None = None
    symlink_target: str | None = None


class FileStat(FileEntry):
    mode: str
    uid: int
    gid: int
    owner: str | None = None
    atime: str
    ctime: str
    media_type: str | None = None
    sha256: str | None = None
    sha256_status: Literal[
        "computed", "not_requested", "not_applicable", "skipped_size"
    ]
    sha256_reason: str | None = None
    inode: int
    device: int
    affordances: list[str] = Field(default_factory=list)


class StatInput(RequestControls):
    target: FileLocator
    follow_symlinks: bool = True
    with_sha256: bool = Field(
        default=True, description="Hash a regular file within max_hash_bytes."
    )
    max_hash_bytes: int = Field(
        default=256 * 1024 * 1024,
        ge=0,
        description="Largest regular file hashed by this stat request; raise deliberately for larger files.",
    )


def _stat(runtime: Runtime, inp: StatInput) -> FileStat:
    runtime.principal.require(Capability.FILE_READ)
    raw_path, _ = inp.target.resolve()
    candidate = Path(raw_path)
    if inp.follow_symlinks:
        target = _authorized(runtime, inp.target, existing=True)
    else:
        target = candidate
        _authorized(runtime, FileLocator(path=str(candidate.parent)), existing=True)
        if not candidate.exists() and not candidate.is_symlink():
            raise ProtocolError("not_found", "path does not exist")
    details = target.lstat() if not inp.follow_symlinks else target.stat()
    kind = _kind(target, follow=inp.follow_symlinks)
    media = sniff_media_type(target) if kind == "file" else None
    digest = None
    if kind != "file":
        hash_status = "not_applicable"
        hash_reason = "only regular files have a SHA-256 digest"
    elif not inp.with_sha256:
        hash_status = "not_requested"
        hash_reason = "with_sha256 is false"
    elif details.st_size > inp.max_hash_bytes:
        hash_status = "skipped_size"
        hash_reason = (
            f"file is {details.st_size} bytes, above max_hash_bytes "
            f"({inp.max_hash_bytes} bytes)"
        )
    else:
        digest = sha256_of(target)
        hash_status = "computed"
        hash_reason = None
    try:
        import pwd

        owner = pwd.getpwuid(details.st_uid).pw_name
    except (KeyError, ImportError):
        owner = None
    affordances = ["files.read", "files.change"] if kind == "file" else []
    if kind == "directory":
        affordances = ["files.list", "files.search", "files.change"]
    return FileStat(
        ref=encode_file_ref(str(target)),
        path=str(target),
        name=target.name,
        kind=kind,
        bytes=details.st_size,
        mode=oct(stat_module.S_IMODE(details.st_mode)),
        uid=details.st_uid,
        gid=details.st_gid,
        owner=owner,
        mtime=_iso(details.st_mtime_ns),
        atime=_iso(details.st_atime_ns),
        ctime=_iso(details.st_ctime_ns),
        symlink_target=os.readlink(target) if target.is_symlink() else None,
        media_type=media,
        sha256=digest,
        sha256_status=hash_status,
        sha256_reason=hash_reason,
        inode=details.st_ino,
        device=details.st_dev,
        affordances=affordances,
    )


class ListInput(RequestControls):
    target: FileLocator
    limit: int = Field(default=200, ge=1)
    offset: int = Field(default=0, ge=0)
    include_hidden: bool = False
    sort: Literal["name", "mtime", "size"] = "name"
    descending: bool = False


class DirectoryListing(GatewayModel):
    ref: str
    path: str
    entries: list[FileEntry]
    total: int
    offset: int
    next_offset: int | None = None
    truncated: bool


def _entry(runtime: Runtime, child: Path) -> FileEntry | None:
    try:
        # Resolve each result, not just the requested root.  This rejects
        # secret descendants and symlinks that escape the authorized view.
        runtime.files._resolve(str(child), existing=True)
    except FileError:
        return None
    try:
        details = child.lstat()
    except OSError:
        return None
    kind = _kind(child, follow=False)
    if kind == "symlink":
        try:
            resolved = child.resolve()
            kind = (
                "directory"
                if resolved.is_dir()
                else "file"
                if resolved.is_file()
                else "symlink"
            )
        except OSError:
            pass
    return FileEntry(
        ref=encode_file_ref(str(child)),
        path=str(child),
        name=child.name,
        kind=kind,
        bytes=details.st_size if stat_module.S_ISREG(details.st_mode) else None,
        mtime=_iso(details.st_mtime_ns),
        symlink_target=os.readlink(child) if child.is_symlink() else None,
    )


def _list(runtime: Runtime, inp: ListInput) -> DirectoryListing:
    runtime.principal.require(Capability.FILE_READ)
    target = _authorized(runtime, inp.target, existing=True)
    if not target.is_dir():
        raise ProtocolError("invalid_request", "path is not a directory")
    try:
        children = [
            child
            for child in target.iterdir()
            if inp.include_hidden or not child.name.startswith(".")
        ]
    except PermissionError as exc:
        raise ProtocolError("policy_denied", "directory is not readable") from exc
    entries = [
        entry
        for entry in (_entry(runtime, child) for child in children)
        if entry is not None
    ]
    keys = {
        "name": lambda entry: entry.name.casefold(),
        "mtime": lambda entry: entry.mtime or "",
        "size": lambda entry: entry.bytes or 0,
    }
    entries.sort(key=keys[inp.sort], reverse=inp.descending)
    page = entries[inp.offset : inp.offset + inp.limit]
    truncated = inp.offset + inp.limit < len(entries)
    return DirectoryListing(
        ref=encode_file_ref(str(target)),
        path=str(target),
        entries=page,
        total=len(entries),
        offset=inp.offset,
        next_offset=inp.offset + inp.limit if truncated else None,
        truncated=truncated,
    )


class ReadInput(RequestControls):
    target: FileLocator
    offset: int = Field(default=0, ge=0, description="Byte offset for raw reads.")
    max_bytes: int = Field(
        default=64_000, ge=1, description="Maximum inline text bytes."
    )
    with_sha256: bool = Field(
        default=False,
        description="Compute a full-file SHA-256. Disabled by default for bounded reads.",
    )
    line_start: int | None = Field(
        default=None, ge=1, description="First line (1-based) for text reads."
    )
    line_count: int | None = Field(default=None, ge=1)
    representation: Literal["auto", "text"] = Field(
        default="auto",
        description="auto returns text inline and binary files as canonical read-only links.",
    )


class FileContent(GatewayModel):
    ref: str
    path: str
    media_type: str
    bytes: int = Field(description="Total size of the file.")
    sha256: str | None = None
    text: str | None = Field(
        default=None, description="Inline text when the file is textual."
    )
    offset: int = 0
    returned_bytes: int = 0
    truncated: bool = False
    line_start: int | None = None
    line_end: int | None = None
    total_lines: int | None = None
    artifact: Artifact | None = Field(
        default=None,
        description="Set for binary files; bytes are represented by a canonical read-only link.",
    )
    affordances: list[str] = Field(default_factory=list)


def _read(runtime: Runtime, inp: ReadInput) -> ActionResult:
    runtime.principal.require(Capability.FILE_READ)
    target = _authorized(runtime, inp.target, existing=True)
    if not target.is_file():
        raise ProtocolError("invalid_request", "path is not a regular file")
    ref = encode_file_ref(str(target))
    media = sniff_media_type(target)
    size = target.stat().st_size
    digest = sha256_of(target) if inp.with_sha256 else None
    textual = inp.representation == "text" or (
        inp.representation == "auto" and is_text(media)
    )
    max_bytes = inp.max_bytes
    base = {
        "ref": ref,
        "path": str(target),
        "media_type": media,
        "bytes": size,
        "sha256": digest,
        "affordances": [
            "files.change",
            "files.patch",
            "files.stat",
        ],
    }
    if textual:
        if inp.line_start is not None:
            with target.open("rb") as handle:
                start = inp.line_start
                count = inp.line_count or 200
                selected: list[bytes] = []
                returned = 0
                truncated = False
                for number, line in enumerate(handle, start=1):
                    if number < start:
                        continue
                    if len(selected) >= count:
                        truncated = True
                        break
                    remaining = max_bytes + 1 - returned
                    if remaining <= 0:
                        truncated = True
                        break
                    selected.append(line[:remaining])
                    returned += len(selected[-1])
                    if len(line) > len(selected[-1]):
                        truncated = True
                        break
                    if len(selected) >= count:
                        truncated = bool(handle.read(1))
                        break
            data = b"".join(selected)
            if data.endswith(b"\n"):
                data = data[:-1]
            truncated = truncated or len(data) > max_bytes
            data = data[:max_bytes]
            return ActionResult(
                FileContent(
                    **base,
                    text=data.decode("utf-8", errors="replace"),
                    returned_bytes=len(data),
                    truncated=truncated,
                    line_start=start,
                    line_end=start + len(selected) - 1 if selected else None,
                    total_lines=None,
                )
            )
        with target.open("rb") as handle:
            handle.seek(inp.offset)
            data = handle.read(max_bytes + 1)
        truncated = len(data) > max_bytes
        data = data[:max_bytes]
        return ActionResult(
            FileContent(
                **base,
                text=data.decode("utf-8", errors="replace"),
                offset=inp.offset,
                returned_bytes=len(data),
                truncated=truncated,
            )
        )
    artifact, blocks = attach(
        target,
        ref=ref,
        media_type=media,
        sha256=digest,
        compute_sha256=inp.with_sha256,
    )
    return ActionResult(
        FileContent(**base, artifact=artifact, returned_bytes=0),
        blocks=blocks,
    )


ACTIONS: tuple[Action, ...] = (
    Action(
        name="files.stat",
        family=VerbFamily.QUERY,
        owner="files",
        summary="Describe one host path: kind, size, mode, owner, timestamps, MIME, hash.",
        Input=StatInput,
        Output=FileStat,
        handler=_stat,
        principals=OBSERVER_OPERATOR,
        resource_kinds=("host_file",),
        affordances=("files.read", "files.list", "files.change"),
        aliases=("file info", "metadata", "size", "permissions"),
        examples=(
            Example(title="Stat a file", input={"target": {"path": "/etc/os-release"}}),
        ),
    ),
    Action(
        name="files.list",
        family=VerbFamily.QUERY,
        owner="files",
        summary="List a directory with a canonical ref for every child.",
        Input=ListInput,
        Output=DirectoryListing,
        handler=_list,
        principals=OBSERVER_OPERATOR,
        resource_kinds=("host_file",),
        affordances=("files.stat", "files.read", "files.search"),
        aliases=("ls", "directory", "folder", "browse"),
        examples=(
            Example(title="List /realm/tmp", input={"target": {"path": "/realm/tmp"}}),
        ),
    ),
    Action(
        name="files.read",
        family=VerbFamily.QUERY,
        owner="files",
        summary="Read a file: text inline, images as image blocks, other binary as read-only links.",
        Input=ReadInput,
        Output=FileContent,
        handler=_read,
        principals=OBSERVER_OPERATOR,
        resource_kinds=("host_file",),
        affordances=("files.patch", "files.change", "files.stat"),
        aliases=("cat", "open", "view", "image", "picture", "screenshot file"),
        examples=(
            Example(
                title="Read /etc/os-release",
                input={"target": {"path": "/etc/os-release"}},
            ),
            Example(
                title="Lines 10-30 of a log",
                input={
                    "target": {"path": "/var/log/example.log"},
                    "line_start": 10,
                    "line_count": 21,
                },
            ),
        ),
    ),
)


# --------------------------------------------------------------------- search


class SearchInput(RequestControls):
    roots: list[FileLocator] = Field(min_length=1, max_length=8)
    name_glob: str | None = Field(
        default=None, max_length=512, description="Glob on the file name, e.g. *.png"
    )
    path_regex: str | None = Field(
        default=None, max_length=512, description="Regex on the full path."
    )
    extensions: list[str] = Field(default_factory=list, max_length=32)
    kind: Literal["any", "file", "directory", "symlink"] = "any"
    min_bytes: int | None = Field(default=None, ge=0)
    max_bytes: int | None = Field(default=None, ge=0)
    modified_within_seconds: int | None = Field(default=None, ge=1)
    max_depth: int | None = Field(default=None, ge=1, le=64)
    include_hidden: bool = False
    respect_ignore_files: bool = Field(
        default=True, description="Honour .gitignore and similar files."
    )
    content_regex: str | None = Field(
        default=None,
        max_length=1_024,
        description="Search file contents; returns matching lines with context.",
    )
    fixed_string: bool = Field(
        default=False, description="Treat content_regex as a literal string."
    )
    case_insensitive: bool = False
    context_lines: int = Field(default=0, ge=0, le=5)
    limit: int = Field(default=100, ge=1)
    timeout_seconds: int = Field(default=30, ge=1, le=300)


class MatchLine(GatewayModel):
    line_number: int
    text: str
    is_match: bool = True


class FileMatch(FileEntry):
    lines: list[MatchLine] = Field(default_factory=list)
    match_count: int | None = None


class SearchResult(GatewayModel):
    roots: list[str] = Field(description="Canonical refs of the searched roots.")
    matches: list[FileMatch]
    returned: int
    truncated: bool
    engine: Literal["fd", "rg"]
    timed_out: bool = False
    warnings: list[str] = Field(default_factory=list)


def _run(
    argv: list[str],
    timeout: int,
    *,
    max_stderr_bytes: int,
    on_stdout: Callable[[bytes], None],
) -> ExecutionResult:
    """Stream a declared search owner without retaining aggregate stdout.

    Search output is parsed as it arrives.  The typed result layer applies the
    client response bound afterwards and, when needed, retains the complete
    structured result as an attested artifact.
    """
    return OwnerExecution().run(
        argv,
        ExecutionProfile(
            route=OwnerRoute("files-search"),
            timeout_seconds=timeout,
            max_stdout_bytes=1,
            max_stderr_bytes=max_stderr_bytes,
        ),
        stdout_chunk_callback=on_stdout,
    )


def _raise_search_failure(argv: list[str], result: ExecutionResult) -> None:
    if result.timed_out:
        return
    if result.failure_class and result.failure_class.startswith("command_unavailable"):
        raise ProtocolError("unavailable", f"{argv[0]} is not installed")
    if result.exit_status in (0, 1) and not result.output_exceeded:
        return
    diagnostic = result.stderr.decode("utf-8", "replace").strip()
    code = (
        "invalid_request"
        if "regex parse error" in diagnostic.lower()
        else "owner_failed"
    )
    raise ProtocolError(
        code,
        diagnostic
        or f"{argv[0]} failed with {result.failure_class or f'exit status {result.exit_status}'}",
        details={"command": argv[0], "exit_status": result.exit_status},
    )


def _search(runtime: Runtime, inp: SearchInput) -> SearchResult:
    runtime.principal.require(Capability.FILE_READ)
    roots = [_authorized(runtime, root, existing=True) for root in inp.roots]
    root_refs = [encode_file_ref(str(root)) for root in roots]
    warnings: list[str] = []
    if inp.content_regex is not None and inp.path_regex:
        import re

        try:
            path_pattern = re.compile(inp.path_regex)
        except re.error as exc:
            raise ProtocolError(
                "invalid_request", f"invalid path_regex: {exc}"
            ) from exc
    else:
        path_pattern = None
    if inp.content_regex is not None:
        argv = ["rg", "--json", "--no-messages"]
        for glob in _secret_descendant_globs(runtime, roots):
            argv.extend(["--glob", glob])
        if inp.fixed_string:
            argv.append("--fixed-strings")
        if inp.case_insensitive:
            argv.append("--ignore-case")
        if inp.include_hidden:
            argv.append("--hidden")
        if not inp.respect_ignore_files:
            argv.append("--no-ignore")
        if inp.max_depth is not None:
            argv.append(f"--max-depth={inp.max_depth}")
        if inp.context_lines:
            argv.append(f"--context={inp.context_lines}")
        if inp.name_glob:
            argv.extend(["--glob", inp.name_glob])
        for extension in inp.extensions:
            argv.extend(["--glob", f"*.{extension.lstrip('.')}"])
        if inp.max_bytes is not None:
            argv.append(f"--max-filesize={inp.max_bytes}")
        argv.extend(["--regexp", inp.content_regex, "--", *map(str, roots)])
        import json as json_module
        import time

        by_path: dict[str, FileMatch] = {}
        limit_reached = False
        pending = bytearray()

        def warn_once(message: str) -> None:
            if message not in warnings:
                warnings.append(message)

        def rg_text(value: object, *, field: str, path: bool = False) -> str | None:
            if not isinstance(value, dict):
                warn_once(f"ripgrep emitted malformed {field} data")
                return None
            text = value.get("text")
            if isinstance(text, str):
                return text
            encoded = value.get("bytes")
            if not isinstance(encoded, str):
                warn_once(f"ripgrep omitted {field} text")
                return None
            try:
                raw = base64.b64decode(encoded, validate=True)
            except ValueError:
                warn_once(f"ripgrep emitted invalid base64 {field} data")
                return None
            if path:
                decoded = os.fsdecode(raw)
                if any("\udc80" <= character <= "\udcff" for character in decoded):
                    warn_once("ripgrep emitted a non-UTF-8 path; decoded losslessly")
                return decoded
            decoded = raw.decode("utf-8", "replace")
            if "\ufffd" in decoded:
                warn_once(
                    "ripgrep emitted non-UTF-8 line content; replacement characters were used"
                )
            return decoded

        def consume_record(raw: bytes) -> None:
            nonlocal limit_reached
            if not raw:
                return
            try:
                event = json_module.loads(raw)
            except ValueError:
                return
            kind = event.get("type")
            data = event.get("data", {})
            if not isinstance(data, dict):
                warn_once("ripgrep emitted malformed match data")
                return
            path_text = rg_text(data.get("path"), field="path", path=True)
            if not path_text or kind not in {"match", "context"}:
                return
            candidate = Path(path_text)
            try:
                runtime.files._resolve(str(candidate), existing=True)
            except FileError:
                return
            try:
                details = candidate.stat()
            except OSError:
                return
            candidate_kind = _kind(candidate, follow=False)
            if inp.kind != "any" and candidate_kind != inp.kind:
                return
            if inp.min_bytes is not None and details.st_size < inp.min_bytes:
                return
            if inp.max_bytes is not None and details.st_size > inp.max_bytes:
                return
            if (
                inp.modified_within_seconds is not None
                and time.time() - details.st_mtime > inp.modified_within_seconds
            ):
                return
            if path_pattern is not None and not path_pattern.search(str(candidate)):
                return
            entry = by_path.get(path_text)
            if entry is None:
                if len(by_path) >= inp.limit:
                    limit_reached = True
                    return
                base = _entry(runtime, candidate)
                if base is None:
                    return
                entry = FileMatch(**base.model_dump(), match_count=0)
                by_path[path_text] = entry
            line = rg_text(data.get("lines"), field="line")
            if line is None:
                return
            entry.lines.append(
                MatchLine(
                    line_number=int(data.get("line_number") or 0),
                    text=line.rstrip("\n"),
                    is_match=kind == "match",
                )
            )
            if kind == "match":
                entry.match_count = (entry.match_count or 0) + 1

        def consume(chunk: bytes) -> None:
            pending.extend(chunk)
            while (newline := pending.find(b"\n")) >= 0:
                raw = bytes(pending[:newline])
                del pending[: newline + 1]
                consume_record(raw)

        result = _run(
            argv,
            inp.timeout_seconds,
            max_stderr_bytes=runtime.config.max_result_bytes,
            on_stdout=consume,
        )
        # A killed command can leave one partial JSON record.  It does not
        # describe a complete match, so only consume a final unterminated row
        # after normal completion.
        if pending and not result.timed_out:
            consume_record(bytes(pending))
        _raise_search_failure(argv, result)
        matches = list(by_path.values())
        return SearchResult(
            roots=root_refs,
            matches=matches,
            returned=len(matches),
            truncated=limit_reached or result.timed_out,
            engine="rg",
            timed_out=result.timed_out,
            warnings=warnings,
        )
    argv = ["fd", "--print0", "--absolute-path", f"--max-results={inp.limit + 1}"]
    if inp.include_hidden:
        argv.append("--hidden")
    if not inp.respect_ignore_files:
        argv.append("--no-ignore")
    if inp.max_depth is not None:
        argv.append(f"--max-depth={inp.max_depth}")
    if inp.kind != "any":
        argv.append(
            f"--type={ {'file': 'f', 'directory': 'd', 'symlink': 'l'}[inp.kind] }"
        )
    for extension in inp.extensions:
        argv.append(f"--extension={extension.lstrip('.')}")
    if inp.min_bytes is not None:
        argv.append(f"--size=+{inp.min_bytes}b")
    if inp.max_bytes is not None:
        argv.append(f"--size=-{inp.max_bytes}b")
    if inp.modified_within_seconds is not None:
        argv.append(f"--changed-within={inp.modified_within_seconds}s")
    if inp.case_insensitive:
        argv.append("--ignore-case")
    else:
        argv.append("--case-sensitive")
    if inp.name_glob and inp.path_regex:
        raise ProtocolError("invalid_request", "give name_glob or path_regex, not both")
    if inp.name_glob:
        argv.extend(["--glob", inp.name_glob])
    elif inp.path_regex:
        argv.extend(["--full-path", inp.path_regex])
    else:
        argv.append(".")
    argv.extend(["--"] if not (inp.name_glob or inp.path_regex) else [])
    argv.extend(str(root) for root in roots)
    entries: list[FileEntry] = []
    path_count = 0
    pending = bytearray()

    def consume_path(raw: bytes) -> None:
        nonlocal path_count
        if not raw:
            return
        path_count += 1
        if path_count > inp.limit:
            return
        entry = _entry(runtime, Path(raw.decode("utf-8", "surrogateescape")))
        if entry is not None:
            entries.append(entry)

    def consume(chunk: bytes) -> None:
        pending.extend(chunk)
        while (separator := pending.find(b"\0")) >= 0:
            raw = bytes(pending[:separator])
            del pending[: separator + 1]
            consume_path(raw)

    result = _run(
        argv,
        inp.timeout_seconds,
        max_stderr_bytes=runtime.config.max_result_bytes,
        on_stdout=consume,
    )
    if pending and not result.timed_out:
        consume_path(bytes(pending))
    _raise_search_failure(argv, result)
    return SearchResult(
        roots=root_refs,
        matches=[FileMatch(**entry.model_dump()) for entry in entries],
        returned=len(entries),
        truncated=path_count > inp.limit or result.timed_out,
        engine="fd",
        timed_out=result.timed_out,
        warnings=warnings,
    )


# ---------------------------------------------------------------------- patch


class UnifiedPatch(GatewayModel):
    mode: Literal["unified"] = "unified"
    patch: str = Field(
        min_length=1,
        max_length=1_048_576,
        description="Unified diff hunks for this one file (--- / +++ headers optional).",
    )


class RangeReplace(GatewayModel):
    mode: Literal["range"] = "range"
    start_line: int = Field(ge=1, description="First line to replace, 1-based.")
    end_line: int = Field(
        ge=0,
        description="Last line to replace inclusive; start_line-1 inserts before start_line.",
    )
    replacement: str = Field(max_length=1_048_576)
    expected_text: str | None = Field(
        default=None,
        max_length=1_048_576,
        description="If given, the current lines in the range must equal this text.",
    )


class PatchInput(MutationControls):
    target: FileLocator
    edit: UnifiedPatch | RangeReplace = Field(discriminator="mode")
    expected_sha256: str | None = Field(
        default=None,
        pattern="^[0-9a-f]{64}$",
        description="Hash from the prior read; the edit is refused if the file changed.",
    )
    dry_run: bool = Field(default=False, description="Validate without writing.")


class RejectedHunk(GatewayModel):
    index: int
    reason: str
    header: str


class PatchResult(GatewayModel):
    ref: str
    path: str
    mode: Literal["unified", "range"]
    dry_run: bool
    applied_hunks: int
    rejected_hunks: list[RejectedHunk] = Field(default_factory=list)
    before_sha256: str
    after_sha256: str
    bytes: int
    lines_before: int
    lines_after: int
    affordances: list[str] = Field(default_factory=list)


def _split_lines(text: str) -> list[str]:
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def _single_file_patch(patch: str, filename: str) -> tuple[str, list[str]]:
    """Normalize optional headers while enforcing the one-file patch boundary."""
    import re

    lines = patch.splitlines(keepends=True)
    hunk_pattern = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
    first_hunk = next(
        (index for index, line in enumerate(lines) if hunk_pattern.match(line)),
        len(lines),
    )
    old_headers = [
        index
        for index, line in enumerate(lines[:first_hunk])
        if line.startswith("--- ")
    ]
    new_headers = [
        index
        for index, line in enumerate(lines[:first_hunk])
        if line.startswith("+++ ")
    ]
    if len(old_headers) != len(new_headers):
        raise ProtocolError("invalid_request", "patch has an incomplete file header")
    if len(old_headers) > 1:
        raise ProtocolError("invalid_request", "patch must identify one file")

    def header_path(line: str) -> str:
        return line[4:].split("\t", 1)[0].rstrip("\r\n")

    if old_headers:
        old_path = header_path(lines[old_headers[0]])
        new_path = header_path(lines[new_headers[0]])
        if old_path in {"/dev/null", "dev/null"} or new_path in {
            "/dev/null",
            "dev/null",
        }:
            raise ProtocolError(
                "invalid_request", "patch must update the existing file"
            )
        old_path = old_path.removeprefix("a/")
        new_path = new_path.removeprefix("b/")
        if (old_path, new_path) not in {("a", "b"), (filename, filename)}:
            raise ProtocolError("invalid_request", "patch targets a different file")
        normalized = list(lines)
        normalized[old_headers[0]] = f"--- a/{filename}\n"
        normalized[new_headers[0]] = f"+++ b/{filename}\n"
    else:
        normalized = [f"--- a/{filename}\n", f"+++ b/{filename}\n", *lines]

    hunk_headers: list[str] = []
    hunk_started = False
    expected_old = expected_new = seen_old = seen_new = None

    def finish_hunk() -> None:
        if hunk_started and (seen_old != expected_old or seen_new != expected_new):
            raise ProtocolError("invalid_request", "patch hunk line counts are invalid")

    for line in normalized:
        match = hunk_pattern.match(line)
        if match:
            finish_hunk()
            hunk_started = True
            hunk_headers.append(line.rstrip("\r\n"))
            expected_old = int(match.group(2) or "1") if match.group(1) != "0" else 0
            expected_new = int(match.group(4) or "1") if match.group(3) != "0" else 0
            seen_old = seen_new = 0
            continue
        if hunk_started:
            if not line or line[0] not in " +-\\":
                raise ProtocolError("invalid_request", "patch contains trailing data")
            if line[0] in " -":
                seen_old += 1
            if line[0] in " +":
                seen_new += 1
    finish_hunk()
    if not hunk_headers:
        raise ProtocolError("invalid_request", "patch contains no @@ hunks")
    return "".join(normalized), hunk_headers


def _git_apply_patch(
    original: bytes, patch: str, filename: str, mode: int
) -> tuple[bytes, int, list[RejectedHunk]]:
    """Apply one file through git in a private staging directory."""
    import os
    import re
    import subprocess
    import tempfile

    normalized, hunk_headers = _single_file_patch(patch, filename)
    with tempfile.TemporaryDirectory(prefix="gateway-patch-") as root:
        staging = Path(root)
        staged_target = staging / filename
        staged_target.write_bytes(original)
        staged_target.chmod(mode & 0o7777)
        patch_path = staging / f".gateway-patch-input-{os.urandom(8).hex()}"
        patch_path.write_text(normalized, encoding="utf-8", newline="")
        try:
            completed = subprocess.run(
                [
                    "git",
                    "-C",
                    str(staging),
                    "apply",
                    "--reject",
                    "--unidiff-zero",
                    "--whitespace=nowarn",
                    str(patch_path),
                ],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ProtocolError("deadline", "git patch operation timed out") from exc
        if completed.returncode not in (0, 1):
            diagnostic = (completed.stderr or completed.stdout).strip()
            raise ProtocolError(
                "invalid_request",
                diagnostic or "git rejected the unified patch",
            )
        reject_path = staged_target.with_name(f"{filename}.rej")
        rejected_headers = []
        if reject_path.exists():
            rejected_text = reject_path.read_text(encoding="utf-8", errors="replace")
            rejected_headers = re.findall(
                r"^(@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@[^\r\n]*)",
                rejected_text,
                flags=re.MULTILINE,
            )
        rejected: list[RejectedHunk] = []
        used: set[int] = set()
        for header in rejected_headers:
            try:
                index = next(
                    index
                    for index, candidate in enumerate(hunk_headers)
                    if index not in used and candidate == header
                )
            except StopIteration:
                index = len(used)
            used.add(index)
            rejected.append(
                RejectedHunk(
                    index=index, reason="context does not match", header=header
                )
            )
        if not staged_target.exists():
            raise ProtocolError(
                "invalid_request", "git apply did not produce the target file"
            )
        return staged_target.read_bytes(), len(hunk_headers) - len(rejected), rejected


def _patch(runtime: Runtime, inp: PatchInput) -> PatchResult:
    runtime.principal.require(Capability.FILE_WRITE)
    target = _authorized(runtime, inp.target, existing=True)
    if not target.is_file():
        raise ProtocolError("invalid_request", "path is not a regular file")
    if target.is_symlink():
        raise ProtocolError("invalid_request", "patching symlinks is not supported")
    before = sha256_of(target)
    expected = inp.expected_sha256
    if inp.preconditions:
        extra = set(inp.preconditions) - {"expected_sha256"}
        if extra:
            raise ProtocolError(
                "invalid_request", "file preconditions are not recognized"
            )
        expected = expected or inp.preconditions.get("expected_sha256")
    if expected is not None and expected != before:
        raise ProtocolError(
            "precondition_failed",
            "file changed since it was read",
            details={"expected_sha256": expected, "current_sha256": before},
        )
    original = target.read_bytes()
    try:
        text = original.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProtocolError("invalid_request", "file is not UTF-8 text") from exc
    lines = _split_lines(text)
    rejected: list[RejectedHunk] = []
    if inp.edit.mode == "unified":
        encoded, applied, rejected = _git_apply_patch(
            original, inp.edit.patch, target.name, target.stat().st_mode
        )
        if rejected and not applied:
            raise ProtocolError(
                "conflict",
                "no hunk applied",
                details={"rejected_hunks": [hunk.model_dump() for hunk in rejected]},
            )
    else:
        edit = inp.edit
        if edit.end_line < edit.start_line - 1 or edit.start_line > len(lines) + 1:
            raise ProtocolError("invalid_request", "line range is outside the file")
        current = lines[edit.start_line - 1 : edit.end_line]
        if (
            edit.expected_text is not None
            and _split_lines(edit.expected_text) != current
        ):
            raise ProtocolError(
                "precondition_failed",
                "range text differs from expected_text",
                details={"current_text": "\n".join(current)[:4_000]},
            )
        updated = (
            lines[: edit.start_line - 1]
            + _split_lines(edit.replacement)
            + lines[edit.end_line :]
        )
        applied = 1
        trailing_newline = text.endswith("\n") or text == ""
        encoded = (
            "\n".join(updated) + ("\n" if trailing_newline and updated else "")
        ).encode()
    updated = _split_lines(encoded.decode("utf-8"))
    if not inp.dry_run:
        temporary = target.with_name(f".{target.name}.gateway-tmp")
        temporary.write_bytes(encoded)
        temporary.chmod(target.stat().st_mode & 0o7777)
        temporary.replace(target)
    import hashlib

    after = hashlib.sha256(encoded).hexdigest()
    return PatchResult(
        ref=encode_file_ref(str(target)),
        path=str(target),
        mode=inp.edit.mode,
        dry_run=inp.dry_run,
        applied_hunks=applied,
        rejected_hunks=rejected,
        before_sha256=before,
        after_sha256=after,
        bytes=len(encoded),
        lines_before=len(lines),
        lines_after=len(updated),
        affordances=["files.read", "files.patch", "files.stat"],
    )


# --------------------------------------------------------------------- change


class ReplaceOp(GatewayModel):
    operation: Literal["replace"] = "replace"
    content: str = Field(max_length=4_194_304)
    create: bool = Field(default=True, description="Create the file when absent.")


class AppendOp(GatewayModel):
    operation: Literal["append"] = "append"
    content: str = Field(max_length=4_194_304)


class CreateOp(GatewayModel):
    operation: Literal["create"] = "create"
    content: str = Field(default="", max_length=4_194_304)


class MkdirOp(GatewayModel):
    operation: Literal["mkdir"] = "mkdir"
    parents: bool = False


class CopyOp(GatewayModel):
    operation: Literal["copy"] = "copy"
    destination: FileLocator


class MoveOp(GatewayModel):
    operation: Literal["move"] = "move"
    destination: FileLocator


class RemoveOp(GatewayModel):
    operation: Literal["remove"] = "remove"


FileOp = ReplaceOp | AppendOp | CreateOp | MkdirOp | CopyOp | MoveOp | RemoveOp


class ChangeInput(MutationControls):
    target: FileLocator
    change: FileOp = Field(discriminator="operation")
    expected_sha256: str | None = Field(default=None, pattern="^[0-9a-f]{64}$")


class ChangeResult(GatewayModel):
    ref: str
    path: str
    operation: str
    destination_ref: str | None = None
    destination: str | None = None
    created: bool = False
    removed: bool = False
    bytes: int | None = None
    previous_sha256: str | None = None
    sha256: str | None = None
    affordances: list[str] = Field(default_factory=list)


def _change(runtime: Runtime, inp: ChangeInput) -> ChangeResult:
    runtime.principal.require(Capability.FILE_WRITE)
    path, ref = inp.target.resolve()
    expected = inp.expected_sha256
    if inp.preconditions:
        if set(inp.preconditions) - {"expected_sha256"}:
            raise ProtocolError(
                "invalid_request", "file preconditions are not recognized"
            )
        expected = expected or inp.preconditions.get("expected_sha256")
    op = inp.change
    destination: str | None = None
    destination_ref: str | None = None
    if isinstance(op, (CopyOp, MoveOp)):
        destination, destination_ref = op.destination.resolve()
    try:
        if isinstance(op, CreateOp):
            if Path(path).exists() or Path(path).is_symlink():
                raise ProtocolError("conflict", "path already exists")
            result = runtime.files.write("replace", path, content=op.content)
            result["created"] = True
        elif isinstance(op, ReplaceOp):
            if not op.create and not Path(path).exists():
                raise ProtocolError("not_found", "path does not exist")
            existed = Path(path).exists()
            result = runtime.files.write(
                "replace", path, content=op.content, expected_sha256=expected
            )
            result["created"] = not existed
        elif isinstance(op, MkdirOp):
            if op.parents:
                Path(path).mkdir(mode=0o700, parents=True, exist_ok=False)
                result = {"operation": "mkdir", "path": path, "created": True}
            else:
                result = runtime.files.write("mkdir", path)
        else:
            result = runtime.files.write(
                op.operation,
                path,
                content=getattr(op, "content", None),
                destination=destination,
                expected_sha256=expected,
            )
    except FileError as exc:
        message = str(exc)
        if "expected_sha256" in message:
            raise ProtocolError("precondition_failed", message) from exc
        if "already exists" in message:
            raise ProtocolError("conflict", message) from exc
        if "not exist" in message:
            raise ProtocolError("not_found", message) from exc
        if "unavailable" in message:
            raise ProtocolError("policy_denied", message) from exc
        raise ProtocolError("invalid_request", message) from exc
    except FileExistsError as exc:
        raise ProtocolError("conflict", "path already exists") from exc
    return ChangeResult(
        ref=ref,
        path=result.get("path", path),
        operation=op.operation,
        destination=result.get("destination"),
        destination_ref=destination_ref,
        created=bool(result.get("created", False)),
        removed=bool(result.get("removed", False)),
        bytes=result.get("bytes"),
        previous_sha256=result.get("previous_sha256")
        or (
            result.get("sha256") if isinstance(op, (CopyOp, MoveOp, RemoveOp)) else None
        ),
        sha256=result.get("sha256")
        if not isinstance(op, (CopyOp, MoveOp, RemoveOp))
        else None,
        affordances=["files.stat", "files.read", "files.list"],
    )


ACTIONS = ACTIONS + (
    Action(
        name="files.search",
        family=VerbFamily.QUERY,
        owner="files",
        summary="Find files by name, path, type, size, age or content under one or more roots.",
        Input=SearchInput,
        Output=SearchResult,
        handler=_search,
        principals=OBSERVER_OPERATOR,
        resource_kinds=("host_file",),
        affordances=("files.read", "files.stat", "files.list"),
        aliases=("find", "grep", "locate", "rg", "fd", "search files", "recent files"),
        documentation="Without content_regex the search is over paths (fd); with it, matching lines are returned (ripgrep --json). Results are bounded by limit and timeout.",
        examples=(
            Example(
                title="PNGs under /realm/tmp/work",
                input={"roots": [{"path": "/realm/tmp/work"}], "extensions": ["png"]},
            ),
            Example(
                title="Grep a string in a project",
                input={
                    "roots": [{"path": "/realm/project/sinnix"}],
                    "content_regex": "screenshot_probe",
                    "context_lines": 1,
                },
            ),
            Example(
                title="Files modified in the last two hours",
                input={
                    "roots": [{"path": "/realm/tmp"}],
                    "modified_within_seconds": 7200,
                },
            ),
        ),
    ),
    Action(
        name="files.patch",
        family=VerbFamily.CHANGE,
        owner="files",
        summary="Edit a text file with a unified diff or an exact line-range replacement.",
        Input=PatchInput,
        Output=PatchResult,
        handler=_patch,
        principals=OPERATOR_ONLY,
        resource_kinds=("host_file",),
        affordances=("files.read", "files.stat"),
        aliases=("edit", "apply diff", "modify text", "sed"),
        supports_precondition=True,
        documentation="Pass expected_sha256 from the prior read so a concurrent change is refused instead of overwritten. Unified hunks are applied individually; rejected hunks are reported.",
        examples=(
            Example(
                title="Replace lines 3-4",
                input={
                    "target": {"path": "/realm/tmp/work/notes.md"},
                    "edit": {
                        "mode": "range",
                        "start_line": 3,
                        "end_line": 4,
                        "replacement": "new line",
                    },
                    "idempotency_key": "patch-notes-1",
                },
            ),
            Example(
                title="Apply a unified diff",
                input={
                    "target": {"path": "/realm/tmp/work/notes.md"},
                    "edit": {
                        "mode": "unified",
                        "patch": "@@ -1,1 +1,1 @@\n-old\n+new\n",
                    },
                    "expected_sha256": "0" * 64,
                    "idempotency_key": "patch-notes-2",
                },
            ),
        ),
    ),
    Action(
        name="files.change",
        family=VerbFamily.CHANGE,
        owner="files",
        summary="Create, replace, append, mkdir, copy, move or remove one host path.",
        Input=ChangeInput,
        Output=ChangeResult,
        handler=_change,
        principals=OPERATOR_ONLY,
        resource_kinds=("host_file",),
        affordances=("files.stat", "files.read", "files.list"),
        aliases=("write", "save", "rename", "delete", "mkdir", "touch"),
        supports_precondition=True,
        documentation="Copy and move never overwrite an existing destination. Remove supports regular files only.",
        examples=(
            Example(
                title="Write a file",
                input={
                    "target": {"path": "/realm/tmp/work/hello.txt"},
                    "change": {"operation": "replace", "content": "hello\n"},
                    "idempotency_key": "write-hello-1",
                },
            ),
            Example(
                title="Move a file",
                input={
                    "target": {"path": "/realm/tmp/work/hello.txt"},
                    "change": {
                        "operation": "move",
                        "destination": {"path": "/realm/tmp/work/archive/hello.txt"},
                    },
                    "idempotency_key": "move-hello-1",
                },
            ),
        ),
    ),
)
