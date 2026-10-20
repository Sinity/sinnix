"""Keep a native rebuild unit alive only while its initiating process lives.

The service uses ExitType=main and KillMode=control-group. Returning stops its
cgroup through systemd;
it must not wait for a surviving workload after its caller has disappeared.
"""

import argparse
import os
import selectors
import signal
import sys
from pathlib import Path


class CallerGone(Exception):
    pass


def start_ticks(pid):
    # comm may contain spaces and parentheses; fields after its final ')' do not.
    return int(Path(f"/proc/{pid}/stat").read_text().rsplit(") ", 1)[1].split()[19])


def run_owned(owner_pid, owner_start, command, chrt):
    owner_fd = child_fd = None
    try:
        try:
            owner_fd = os.pidfd_open(owner_pid)
            if start_ticks(owner_pid) != owner_start:
                raise CallerGone
        except (ProcessLookupError, FileNotFoundError):
            raise CallerGone from None
        with selectors.DefaultSelector() as selector:
            selector.register(owner_fd, selectors.EVENT_READ, "owner")
            if selector.select(0):
                raise CallerGone
            # Only the workload uses batch scheduling. The tiny lifecycle controller must
            # remain schedulable when ordinary work occupies every CPU.
            argv = [chrt, "--batch", "0", *command]
            child = os.posix_spawn(chrt, argv, dict(os.environ))
            child_fd = os.pidfd_open(child)
            selector.register(child_fd, selectors.EVENT_READ, "child")
            while True:
                events = selector.select()
                if any(key.data == "owner" for key, _ in events):
                    raise CallerGone
                # Prefer cancellation if both processes exited together.
                if any(key.data == "owner" for key, _ in selector.select(0)):
                    raise CallerGone
                if any(key.data == "child" for key, _ in events):
                    _, status = os.waitpid(child, 0)
                    code = os.waitstatus_to_exitcode(status)
                    return code if code >= 0 else 128 - code
    finally:
        for fd in (child_fd, owner_fd):
            if fd is not None:
                os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--owner-pid", type=int, required=True)
    parser.add_argument("--owner-start-ticks", type=int, required=True)
    parser.add_argument("--chrt", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if args.owner_pid <= 0 or args.owner_start_ticks <= 0 or not command:
        parser.error("positive caller identity and a command are required")
    if os.environ.get("SYSTEMD_EXEC_PID") != str(os.getpid()):
        print("rebuild guard must be the native service main process", file=sys.stderr)
        return 64
    if args.owner_pid == os.getpid():
        parser.error("caller must be a different process")
    for number in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(number, lambda sig, _frame: sys.exit(128 + sig))
    signal.signal(signal.SIGCHLD, signal.SIG_DFL)
    try:
        return run_owned(args.owner_pid, args.owner_start_ticks, command, args.chrt)
    except CallerGone:
        # Caller-owned output may be full. Exit immediately so systemd can
        # terminate the workload cgroup without needing a writable pipe.
        return 143
    except (OSError, ValueError):
        # The same output constraint applies to identity and spawn failures.
        return 69


if __name__ == "__main__":
    raise SystemExit(main())
