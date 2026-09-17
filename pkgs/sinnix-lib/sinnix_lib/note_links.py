"""Bounded, read-only planning for retained Markdown note references.

A plan is evidence, not a writer: callers preserve source versions, revalidate
all inputs, and choose which edits to publish. No directory outside explicit
roots is searched. Reference roots supply historical targets but never edits.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote

SCHEMA = "sinnix-note-links-v1"


def _token(st: os.stat_result) -> tuple[int, ...]:
    return st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns


def read_note(path: Path, max_bytes: int) -> tuple[str, dict]:
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_size > max_bytes:
        raise ValueError("not a bounded regular Markdown file")
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as handle:
        if _token(os.fstat(handle.fileno())) != _token(before):
            raise ValueError("note changed before read")
        raw = handle.read(max_bytes + 1)
        after = os.fstat(handle.fileno())
    if len(raw) > max_bytes or _token(after) != _token(before) or _token(path.lstat()) != _token(before):
        raise ValueError("note changed during read")
    return raw.decode("utf-8"), {
        "path": str(path), "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw), "device": before.st_dev, "inode": before.st_ino,
        "mtime_ns": before.st_mtime_ns, "mode": stat.S_IMODE(before.st_mode),
    }


def _scalar(value: str) -> str:
    """The deliberately narrow frontmatter string subset used for identities.

    This is not a YAML interpreter. Complex YAML must not acquire guessed ids.
    """
    value = value.strip()
    if value.startswith('"'):
        result = json.loads(value)
    elif value.startswith("'") and value.endswith("'"):
        result = value[1:-1].replace("''", "'")
    elif value and not value.startswith(("&", "*", "!", "|", ">")) and not any(c in value for c in "[]{}#\t"):
        result = value
    else:
        raise ValueError("unsupported identity scalar")
    if not isinstance(result, str) or not result or any(ord(c) < 32 for c in result):
        raise ValueError("invalid identity string")
    return result


def note_metadata(text: str) -> tuple[list[str], list[str], int]:
    if not re.match(r"\A---[ \t]*\r?\n", text):
        return [], [], 0
    match = re.match(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|$)", text, re.S)
    if not match:
        raise ValueError("unterminated frontmatter")
    header = match.group(1)
    ids = re.findall(r"^id:[ \t]*(.+?)\s*$", header, re.M)
    if len(ids) > 1:
        raise ValueError("duplicate id field")
    ids = [_scalar(x) for x in ids]
    aliases: list[str] = []
    block = False
    seen = False
    for line in header.splitlines():
        if line.startswith("aliases:"):
            if seen:
                raise ValueError("duplicate aliases field")
            seen = True
            remainder = line[len("aliases:"):].strip()
            if remainder and remainder != "[]":
                # JSON-style flow lists are unambiguous, ordinary YAML flows
                # are not interpreted by this small identity reader.
                if not remainder.startswith("[") or not remainder.endswith("]"):
                    raise ValueError("unsupported aliases list")
                inner = remainder[1:-1].strip()
                values = []
                # Plain/quoted YAML flow-list strings only; no nested values,
                # tags or alias evaluation. Quoted commas remain inside items.
                pos = 0
                token = re.compile(r"\s*(\"(?:[^\"\\]|\\.)*\"|'(?:[^']|'')*'|[^,\[\]{}]+?)\s*(,|$)")
                while pos < len(inner):
                    match = token.match(inner, pos)
                    if not match:
                        raise ValueError("unsupported aliases list")
                    values.append(_scalar(match[1]))
                    pos = match.end()
                if inner.endswith(","):
                    raise ValueError("trailing alias delimiter")
                aliases.extend(values)
            block = not remainder
        elif block:
            item = re.match(r"^[ \t]+-[ \t]+(.+?)\s*$", line)
            if item:
                aliases.append(_scalar(item.group(1)))
            elif line.strip() and not line.lstrip().startswith("#"):
                block = False
    return ids, aliases, match.end()


def prose_mask(text: str, header_end: int = 0) -> str:
    """Same-length text with frontmatter, comments and code blanked out."""
    chars = list(text)
    def blank(start: int, end: int) -> None:
        chars[start:end] = ["\n" if c == "\n" else " " for c in text[start:end]]
    blank(0, header_end)
    for match in re.finditer(r"<!--[\s\S]*?(?:-->|\Z)", text):
        blank(*match.span())
    offset = 0
    fence: tuple[str, int] | None = None
    for line in text.splitlines(keepends=True):
        end = offset + len(line)
        if offset < header_end:
            offset = end
            continue
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line.rstrip("\r\n"))
        if fence:
            blank(offset, end)
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= fence[1] and not marker[2].strip():
                fence = None
        elif marker:
            fence = marker[1][0], len(marker[1])
            blank(offset, end)
        elif line.startswith(("    ", "\t")):
            blank(offset, end)
        offset = end
    masked = "".join(chars)
    for match in re.finditer(r"(`+)([\s\S]*?)\1(?!`)", masked):
        blank(*match.span())
    return "".join(chars)


def _label(value: str) -> str:
    return re.sub(r"([\\`*_{}\[\]<>])", r"\\\1", value)


def scan_notes(roots: list[Path], reference_roots: list[Path] | None = None, *,
               exclude: set[str] | None = None, max_files: int = 2000,
               max_bytes: int = 32 << 20, max_file_bytes: int = 2 << 20,
               max_depth: int = 12) -> dict:
    """Resolve bare [[id]], [[alias]] and [[filename]] references conservatively.

    No basename fallback for path-qualified targets; no guessing of anchors,
    alias-pipe dialect, embeds, or missing targets. Ambiguous candidates remain
    unresolved. Any unplanned coverage error disables all proposed edits.
    """
    if not roots or not 1 <= max_files <= 10000 or not 1 <= max_depth <= 32:
        raise ValueError("explicit roots and bounded file/depth limits required")
    if not 1 <= max_file_bytes <= 16 << 20 or not 1 <= max_bytes <= 256 << 20:
        raise ValueError("invalid read budget")
    reference_roots = reference_roots or []
    excluded = set(exclude or ())
    excluded.update({".git", ".venv", "node_modules", "__pycache__"})
    documents: dict[str, dict] = {}
    errors, boundaries = [], []
    read_bytes = 0
    examined = directories = 0
    for primary, selected in ((True, roots), (False, reference_roots)):
        for supplied in selected:
            root = Path(os.path.abspath(supplied))
            if root.is_symlink() or not root.is_dir():
                errors.append({"path": str(root), "error": "missing/non-directory/symlink root"})
                continue
            def unreadable(exc: OSError) -> None:
                errors.append({"path": str(exc.filename), "error": type(exc).__name__})
            for parent, dirs, files in os.walk(root, followlinks=False, onerror=unreadable):
                directories += 1
                if directories > max_files * 4:
                    raise ValueError("directory-count budget exceeded")
                here = Path(parent)
                if ".git" in dirs or ".git" in files:
                    boundaries.append({"path": parent, "reason": "native Git workspace not inspected"})
                    dirs[:] = []
                    continue
                depth = len(here.relative_to(root).parts)
                children = []
                for name in sorted(dirs):
                    path = here / name
                    if name in excluded or name.startswith(".") or path.is_symlink():
                        boundaries.append({"path": str(path), "reason": "declared exclusion or alias"})
                    elif depth >= max_depth:
                        errors.append({"path": str(path), "error": "depth budget exceeded"})
                    else:
                        children.append(name)
                dirs[:] = children
                for name in sorted(files):
                    if not name.endswith(".md") or name.startswith(".") or name in excluded:
                        continue
                    path = here / name
                    key = str(path)
                    if key in documents:
                        continue
                    if path.is_symlink():
                        boundaries.append({"path": key, "reason": "note alias not followed"})
                        continue
                    examined += 1
                    if examined > max_files:
                        raise ValueError("candidate-file budget exceeded")
                    try:
                        if len(documents) >= max_files:
                            raise ValueError("file-count budget exceeded")
                        if path.lstat().st_size + read_bytes > max_bytes:
                            raise ValueError("total-byte budget exceeded")
                        text, facts = read_note(path, max_file_bytes)
                        read_bytes += facts["bytes"]
                        ids, aliases, end = note_metadata(text)
                        documents[key] = {**facts, "primary": primary, "ids": ids,
                                          "aliases": aliases, "text": text, "header_end": end}
                    except (OSError, ValueError) as exc:
                        errors.append({"path": key, "error": str(exc)})
    indexes = {(tier, kind): defaultdict(set) for tier in (True, False) for kind in ("id", "alias", "name")}
    for key, doc in documents.items():
        for kind, values in (("id", doc["ids"]), ("alias", doc["aliases"]),
                             ("name", [Path(key).stem, Path(key).name])):
            for value in values:
                indexes[(doc["primary"], kind)][value].add(key)
    def resolve(source: str, target: str) -> tuple[str, list[str]]:
        if not target or any(c in target for c in "|#[]\n\r"):
            return "unsupported-syntax", []
        if "/" in target:
            candidate = os.path.abspath(os.path.join(os.path.dirname(source), target))
            candidates = [p for p in (candidate, candidate + ".md") if p in documents]
            return ("path" if len(candidates) == 1 else "ambiguous" if candidates else "unresolved"), candidates
        for tier in (True, False):
            for kind in ("id", "alias", "name"):
                matches = sorted(indexes[(tier, kind)].get(target, ()))
                if matches:
                    return (kind if len(matches) == 1 else "ambiguous"), matches
        return "unresolved", []
    observations, changes = [], []
    for key, doc in sorted(documents.items()):
        if not doc["primary"]:
            continue
        edits = []
        masked = prose_mask(doc["text"], doc["header_end"])
        for match in re.finditer(r"(?<!!)\[\[([^\]\n]+)\]\]", masked):
            backslashes = len(masked[:match.start()]) - len(masked[:match.start()].rstrip("\\"))
            if backslashes % 2:
                continue
            target = match[1].strip()
            status, candidates = resolve(key, target)
            info = {"source": key, "line": doc["text"].count("\n", 0, match.start()) + 1,
                    "token": doc["text"][match.start():match.end()], "status": status,
                    "target": target, "candidates": candidates}
            if len(candidates) == 1 and status != "ambiguous":
                destination = candidates[0]
                if destination == key:
                    info["status"] = "self-reference"
                else:
                    href = quote(os.path.relpath(destination, Path(key).parent), safe="/")
                    replacement = "[" + _label(target) + "](" + href + ")"
                    edits.append({"start": match.start(), "end": match.end(), "before": info["token"],
                                  "after": replacement, "destination": destination,
                                  "target_sha256": documents[destination]["sha256"]})
            observations.append(info)
        if edits:
            changes.append({"path": key, "before_sha256": doc["sha256"], "edits": edits})
    return {"schema": SCHEMA,
            "scope": {"roots": [str(Path(os.path.abspath(r))) for r in roots],
                      "reference_roots": [str(Path(os.path.abspath(r))) for r in reference_roots],
                      "exclude_components": sorted(excluded), "max_files": max_files,
                      "max_bytes": max_bytes, "max_file_bytes": max_file_bytes, "max_depth": max_depth},
            "complete": not errors, "errors": errors, "boundaries": boundaries,
            "documents": [{k: v for k, v in d.items() if k not in ("text", "header_end")} for d in documents.values()],
            "counts": {"documents": len(documents), "bytes_read": read_bytes,
                       "references": len(observations), "statuses": dict(Counter(x["status"] for x in observations)),
                       "editable_documents": 0 if errors else len(changes),
                       "proposed_edits": 0 if errors else sum(len(c["edits"]) for c in changes)},
            "references": observations, "changes": [] if errors else changes,
            "limitations": "Read-only plan. No payload writes, inferred alias-pipe dialect, anchor repair, archive extraction, native workspace traversal, or global uniqueness claim outside the declared roots. Revalidate every input and preserve originals before applying selected edits."}


def rewrite(text: str, edits: list[dict]) -> str:
    """Pure edit application; no filesystem writes or revalidation shortcuts."""
    last = len(text)
    for edit in sorted(edits, key=lambda e: e["start"], reverse=True):
        start, end = edit["start"], edit["end"]
        if not 0 <= start <= end <= last or text[start:end] != edit["before"]:
            raise ValueError("overlapping or stale note-link edit")
        text = text[:start] + edit["after"] + text[end:]
        last = start
    return text


def command(args) -> int:
    plan = scan_notes(args.root, args.reference_root, exclude=set(args.exclude_component),
                      max_files=args.max_files, max_bytes=args.max_bytes,
                      max_file_bytes=args.max_file_bytes, max_depth=args.max_depth)
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 2 if not plan["complete"] else 1 if plan["references"] else 0
