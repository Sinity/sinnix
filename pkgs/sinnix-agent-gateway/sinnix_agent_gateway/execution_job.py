from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

JOB_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def proc_start(pid: int) -> str:
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
    except OSError:
        return ""
    fields = stat.rsplit(") ", 1)[-1].split()
    return fields[19] if len(fields) >= 20 else ""


def current_cgroup() -> str:
    try:
        for line in Path("/proc/self/cgroup").read_text().splitlines():
            hierarchy, _, cgroup = line.partition("::")
            if hierarchy == "0":
                return cgroup
    except OSError:
        pass
    return ""


class ExecutionJob:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.root = Path(args.state_dir)
        self.manifest = self.root / f"{args.job_id}.json"
        self.events = self.root / f"{args.job_id}.events.jsonl"

    def store(self, document: dict[str, Any]) -> None:
        fd, temporary = tempfile.mkstemp(
            prefix=f".{self.manifest.name}.", dir=str(self.root)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                json.dump(document, output, sort_keys=True, separators=(",", ":"))
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, self.manifest)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass

    def load(self) -> dict[str, Any]:
        return json.loads(self.manifest.read_text())

    def event(self, lifecycle: str, exit_status: int | None = None) -> None:
        document = {
            "schema_version": 2,
            "at": utc_now(),
            "job_id": self.args.job_id,
            "kind": "shell",
            "lifecycle": lifecycle,
            "scope_unit": self.args.scope_unit,
            "cgroup": current_cgroup(),
            "exit_status": exit_status,
        }
        with self.events.open("a", encoding="utf-8") as output:
            json.dump(document, output, sort_keys=True, separators=(",", ":"))
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.chmod(self.events, 0o600)

    def update(self, lifecycle: str, exit_status: int | None = None) -> None:
        document = self.load()
        document["lifecycle"] = lifecycle
        document["updated_at"] = utc_now()
        document["exit_status"] = exit_status
        if exit_status is not None:
            document["completion"] = {
                "duration_seconds": max(0, time.time() - document["started_epoch"]),
                "verification": {
                    "exit_status": exit_status,
                    "outcome": "passed" if exit_status == 0 else "failed",
                },
            }
        self.store(document)
        self.event(lifecycle, exit_status)

    def run(self, request: dict[str, Any]) -> int:
        command = request["argv"]
        log_path = self.root / f"{self.args.job_id}.log"
        now = utc_now()
        document = {
            "schema_version": 4,
            "kind": "shell",
            "job_id": self.args.job_id,
            "launch_id": self.args.launch_id,
            "created_at": now,
            "updated_at": now,
            "started_epoch": time.time(),
            "lifecycle": "running",
            "command": {
                "argv": command,
                "argv_sha256": hashlib.sha256(
                    json.dumps(command, separators=(",", ":")).encode()
                ).hexdigest(),
                "cwd": request["cwd"],
                "identity": request["identity"],
            },
            "artifacts": {"log": str(log_path)},
            "launcher": {
                "pid": os.getpid(),
                "proc_start": proc_start(os.getpid()),
                "scope_unit": self.args.scope_unit,
                "cgroup": current_cgroup(),
            },
            "resource_overrides": {"RuntimeMaxSec": request["timeout_seconds"]},
            "exit_status": None,
        }
        self.store(document)
        self.event("running")
        with log_path.open("wb") as output:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=subprocess.STDOUT,
                cwd=request["cwd"],
                env=request["environment"],
                start_new_session=True,
            )
            try:
                exit_status = process.wait(timeout=request["timeout_seconds"])
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait()
                self.update("timed_out", 124)
                return 124
        if exit_status < 0:
            exit_status = 128 + (-exit_status)
        self.update("succeeded" if exit_status == 0 else "failed", exit_status)
        return exit_status


def load_request(path: Path, job_id: str, launch_id: str) -> dict[str, Any]:
    try:
        request = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("execution request is unavailable") from exc
    if request.get("job_id") != job_id or request.get("launch_id") != launch_id:
        raise ValueError("execution request identity mismatch")
    argv = request.get("argv")
    if (
        not isinstance(argv, list)
        or not 1 <= len(argv) <= 128
        or any(not isinstance(value, str) for value in argv)
    ):
        raise ValueError("execution request argv is malformed")
    if not isinstance(request.get("cwd"), str) or not isinstance(
        request.get("identity"), str
    ):
        raise ValueError("execution request is malformed")
    if not isinstance(request.get("environment"), dict) or any(
        not isinstance(name, str) or not isinstance(value, str)
        for name, value in request["environment"].items()
    ):
        raise ValueError("execution request environment is malformed")
    if not isinstance(request.get("timeout_seconds"), int):
        raise ValueError("execution request timeout is malformed")
    return request


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--job-id", required=True)
    value.add_argument("--launch-id", required=True)
    value.add_argument("--state-dir", required=True)
    value.add_argument("--request", required=True)
    value.add_argument("--scope-unit", required=True)
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if not JOB_ID_RE.fullmatch(args.job_id) or not JOB_ID_RE.fullmatch(args.launch_id):
        raise SystemExit("invalid job identity")
    if os.environ.get("SINNIX_AGENT_SCOPE_UNIT") != args.scope_unit:
        raise SystemExit("execution job is not running in its declared scope")
    root = Path(args.state_dir)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        reserved_launch_id = (root / ".reservations" / args.job_id / "launch-id").read_text()
    except OSError as exc:
        raise SystemExit("execution job reservation is unavailable") from exc
    if reserved_launch_id != args.launch_id:
        raise SystemExit("execution job reservation identity mismatch")
    request_path = Path(args.request)
    request = load_request(request_path, args.job_id, args.launch_id)
    request_path.unlink(missing_ok=True)
    return ExecutionJob(args).run(request)


if __name__ == "__main__":
    raise SystemExit(main())
