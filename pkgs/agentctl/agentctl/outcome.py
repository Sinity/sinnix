"""Compact views of complete immutable outcomes, including historical inventories."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any

from ijson.backends import python as streaming_json
from ijson.common import JSONError, ObjectBuilder

_INVENTORIES = {
    f"execution_receipt.{endpoint}.content_manifest.{field}": (endpoint, field)
    for endpoint in ("start", "end")
    for field in ("files", "omissions")
}


class _DigestReader:
    def __init__(self, handle):
        self.handle = handle
        self.digest = hashlib.sha256()
        self.bytes = 0

    def read(self, size):
        data = self.handle.read(size)
        self.digest.update(data)
        self.bytes += len(data)
        return data


def _token(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _project(handle, path: Path, limit: int) -> dict[str, Any] | None:
    reader = _DigestReader(handle)
    builder = ObjectBuilder()
    skipped = []
    depth = 0
    retained = 0
    keys = []
    selected = ("", "")
    container = ""
    count = 0
    for prefix, event, value in streaming_json.parse(reader, use_float=True):
        if depth:
            if depth == 1 and (
                event == "map_key"
                or (container == "array" and event not in ("end_array", "end_map"))
            ):
                count += 1
            if event in ("start_map", "start_array"):
                depth += 1
            elif event in ("end_map", "end_array"):
                depth -= 1
            if not depth:
                skipped.append((selected, count, container))
            continue
        if prefix in _INVENTORIES and event in ("start_map", "start_array"):
            selected = _INVENTORIES[prefix]
            container = "map" if event == "start_map" else "array"
            depth, count = 1, 0
            builder.event("null", None)
            continue
        if event == "map_key":
            if value in keys[-1]:
                return None
            keys[-1].add(value)
        elif event in ("start_map", "start_array"):
            keys.append(set() if event == "start_map" else None)
        elif event in ("end_map", "end_array"):
            keys.pop()
        retained += len(json.dumps(value, ensure_ascii=True)) + 2
        if retained > limit:
            return None
        builder.event(event, value)
    result = builder.value
    if not isinstance(result, dict):
        return None
    reference = {
        "path": str(path.absolute()),
        "sha256": reader.digest.hexdigest(),
        "bytes": reader.bytes,
    }
    for (endpoint, field), count, container in skipped:
        manifest = result["execution_receipt"][endpoint]["content_manifest"]
        if manifest[field] is not None or field + "_ref" in manifest:
            return None
        del manifest[field]
        manifest[field + "_ref"] = {
            **reference,
            "json_pointer": f"/execution_receipt/{endpoint}/content_manifest/{field}",
            "entries": count,
            "container": container,
        }
    result["outcome_ref"] = reference
    result["view"] = {"kind": "manifest-references", "complete_source_retained": True}
    return result if len(json.dumps(result).encode()) <= limit else None


def read_outcome(path: Path | None, limit: int) -> dict[str, Any] | None:
    """Read bounded metadata; oversized inventories stay in the source artifact.

    The Python streaming backend preserves JSON surrogate escapes used for
    filesystem filenames. Parse and hash the entire source before returning;
    malformed, changing and nonregular files never produce a partial verdict.
    Memory scales with transport metadata and individual parser tokens, not
    the number of manifest entries. The full source is never rewritten.
    """
    if path is None:
        return None
    descriptor = None
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            return None
        handle = os.fdopen(descriptor, "rb")
        descriptor = None
        with handle:
            if before.st_size <= limit:
                result = json.loads(handle.read(limit + 1))
            else:
                result = _project(handle, path, limit)
            if _token(os.fstat(handle.fileno())) != _token(before) or _token(
                path.lstat()
            ) != _token(before):
                return None
            return result if isinstance(result, dict) else None
    except (
        OSError,
        ValueError,
        UnicodeError,
        JSONError,
        RecursionError,
        KeyError,
        TypeError,
    ):
        return None
    finally:
        if descriptor is not None:
            os.close(descriptor)
