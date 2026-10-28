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
MAX_OWNERSHIP_RUNTIMES = 32


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


def _ownership(payload: object, pid: int, earliest_ms: int, latest_ms: int) -> dict:
    """Optional worker snapshots cannot invalidate sound allocator counters."""
    unavailable = {
        "schema_version": 1,
        "status": "unavailable",
        "collector_reason": "invalid_payload",
    }
    if payload is None:
        return {**unavailable, "collector_reason": "not_provided"}
    if not isinstance(payload, dict):
        return unavailable
    if type(payload.get("schema_version")) is not int or payload["schema_version"] != 1:
        return {**unavailable, "collector_reason": "unsupported_schema"}

    def unsigned(value: object) -> bool:
        return type(value) is int and 0 <= value < 2**64

    required = (
        "schema_version",
        "provider",
        "status",
        "pid",
        "observed_at_unix_ms",
        "units",
        "runtime_count",
        "reported_runtime_count",
        "truncated_count",
        "runtimes",
    )
    if any(key not in payload for key in required):
        return unavailable
    observed = payload["observed_at_unix_ms"]
    if (
        payload["provider"] != "luau"
        or payload["units"] != "bytes"
        or payload["status"] not in ("available", "partial", "unavailable")
        or type(payload["pid"]) is not int
        or payload["pid"] != pid
        or type(observed) is not int
        or not earliest_ms - 1000 <= observed <= latest_ms + 1000
    ):
        return unavailable
    total, reported, truncated = (
        payload[key]
        for key in ("runtime_count", "reported_runtime_count", "truncated_count")
    )
    runtimes = payload["runtimes"]
    if (
        not all(unsigned(value) for value in (total, reported, truncated))
        or not isinstance(runtimes, list)
        or reported != len(runtimes)
        or reported > MAX_OWNERSHIP_RUNTIMES
        or total != reported + truncated
    ):
        return unavailable
    runtime_keys = (
        "state_token",
        "runtime_id",
        "host_generation",
        "status",
        "bytes",
        "sampled_at_unix_ms",
        "age_ms",
        "reason",
    )
    snapshots = []
    last_token = -1
    for runtime in runtimes:
        if not isinstance(runtime, dict) or any(
            key not in runtime for key in runtime_keys
        ):
            return unavailable
        token, identifier, generation = (
            runtime[key] for key in ("state_token", "runtime_id", "host_generation")
        )
        status, value, sampled, age, reason = (
            runtime[key]
            for key in ("status", "bytes", "sampled_at_unix_ms", "age_ms", "reason")
        )
        if (
            not unsigned(token)
            or token <= last_token
            or (
                identifier is not None
                and (
                    not isinstance(identifier, str)
                    or not re.fullmatch(r"[A-Za-z0-9_./:-]{1,128}", identifier)
                )
            )
            or (generation is not None and not unsigned(generation))
        ):
            return unavailable
        if status in ("available", "stale"):
            if (
                identifier is None
                or generation is None
                or not all(unsigned(item) for item in (value, sampled, age))
                or (status == "available" and reason is not None)
                or (status == "stale" and reason != "worker_in_flight")
            ):
                return unavailable
        elif status == "unavailable":
            if (
                any(item is not None for item in (value, sampled, age))
                or reason
                not in (
                    "not_observed",
                    "host_absent",
                    "worker_in_flight",
                    "runtime_id_too_long",
                    "runtime_id_invalid",
                )
                or (
                    identifier is None
                    and reason not in ("runtime_id_too_long", "runtime_id_invalid")
                )
            ):
                return unavailable
        else:
            return unavailable
        snapshots.append({key: runtime[key] for key in runtime_keys})
        last_token = token
    expected_status = (
        "partial"
        if truncated
        else "available"
        if all(item["status"] == "available" for item in snapshots)
        else "partial"
        if any(item["bytes"] is not None for item in snapshots)
        else "unavailable"
    )
    if payload["status"] != expected_status:
        return unavailable
    # Worker snapshots can be old even when the report is fresh. Retain their
    # status, sample time and age; never infer freshness or sum a current total.
    return {
        **{key: payload[key] for key in required if key != "runtimes"},
        "runtimes": snapshots,
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
            allocator["ownership"] = _ownership(
                envelope.get("ownership"), pid, earliest, latest
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
