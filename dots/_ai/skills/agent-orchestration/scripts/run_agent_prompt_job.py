#!/usr/bin/env python3
"""Attested job state for run_agent_prompt.sh: manifest, events, supervised run.

Extracted from the bash implementation (sinnix-gdlu). This module owns
everything that touches the job's attestation record:

  * the schema_version 3 manifest (`<state-dir>/<job-id>.json`), rendered
    byte-for-byte as jq rendered it -- 2-space indent, insertion order,
    UTF-8 with DEL escaped as \\u007f, trailing newline;
  * the schema_version 2 event log (`<state-dir>/<job-id>.events.jsonl`) and
    its journald twin;
  * the actual-agent PID/start-time attestation, taken from the direct child
    while it is alive;
  * the cgroup completion accounting (memory.peak / cpu.stat / io.stat);
  * the supervised run itself: one attempt per launcher-race retry, each with
    its own stdin snapshot, output truncation, and artifact finalization.

The manifest is attested by `sinnix-observe orphans`, so the shape here is a hard contract, not an
implementation detail.

The shell entrypoint keeps what shells are good at: option parsing and
validation, the mkdir-mode reservation lock, the self-reexec through
sinnix-agent-scope-exec, per-backend argv, and the scrubbed `env -i` prefix.
It calls `write` for each lifecycle transition, `lifecycle` to ask what the
manifest currently says, and `run` once for the supervised invocation.

Exit status semantics of `run`: the agent's own status, or -- when the agent
succeeded and artifact finalization did not -- the finalizer's status.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 3
EVENT_SCHEMA_VERSION = 2

# lifecycle -> coarse event kind, as the jq lookup table spelled it.
EVENT_KIND = {
    "accepted": "accepted",
    "starting": "starting",
    "running": "heartbeat",
    "succeeded": "completion",
    "failed": "failure",
    "cancel_requested": "approval",
    "cancelled": "completion",
    "timed_out": "failure",
}

LAUNCHER_RACE_MARKER = b"Text file busy"


def sanitize(value: str) -> str:
    """Undecodable argv bytes become U+FFFD, matching jq's --arg handling."""
    return value.encode("utf-8", "surrogateescape").decode("utf-8", "replace")


def jq_dumps(obj: Any, *, compact: bool) -> str:
    """Serialize like jq: UTF-8, DEL escaped, one trailing newline."""
    if compact:
        text = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    else:
        text = json.dumps(obj, ensure_ascii=False, indent=2)
    # jq escapes U+007F; python does not. A literal DEL byte can only occur
    # inside a string value, so a plain substitution is exact.
    return text.replace("\x7f", "\\u007f") + "\n"


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def null_if_empty(value: str) -> str | None:
    return value if value else None


def proc_start(pid: int | str) -> str:
    """Field 22 of /proc/<pid>/stat (start time), or "" when unreadable.

    Mirrors the shell's `${stat##*) }` + `awk '{print $20}'`: split after the
    last ") " so a comm containing spaces or parens cannot shift the fields.
    """
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
    except OSError:
        return ""
    rest = stat.rsplit(") ", 1)[-1]
    fields = rest.split()
    if len(fields) < 20:
        return ""
    return fields[19]


def read_first_line(path: str) -> str:
    try:
        return Path(path).read_text().strip()
    except OSError:
        return ""


class Job:
    """One agent job's attestation record."""

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.job_id = args.job_id
        self.state_dir = Path(args.job_state_dir)
        self.manifest = self.state_dir / f"{self.job_id}.json"
        self.events = self.state_dir / f"{self.job_id}.events.jsonl"
        self.actual_agent_pid = ""
        self.actual_agent_proc_start = ""

    # ---------------------------------------------------------------- events

    def append_event(self, lifecycle: str, exit_status: int | None) -> None:
        a = self.args
        event = {
            "schema_version": EVENT_SCHEMA_VERSION,
            "at": utc_now(),
            "job_id": self.job_id,
            "event": EVENT_KIND.get(lifecycle, "lifecycle"),
            "lifecycle": lifecycle,
            "scope_unit": a.scope_unit,
            "cgroup": a.scope_cgroup,
            "exit_status": exit_status,
        }
        with open(self.events, "a", encoding="utf-8") as fh:
            fh.write(jq_dumps(event, compact=True))
        os.chmod(self.events, 0o600)
        self.journal(lifecycle)

    def journal(self, lifecycle: str) -> None:
        if os.environ.get("SINNIX_AGENT_JOURNAL", "1") != "1":
            return
        if shutil.which("logger") is None:
            return
        a = self.args
        payload = (
            "SYSLOG_IDENTIFIER=sinnix-agent-job\n"
            f"MESSAGE=agent job {self.job_id} entered {lifecycle}\n"
            f"SINNIX_JOB_ID={self.job_id}\n"
            f"SINNIX_JOB_LIFECYCLE={lifecycle}\n"
            f"SINNIX_SCOPE_UNIT={a.scope_unit}\n"
            f"SINNIX_CGROUP={a.scope_cgroup}\n"
        )
        try:
            subprocess.run(
                ["logger", "--journald"],
                input=payload.encode("utf-8", "surrogateescape"),
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except OSError:
            pass

    # -------------------------------------------------------------- manifest

    def load_manifest(self) -> dict[str, Any]:
        return json.loads(self.manifest.read_text(encoding="utf-8"))

    def store_manifest(self, document: dict[str, Any], suffix: str) -> None:
        fd, tmp = tempfile.mkstemp(
            prefix=f"{self.manifest.name}.{suffix}.", dir=str(self.state_dir)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(jq_dumps(document, compact=False))
            os.chmod(tmp, 0o600)
            os.replace(tmp, self.manifest)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def current_lifecycle(self) -> str:
        try:
            document = self.load_manifest()
        except (OSError, ValueError):
            return ""
        value = document.get("lifecycle")
        return value if isinstance(value, str) else ""

    def write_manifest(self, lifecycle: str, exit_status: int | None) -> None:
        a = self.args
        updated_at = utc_now()
        created_at = updated_at
        if self.manifest.is_file():
            try:
                existing = self.load_manifest().get("created_at")
            except (OSError, ValueError):
                existing = None
            if isinstance(existing, str) and existing:
                created_at = existing
        document = {
            "schema_version": SCHEMA_VERSION,
            "job_id": self.job_id,
            "launch_id": a.launch_id,
            "created_at": created_at,
            "updated_at": updated_at,
            "lifecycle": lifecycle,
            "backend": a.backend,
            "model": a.model,
            "effort": a.effort,
            "repo": a.repo,
            "worktree": a.worktree,
            "branch": a.branch,
            "checkout_ref": null_if_empty(a.checkout_ref),
            "prompt": {"path": a.prompt_path, "sha256": a.prompt_sha256},
            "artifacts": {
                "log": a.log_path,
                "json": a.json_path,
                "final": a.final_path,
            },
            "declared": {"role": a.role, "work_item": a.work_item},
            "delegation": {
                "parent_job_id": null_if_empty(a.parent_job_id),
                "coordinator_job_id": null_if_empty(a.coordinator_job_id),
            },
            "identity": {
                "role": a.role,
                "bead_id": null_if_empty(a.work_item),
                "provider": null_if_empty(a.provider),
                "account_hash": null_if_empty(a.account_hash),
            },
            "correlation": {
                "vendor_session_id": null_if_empty(a.vendor_session_id),
                "polylogue_session_id": null_if_empty(a.polylogue_session_id),
                "kitty_socket": null_if_empty(a.kitty_socket),
                "kitty_window_id": null_if_empty(a.kitty_window_id),
                "hyprland_address": null_if_empty(a.hyprland_address),
                "quota_snapshot_id": null_if_empty(a.quota_snapshot_id),
            },
            "launcher": {
                "pid": int(a.launcher_pid),
                "proc_start": proc_start(a.launcher_pid),
                "scope_unit": a.scope_unit,
                "cgroup": a.scope_cgroup,
            },
            "resource_overrides": {
                "MemoryHigh": a.memory_high,
                "MemoryMax": a.memory_max,
                "CPUWeight": a.cpu_weight,
                "IOWeight": a.io_weight,
                "RuntimeMaxSec": a.timeout_seconds,
            },
            "exit_status": exit_status,
        }
        self.store_manifest(document, "tmp")
        self.append_event(lifecycle, exit_status)

    def update_manifest(self, patch: dict[str, Any]) -> None:
        document = self.load_manifest()
        document.update(patch)
        document["updated_at"] = utc_now()
        self.store_manifest(document, "update")

    def record_actual_agent(self, pid: int) -> None:
        """Attest pid and start time together, or not at all.

        A retry ladder attempt whose child exits before its /proc/<pid>/stat
        is readable must not leave the pid and proc_start of two different
        attempts paired in the manifest -- that pairing is what
        sinnix-observe orphans keys pid-reuse detection on. Setting
        actual_agent_pid only once its matching start time is confirmed
        keeps the last successfully-attested attempt as the recorded pair
        instead of the newest (untraceable) pid next to a stale start time.
        """
        start = proc_start(pid)
        if not start:
            return
        self.actual_agent_pid = str(pid)
        self.actual_agent_proc_start = start
        self.update_manifest(
            {
                "actual_agent": {
                    "pid": pid,
                    "proc_start": start,
                    "attested_at": utc_now(),
                }
            }
        )

    def record_completion(self, status: int, started_epoch: int) -> None:
        a = self.args
        cgroup_root = Path(f"/sys/fs/cgroup{a.scope_cgroup}")
        duration = int(time.time()) - started_epoch
        memory_peak: int | None = None
        cpu_usec: int | None = None
        io_bytes: int | None = None
        peak_text = read_first_line(str(cgroup_root / "memory.peak"))
        if peak_text:
            memory_peak = int(peak_text)
        try:
            cpu_stat = (cgroup_root / "cpu.stat").read_text()
        except OSError:
            cpu_stat = ""
        for line in cpu_stat.splitlines():
            fields = line.split()
            if len(fields) >= 2 and fields[0] == "usage_usec":
                cpu_usec = int(fields[1])
                break
        try:
            io_stat = (cgroup_root / "io.stat").read_text()
        except OSError:
            io_stat = None
        if io_stat is not None:
            total = 0
            for token in io_stat.split():
                if token.startswith(("rbytes=", "wbytes=")):
                    total += int(token.split("=", 1)[1])
            io_bytes = total
        self.update_manifest(
            {
                "completion": {
                    "duration_seconds": duration,
                    "peak_memory_bytes": memory_peak,
                    "cpu_usage_usec": cpu_usec,
                    "io_bytes": io_bytes,
                    "artifacts": {
                        "log": a.log_path,
                        "json": a.json_path,
                        "final": a.final_path,
                    },
                    "verification": {
                        "exit_status": status,
                        "outcome": "passed" if status == 0 else "failed",
                    },
                }
            }
        )

    # ------------------------------------------------------------ supervised

    def stdout_target(self) -> str:
        """The file the agent's stdout lands in for this capture plan."""
        if self.args.capture == "split":
            return self.args.json_path
        return self.args.log_path

    def run_attempt(self, argv: list[str]) -> int:
        """One agent invocation, attested and waited on. Returns wait status."""
        a = self.args
        stdin_path: str | None = None
        try:
            with contextlib.ExitStack() as stack:
                if a.stdin_file:
                    # Backends that read the prompt on stdin (codex, gemini):
                    # materialize a fresh copy per attempt, as the shell's
                    # `cat >tmp` did, so a launcher-race retry re-reads the
                    # prompt file rather than an already-drained stream.
                    fd, stdin_path = tempfile.mkstemp(
                        prefix=f"{self.job_id}.stdin.", dir=str(self.state_dir)
                    )
                    with (
                        os.fdopen(fd, "wb") as sink,
                        open(a.stdin_file, "rb") as source,
                    ):
                        shutil.copyfileobj(source, sink)
                    child_stdin = stack.enter_context(open(stdin_path, "rb"))
                else:
                    # Backends that take the prompt as an argv (claude, grok,
                    # antigravity) never read the runner's own stdin -- draining
                    # it here only served to block an interactive TTY launch
                    # that lacked its own </dev/null. Give the child a closed
                    # stdin instead of forwarding whatever the runner inherited.
                    child_stdin = stack.enter_context(open(os.devnull, "rb"))
                out = stack.enter_context(open(self.stdout_target(), "wb"))
                if a.capture == "split":
                    err = stack.enter_context(open(a.log_path, "wb"))
                else:
                    err = out
                child = subprocess.Popen(
                    argv, stdin=child_stdin, stdout=out, stderr=err
                )
            self.record_actual_agent(child.pid)
            code = child.wait()
        finally:
            if stdin_path is not None:
                try:
                    os.unlink(stdin_path)
                except OSError:
                    pass
        return 128 + (-code) if code < 0 else code

    def finalize_artifacts(self) -> int:
        """Per-attempt artifact plumbing: the shell's post-invocation step."""
        a = self.args
        if a.final == "none" or not a.final_path:
            return 0
        source = self.stdout_target()
        if a.final == "json_result":
            # jq owns this extraction: its exit status and diagnostics are
            # what the manifest and the operator have always seen.
            with open(a.final_path, "wb") as out:
                completed = subprocess.run(
                    ["jq", "-r", ".result // empty", source],
                    stdout=out,
                    check=False,
                )
            return completed.returncode
        try:
            shutil.copyfile(source, a.final_path)
        except OSError as exc:
            print(
                f"run_agent_prompt.sh: cannot copy {source} to {a.final_path}: {exc}",
                file=sys.stderr,
            )
            return 1
        return 0

    def looks_like_launcher_race(self, path: str) -> bool:
        """The transient sinnix-agent-npm-bootstrap ETXTBSY signature.

        Every wrapped-CLI invocation regenerates ~/.local/state/<tool>/launch.sh
        in place and then execve()s it; a sibling's execve() during that window
        returns ETXTBSY ("Text file busy"), independent of the model or task.
        Fixed at the source (atomic rename) in scripts/sinnix-agent-npm-bootstrap;
        this retry is defense in depth for hosts that have not rebuilt yet and
        for any other transient collision in the launcher chain. It never
        retries a genuine task failure.
        """
        overlap = len(LAUNCHER_RACE_MARKER) - 1
        tail = b""
        try:
            with open(path, "rb") as fh:
                while chunk := fh.read(1 << 20):
                    if LAUNCHER_RACE_MARKER in tail + chunk:
                        return True
                    tail = chunk[-overlap:]
        except OSError:
            return False
        return False

    def race_detected(self) -> bool:
        if self.looks_like_launcher_race(self.args.log_path):
            return True
        json_path = self.args.json_path
        return bool(json_path) and self.looks_like_launcher_race(json_path)

    def rotate(self, path: str, attempt: int) -> None:
        try:
            os.replace(path, f"{path}.attempt{attempt}")
        except OSError:
            pass

    def supervise(self, argv: list[str]) -> int:
        a = self.args
        retry_attempt = 0
        while True:
            agent_status = self.run_attempt(argv)
            finalize_status = self.finalize_artifacts()
            status = agent_status if agent_status != 0 else finalize_status
            if status == 0 or retry_attempt >= a.max_retries:
                return status
            if not self.race_detected():
                return status
            retry_attempt += 1
            self.rotate(a.log_path, retry_attempt)
            if a.json_path:
                self.rotate(a.json_path, retry_attempt)
            print(
                "run_agent_prompt.sh: launcher race detected, retrying "
                f"(attempt {retry_attempt}/{a.max_retries})",
                file=sys.stderr,
            )
            time.sleep(random.randint(100, 999) / 1000)


def add_manifest_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--job-state-dir", required=True)
    parser.add_argument("--launch-id", default="")
    parser.add_argument("--backend", default="")
    parser.add_argument("--model", default="")
    parser.add_argument("--effort", default="")
    parser.add_argument("--repo", default="")
    parser.add_argument("--worktree", default="")
    parser.add_argument("--branch", default="")
    parser.add_argument("--checkout-ref", default="")
    parser.add_argument("--prompt-path", default="")
    parser.add_argument("--prompt-sha256", default="")
    parser.add_argument("--log-path", default="")
    parser.add_argument("--json-path", default="")
    parser.add_argument("--final-path", default="")
    parser.add_argument("--role", default="")
    parser.add_argument("--work-item", default="")
    parser.add_argument("--parent-job-id", default="")
    parser.add_argument("--coordinator-job-id", default="")
    parser.add_argument("--provider", default="")
    parser.add_argument("--account-hash", default="")
    parser.add_argument("--vendor-session-id", default="")
    parser.add_argument("--polylogue-session-id", default="")
    parser.add_argument("--kitty-socket", default="")
    parser.add_argument("--kitty-window-id", default="")
    parser.add_argument("--hyprland-address", default="")
    parser.add_argument("--quota-snapshot-id", default="")
    parser.add_argument("--scope-unit", default="")
    parser.add_argument("--scope-cgroup", default="")
    parser.add_argument("--launcher-pid", default="0")
    parser.add_argument("--memory-high", default="")
    parser.add_argument("--memory-max", default="")
    parser.add_argument("--cpu-weight", default="")
    parser.add_argument("--io-weight", default="")
    parser.add_argument("--timeout-seconds", default="")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    write = sub.add_parser("write", help="render the manifest for a lifecycle")
    add_manifest_options(write)
    write.add_argument("--lifecycle", required=True)
    write.add_argument("--exit-status", default="")

    lifecycle = sub.add_parser("lifecycle", help="print the recorded lifecycle")
    add_manifest_options(lifecycle)

    run = sub.add_parser("run", help="run the agent under attestation")
    add_manifest_options(run)
    run.add_argument("--job-started-epoch", type=int, required=True)
    run.add_argument("--max-retries", type=int, default=0)
    run.add_argument("--capture", choices=("split", "merged"), required=True)
    run.add_argument("--final", choices=("none", "copy", "json_result"), default="none")
    run.add_argument("--stdin-file", default="")
    return parser


def main() -> int:
    raw = sys.argv[1:]
    agent_argv: list[str] = []
    if "--" in raw:
        cut = raw.index("--")
        raw, agent_argv = raw[:cut], raw[cut + 1 :]
    args = build_parser().parse_args(raw)
    for key, value in vars(args).items():
        if isinstance(value, str):
            setattr(args, key, sanitize(value))
    agent_argv = [sanitize(item) for item in agent_argv]

    job = Job(args)
    if args.command == "lifecycle":
        lifecycle = job.current_lifecycle()
        if lifecycle:
            print(lifecycle)
        return 0
    if args.command == "write":
        exit_status = int(args.exit_status) if args.exit_status != "" else None
        job.write_manifest(args.lifecycle, exit_status)
        return 0

    status = job.supervise(agent_argv)
    job.write_manifest("succeeded" if status == 0 else "failed", status)
    if job.actual_agent_pid and job.actual_agent_proc_start:
        job.update_manifest(
            {
                "actual_agent": {
                    "pid": int(job.actual_agent_pid),
                    "proc_start": job.actual_agent_proc_start,
                    "attested_at": utc_now(),
                }
            }
        )
    job.record_completion(status, args.job_started_epoch)
    return status


if __name__ == "__main__":
    sys.exit(main())
