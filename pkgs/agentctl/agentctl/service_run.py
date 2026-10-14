"""Start declared foreground services inside the verification's existing unit.

Systemd owns the cgroup and its cancellation deadline. This command only
orders readiness and verification, and settles its children on normal exit.
Service output goes to stderr so a verifier's typed stdout remains intact.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


class Interrupted(Exception):
    def __init__(self, signum: int) -> None:
        self.signum = signum


def _stop(children: list[subprocess.Popen[Any]]) -> None:
    for child in children:
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 5
    for child in children:
        try:
            child.wait(timeout=max(0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            pass
    # Also settle descendants of a foreground command which already exited.
    for child in children:
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        child.wait()


def execute(services: list[dict[str, Any]], command: list[str]) -> int:
    children: list[subprocess.Popen[Any]] = []
    running: list[subprocess.Popen[Any]] = []

    def interrupted(signum: int, _frame: Any) -> None:
        raise Interrupted(signum)

    previous = {
        sig: signal.signal(sig, interrupted) for sig in (signal.SIGTERM, signal.SIGINT)
    }
    scratch = tempfile.TemporaryDirectory(prefix="agentctl-services-")
    try:
        for index, service in enumerate(services):
            environment = {
                **os.environ,
                "AGENTCTL_SERVICE_READY": str(Path(scratch.name) / f"{index}.ready"),
            }
            child = subprocess.Popen(
                service["command"],
                stdout=sys.stderr,
                stderr=sys.stderr,
                env=environment,
                start_new_session=True,
            )
            children.append(child)
            running.append(child)
            deadline = time.monotonic() + service["ready_timeout_seconds"]
            while True:
                if any(item.poll() is not None for item in running):
                    print("required service exited before readiness", file=sys.stderr)
                    return 78
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    print(
                        "required service readiness deadline expired", file=sys.stderr
                    )
                    return 78
                probe = subprocess.Popen(
                    service["ready_probe"],
                    stdout=sys.stderr,
                    stderr=sys.stderr,
                    env=environment,
                    start_new_session=True,
                )
                children.append(probe)
                try:
                    status = probe.wait(timeout=min(5, remaining))
                except subprocess.TimeoutExpired:
                    _stop([probe])
                    status = 1
                _stop([probe])
                children.remove(probe)
                if status == 0:
                    break
                time.sleep(min(0.1, max(0, deadline - time.monotonic())))
        if any(item.poll() is not None for item in running):
            return 78
        verification = subprocess.Popen(command, start_new_session=True)
        children.append(verification)
        while verification.poll() is None:
            if any(item.poll() is not None for item in running):
                print("required service exited during verification", file=sys.stderr)
                return 78
            time.sleep(0.1)
        status = verification.returncode
        return status if status >= 0 else 128 - status
    except Interrupted as error:
        return 128 + error.signum
    finally:
        # A second cancellation signal must not interrupt child settlement.
        for sig in previous:
            signal.signal(sig, signal.SIG_IGN)
        _stop(children)
        scratch.cleanup()
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def main() -> int:
    if len(sys.argv) < 4 or sys.argv[2] != "--":
        print(
            "expected service configuration followed by -- and verifier argv",
            file=sys.stderr,
        )
        return 78
    return execute(json.loads(sys.argv[1]), sys.argv[3:])


if __name__ == "__main__":
    sys.exit(main())
