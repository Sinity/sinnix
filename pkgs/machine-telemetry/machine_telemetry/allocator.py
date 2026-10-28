"""Optional, bounded allocator observations for an already sampled shell process."""

from __future__ import annotations

import json
import os
import pwd
import re
import time
from pathlib import Path

from sinnix_lib.process import run_bounded
from sinnix_lib.procfs import parse_stat_start_time

TIMEOUT_SECONDS = 1.0
OUTPUT_LIMIT = 16 * 1024
COUNTERS = (
    "allocated_bytes",
    "active_bytes",
    "resident_bytes",
    "mapped_bytes",
    "retained_bytes",
    "metadata_bytes",
)
PROFILE_ROOT = Path("/etc/profiles/per-user")


def _context(pid: int) -> dict[str, object]:
    proc = Path("/proc") / str(pid)
    # Read only these routing values; never persist the process environment.
    environment = {}
    for entry in (proc / "environ").read_bytes().split(b"\0"):
        name, _, value = entry.partition(b"=")
        if name in (b"XDG_RUNTIME_DIR", b"WAYLAND_DISPLAY"):
            environment[name.decode()] = value.decode("utf-8")
    return {
        "uid": proc.stat().st_uid,
        "start_ticks": parse_stat_start_time((proc / "stat").read_text()),
        **environment,
    }


def _validate(payload: object, pid: int, earliest_ms: int, latest_ms: int) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("missing allocator object")
    required = (
        "schema_version",
        "backend",
        "units",
        "status",
        "observed_at_unix_ms",
        "pid",
        *COUNTERS,
        "errors",
    )
    if any(key not in payload for key in required):
        raise ValueError("incomplete allocator object")
    if payload.get("schema_version") != 1 or isinstance(
        payload.get("schema_version"), bool
    ):
        raise ValueError("unsupported allocator schema")
    if payload.get("units") != "bytes" or payload.get("backend") not in (
        "jemalloc",
        "unavailable",
    ):
        raise ValueError("unsupported allocator units/backend")
    if type(payload.get("pid")) is not int or payload["pid"] != pid:
        raise ValueError("allocator process identity mismatch")
    observed = payload.get("observed_at_unix_ms")
    if (
        type(observed) is not int
        or not earliest_ms - 1000 <= observed <= latest_ms + 1000
    ):
        raise ValueError("allocator timestamp outside probe window")
    status = payload.get("status")
    values = [payload.get(name) for name in COUNTERS]
    errors = payload.get("errors")
    if not isinstance(errors, list) or len(errors) > 8:
        raise ValueError("invalid allocator errors")
    if any(
        not isinstance(e, dict)
        or not isinstance(e.get("field"), str)
        or type(e.get("code")) is not int
        or not isinstance(e.get("message"), str)
        or len(e["field"]) > 64
        or len(e["message"]) > 512
        for e in errors
    ):
        raise ValueError("invalid allocator error record")
    if status == "available":
        if (
            payload["backend"] != "jemalloc"
            or errors
            or any(type(v) is not int or not 0 <= v < 2**64 for v in values)
        ):
            raise ValueError("invalid available allocator counters")
    elif status == "unavailable":
        if not errors or any(v is not None for v in values):
            raise ValueError("unavailable allocator counters must be null")
    else:
        raise ValueError("invalid allocator status")
    # Keep only the versioned allocator contract, not unrelated UI status.
    return {
        key: payload[key]
        for key in (
            "schema_version",
            "backend",
            "units",
            "status",
            "observed_at_unix_ms",
            "pid",
            *COUNTERS,
            "errors",
        )
    }


def observe(row: dict[str, object], user_name: str) -> str:
    started = time.monotonic()
    result: dict[str, object] = {
        "schema_version": 1,
        "status": "unavailable",
        "reason": None,
        "allocator": None,
    }
    try:
        user = pwd.getpwnam(user_name)
        pid = int(row["pid"])
        expected_start = row["process_start_time_ticks"]
        before = _context(pid)
        runtime = f"/run/user/{user.pw_uid}"
        display = before.get("WAYLAND_DISPLAY")
        if (
            type(expected_start) is not int
            or before["uid"] != user.pw_uid
            or before["start_ticks"] != expected_start
        ):
            raise ValueError("identity")
        if (
            before.get("XDG_RUNTIME_DIR") != runtime
            or not isinstance(display, str)
            or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", display)
        ):
            raise ValueError("runtime")
        binary = PROFILE_ROOT / user.pw_name / "bin/noctalia"
        if not binary.is_file():
            raise ValueError("binary_missing")
        environment = {
            "HOME": user.pw_dir,
            "USER": user.pw_name,
            "LOGNAME": user.pw_name,
            "XDG_RUNTIME_DIR": runtime,
            "WAYLAND_DISPLAY": display,
            "PATH": os.environ.get("PATH", ""),
            "LANG": "C.UTF-8",
        }
        command = [str(binary), "msg", "status"]
        if os.geteuid() == 0:
            # The collector has a GPU thread: an external identity bridge avoids
            # unsafe Python preexec_fn work after fork in a threaded process.
            command = [
                "setpriv",
                f"--reuid={user.pw_uid}",
                f"--regid={user.pw_gid}",
                "--init-groups",
                *command,
            ]
        elif os.geteuid() != user.pw_uid:
            raise ValueError("identity")
        earliest = time.time_ns() // 1_000_000
        response = run_bounded(
            command,
            timeout=TIMEOUT_SECONDS,
            env=environment,
            stdout_limit=OUTPUT_LIMIT,
            stderr_limit=2048,
        )
        latest = time.time_ns() // 1_000_000
        after = _context(pid)
        if after != before:
            raise ValueError("identity_changed")
        if response.timed_out:
            result["reason"] = "timeout"
        elif response.limited or response.output_incomplete:
            result["reason"] = "output_limit"
        elif not response.ok:
            result["reason"] = "command_failed"
        else:
            envelope = json.loads(response.stdout)
            allocator = _validate(
                envelope.get("allocator") if isinstance(envelope, dict) else None,
                pid,
                earliest,
                latest,
            )
            result.update(
                status=allocator["status"],
                allocator=allocator,
                reason=None
                if allocator["status"] == "available"
                else "provider_unavailable",
            )
    except (KeyError, OSError, UnicodeError):
        result["reason"] = "identity_unavailable"
    except ValueError as error:
        result["reason"] = (
            str(error)
            if str(error)
            in {"identity", "identity_changed", "runtime", "binary_missing"}
            else "invalid_payload"
        )
    result["probe_duration_ms"] = round((time.monotonic() - started) * 1000, 3)
    return json.dumps(result, sort_keys=True, separators=(",", ":"))


def attach(rows: list[dict[str, object]], user_name: str) -> None:
    """At most one probe in the existing top-PSS process sample, never a timer."""
    sampled = False
    for row in rows:
        row["allocator_json"] = None
        if (
            not sampled
            and row.get("unit") == "noctalia.service"
            and row.get("scope") == "user"
            and Path(str(row.get("exe") or "")).name
            in {"noctalia", ".noctalia-wrapped"}
        ):
            row["allocator_json"] = observe(row, user_name)
            sampled = True
