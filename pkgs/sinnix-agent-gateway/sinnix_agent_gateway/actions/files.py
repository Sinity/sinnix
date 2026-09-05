"""Host filesystem actions: paths in, canonical refs and typed content out."""

from __future__ import annotations

import os
import stat as stat_module
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import Field

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
    inode: int
    device: int
    affordances: list[str] = Field(default_factory=list)


class StatInput(RequestControls):
    target: FileLocator
    follow_symlinks: bool = True
    with_sha256: bool = Field(
        default=True, description="Hash regular files; skipped above 256 MiB."
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
    if inp.with_sha256 and kind == "file" and details.st_size <= 256 * 1024 * 1024:
        digest = sha256_of(target)
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
        inode=details.st_ino,
        device=details.st_dev,
        affordances=affordances,
    )


class ListInput(RequestControls):
    target: FileLocator
    limit: int = Field(default=200, ge=1, le=5_000)
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


def _entry(child: Path) -> FileEntry | None:
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
    entries = [entry for entry in map(_entry, children) if entry is not None]
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
    max_bytes: int = Field(default=64_000, ge=1, le=4_194_304)
    line_start: int | None = Field(
        default=None, ge=1, description="First line (1-based) for text reads."
    )
    line_count: int | None = Field(default=None, ge=1, le=10_000)
    representation: Literal["auto", "text", "binary"] = Field(
        default="auto",
        description="auto returns text inline for text types and a typed content block for binary types.",
    )


class FileContent(GatewayModel):
    ref: str
    path: str
    media_type: str
    bytes: int = Field(description="Total size of the file.")
    sha256: str
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
        description="Set for binary files; the bytes travel in a content block.",
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
    digest = sha256_of(target)
    textual = inp.representation == "text" or (
        inp.representation == "auto" and is_text(media)
    )
    max_bytes = min(inp.max_bytes, runtime.config.max_result_bytes)
    base = {
        "ref": ref,
        "path": str(target),
        "media_type": media,
        "bytes": size,
        "sha256": digest,
        "affordances": ["files.change", "files.patch", "files.stat"],
    }
    if textual:
        if inp.line_start is not None:
            with target.open("rb") as handle:
                lines = handle.read().split(b"\n")
            total = len(lines) if lines[-1] else len(lines) - 1
            start = inp.line_start
            count = inp.line_count or 200
            selected = lines[start - 1 : start - 1 + count]
            data = b"\n".join(selected)
            truncated = len(data) > max_bytes
            data = data[:max_bytes]
            return ActionResult(
                FileContent(
                    **base,
                    text=data.decode("utf-8", errors="replace"),
                    returned_bytes=len(data),
                    truncated=truncated or start - 1 + count < total,
                    line_start=start,
                    line_end=min(start - 1 + len(selected), total),
                    total_lines=total,
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
        target, ref=ref, media_type=media, max_inline_bytes=max_bytes
    )
    return ActionResult(
        FileContent(**base, artifact=artifact, returned_bytes=min(size, max_bytes)),
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
        summary="Read a file: text inline, images as an image block, other binary as a resource block.",
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
    limit: int = Field(default=100, ge=1, le=2_000)
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


_OUTPUT_CAP = 8 * 1024 * 1024


def _run(argv: list[str], timeout: int) -> tuple[bytes, bool, int]:
    import subprocess

    try:
        completed = subprocess.run(
            argv, capture_output=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired as exc:
        return (exc.stdout or b"")[:_OUTPUT_CAP], True, -1
    except FileNotFoundError as exc:
        raise ProtocolError("unavailable", f"{argv[0]} is not installed") from exc
    return completed.stdout[:_OUTPUT_CAP], False, completed.returncode


def _search(runtime: Runtime, inp: SearchInput) -> SearchResult:
    runtime.principal.require(Capability.FILE_READ)
    roots = [_authorized(runtime, root, existing=True) for root in inp.roots]
    root_refs = [encode_file_ref(str(root)) for root in roots]
    warnings: list[str] = []
    if inp.content_regex is not None:
        argv = ["rg", "--json", "--no-messages", f"--max-count={inp.limit}"]
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
        output, timed_out, _ = _run(argv, inp.timeout_seconds)
        import json as json_module

        by_path: dict[str, FileMatch] = {}
        for raw in output.split(b"\n"):
            if not raw:
                continue
            try:
                event = json_module.loads(raw)
            except ValueError:
                continue
            kind = event.get("type")
            data = event.get("data", {})
            path_text = data.get("path", {}).get("text")
            if not path_text or kind not in {"match", "context"}:
                continue
            entry = by_path.get(path_text)
            if entry is None:
                if len(by_path) >= inp.limit:
                    continue
                base = _entry(Path(path_text))
                if base is None:
                    continue
                entry = FileMatch(**base.model_dump(), match_count=0)
                by_path[path_text] = entry
            line = data.get("lines", {}).get("text", "")
            entry.lines.append(
                MatchLine(
                    line_number=int(data.get("line_number") or 0),
                    text=line.rstrip("\n")[:2_000],
                    is_match=kind == "match",
                )
            )
            if kind == "match":
                entry.match_count = (entry.match_count or 0) + 1
        matches = list(by_path.values())
        if inp.path_regex:
            import re

            pattern = re.compile(inp.path_regex)
            matches = [match for match in matches if pattern.search(match.path)]
        return SearchResult(
            roots=root_refs,
            matches=matches[: inp.limit],
            returned=min(len(matches), inp.limit),
            truncated=len(matches) > inp.limit or len(output) >= _OUTPUT_CAP,
            engine="rg",
            timed_out=timed_out,
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
    output, timed_out, _ = _run(argv, inp.timeout_seconds)
    paths = [
        piece.decode("utf-8", "surrogateescape")
        for piece in output.split(b"\0")
        if piece
    ]
    entries = [
        entry for entry in (_entry(Path(path)) for path in paths[: inp.limit]) if entry
    ]
    return SearchResult(
        roots=root_refs,
        matches=[FileMatch(**entry.model_dump()) for entry in entries],
        returned=len(entries),
        truncated=len(paths) > inp.limit,
        engine="fd",
        timed_out=timed_out,
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


def _parse_hunks(patch: str) -> list[tuple[str, int, int, list[str]]]:
    import re

    header = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
    hunks: list[tuple[str, int, int, list[str]]] = []
    current: list[str] | None = None
    for line in patch.split("\n"):
        match = header.match(line)
        if match:
            current = []
            hunks.append((line, int(match.group(1)), int(match.group(3)), current))
            continue
        if current is None:
            continue
        if line == "" or line.startswith(("---", "+++")) and not hunks[-1][3]:
            continue
        if line[0] in " +-\\":
            current.append(line)
    if not hunks:
        raise ProtocolError("invalid_request", "patch contains no @@ hunks")
    return hunks


def _apply_unified(
    lines: list[str], patch: str
) -> tuple[list[str], int, list[RejectedHunk]]:
    result = list(lines)
    offset = 0
    applied = 0
    rejected: list[RejectedHunk] = []
    for index, (header, old_start, _new_start, body) in enumerate(_parse_hunks(patch)):
        old = [line[1:] for line in body if line[0] in " -"]
        new = [line[1:] for line in body if line[0] in " +"]
        position = old_start - 1 + offset
        if old_start == 0:
            position = 0
        window = result[position : position + len(old)]
        if window != old:
            found = None
            for delta in range(1, 200):
                for candidate in (position - delta, position + delta):
                    if (
                        0 <= candidate <= len(result) - len(old)
                        and result[candidate : candidate + len(old)] == old
                    ):
                        found = candidate
                        break
                if found is not None:
                    break
            if found is None:
                rejected.append(
                    RejectedHunk(
                        index=index, reason="context does not match", header=header
                    )
                )
                continue
            position = found
        result[position : position + len(old)] = new
        offset += len(new) - len(old)
        applied += 1
    return result, applied, rejected


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
    trailing_newline = text.endswith("\n") or text == ""
    lines = _split_lines(text)
    rejected: list[RejectedHunk] = []
    if inp.edit.mode == "unified":
        updated, applied, rejected = _apply_unified(lines, inp.edit.patch)
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
    new_text = "\n".join(updated) + ("\n" if trailing_newline and updated else "")
    encoded = new_text.encode()
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
