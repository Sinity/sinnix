"""Bounded byte subprocess execution with one compatibility wrapper.

Probes shell out to tools that may be absent, may hang, and may fail, and
every caller that hand-rolled the guard invented a different way to say "no
answer": ``None``, a ``CompletedProcess`` or ``None``, a ``(rc, out, err)``
tuple, a stripped stdout string. ``run`` always returns a :class:`Result`,
so "the command failed" and "the command never ran" are readable from the
same value instead of from a sentinel the caller has to remember.

A missing binary, a spawn failure and a timeout are outcomes, not
exceptions: a collector that raises on an absent tool reports an outage it
invented. They come back with ``error`` set and ``returncode``
``NO_EXIT_STATUS``, carrying whatever output the command produced before it
was killed.

New callers that need byte limits or streaming use :func:`run_bounded`
directly.
"""

from __future__ import annotations

import os
import selectors
import signal
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

# No process ever reported this: the command produced no exit status at all.
NO_EXIT_STATUS = -1

# After the group is killed, pipes get this long to reach EOF. A descendant
# that left the group (setsid) survives the kill and may hold a pipe open for
# as long as it likes; the drain ends here and the output is reported
# incomplete instead of extending the caller's deadline.
DRAIN_GRACE_SECONDS = 0.25


def _decoded(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return value if isinstance(value, str) else ""


@dataclass(frozen=True)
class Result:
    """What one command did. ``error`` is set only when it never ran to an
    exit status, which is the one thing an exit code cannot express."""

    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.returncode == 0

    @property
    def text(self) -> str | None:
        """Stripped stdout of a successful command, else None."""
        return self.stdout.strip() if self.ok else None


@dataclass(frozen=True)
class BoundedResult:
    """The byte-level result of :func:`run_bounded`.

    ``error`` describes a failure to start or supervise the command.  A
    non-zero ``returncode`` is an ordinary process exit and therefore does
    not populate ``error``.  ``timed_out`` and ``limited`` identify the two
    supervisory failures that terminate a running process.
    ``output_incomplete`` means a pipe was still open when the post-kill
    drain ended: a process outside the killed group held it, may still run,
    and whatever it wrote after the drain is not here.
    """

    argv: tuple[str, ...]
    returncode: int | None
    stdout: bytes
    stderr: bytes
    error: str | None = None
    timed_out: bool = False
    limited: bool = False
    combined_output: bytes = b""
    stopped_early: bool = False
    error_type: str | None = None
    exit_status: int | None = None
    output_incomplete: bool = False

    @property
    def ok(self) -> bool:
        return self.error is None and self.returncode == 0


def _kill_group(process: subprocess.Popen[bytes]) -> None:
    """Kill *process* and every descendant in its private process group."""

    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def run_bounded(
    argv: Sequence[str],
    *,
    timeout: float,
    env: Mapping[str, str] | None = None,
    cwd: Path | str | None = None,
    stdin: bytes | None = None,
    stdout_limit: int | None = None,
    stderr_limit: int | None = None,
    combined_limit: int | None = None,
    on_stdout_chunk: Callable[[bytes], bool | None] | None = None,
    capture_stdout: bool = True,
    capture_combined: bool = False,
) -> BoundedResult:
    """Run *argv* with byte-oriented pipes and bounded supervision.

    The child starts a new process group.  Its stdout and stderr are drained
    concurrently, so a noisy child cannot deadlock on either pipe.  Limits
    count bytes retained and cause the whole process group to be killed when
    crossed.  ``on_stdout_chunk`` receives stdout chunks in arrival order.
    Returning ``False`` stops the process successfully. Set ``capture_stdout``
    false when a consumer handles the bytes directly and the result should not
    buffer them.

    ``stdin`` is written as bytes and then closed.  ``env`` follows
    :class:`subprocess.Popen` semantics: ``None`` inherits the current
    environment, while a mapping replaces it.  ``timeout`` is a deadline for
    the complete operation, including draining pipes after the leader exits;
    once it passes, the group is killed and draining ends within
    ``DRAIN_GRACE_SECONDS``.

    An exception from ``on_stdout_chunk`` that is not an ``Exception``
    (KeyboardInterrupt, a cancellation) propagates, but only after the group
    is killed and the leader reaped: nothing this call started keeps running
    in the group once it returns or raises.
    """
    args = tuple(argv)
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    for name, limit in (
        ("stdout_limit", stdout_limit),
        ("stderr_limit", stderr_limit),
        ("combined_limit", combined_limit),
    ):
        if limit is not None and limit < 0:
            raise ValueError(f"{name} must be non-negative")

    try:
        process = subprocess.Popen(
            list(args),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            env=dict(env) if env is not None else None,
            start_new_session=True,
        )
    except OSError as exc:
        return BoundedResult(
            args, None, b"", b"", error=str(exc), error_type=type(exc).__name__
        )

    selector = selectors.DefaultSelector()
    stdout_chunks: list[bytes] = []
    stderr_chunks: list[bytes] = []
    combined_chunks: list[bytes] = []
    stdout_size = stderr_size = 0
    total_output_size = 0
    started = time.monotonic()
    killed = False
    killed_at = 0.0
    output_incomplete = False
    timed_out = False
    limited = False
    failure: str | None = None
    stopped_early = False

    def close_stream(fileobj: object) -> None:
        try:
            if fileobj is not None:
                fileobj.close()  # type: ignore[union-attr]
        except OSError:
            pass

    def stop_group() -> None:
        nonlocal killed, killed_at
        killed = True
        killed_at = time.monotonic()
        _kill_group(process)

    def kill(reason: str, *, is_timeout: bool = False, is_limit: bool = False) -> None:
        nonlocal failure, timed_out, limited
        if killed:
            return
        failure = reason
        timed_out = is_timeout
        limited = is_limit
        stop_group()

    try:
        assert process.stdout is not None
        assert process.stderr is not None
        os.set_blocking(process.stdout.fileno(), False)
        os.set_blocking(process.stderr.fileno(), False)
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        selector.register(process.stderr, selectors.EVENT_READ, "stderr")

        if stdin:
            assert process.stdin is not None
            os.set_blocking(process.stdin.fileno(), False)
            selector.register(process.stdin, selectors.EVENT_WRITE, "stdin")
            input_view = memoryview(stdin)
        else:
            close_stream(process.stdin)
            input_view = memoryview(b"")

        # EOF on both pipes does not prove the leader finished: a process may
        # deliberately close stdout/stderr and continue running. Keep the
        # deadline in force until it exits, rather than falling through to an
        # unbounded wait below.
        while selector.get_map() or process.poll() is None:
            now = time.monotonic()
            remaining = timeout - (now - started)
            if remaining <= 0 and not killed:
                kill(f"timed out after {timeout:g}s", is_timeout=True)
            if killed:
                # One final bound for the drain, whatever still holds a pipe.
                remaining = killed_at + DRAIN_GRACE_SECONDS - now
                if remaining <= 0:
                    for key in list(selector.get_map().values()):
                        if key.data != "stdin":
                            output_incomplete = True
                        selector.unregister(key.fileobj)
                        close_stream(key.fileobj)
                    break

            if not selector.get_map():
                if process.poll() is None:
                    time.sleep(min(remaining, 0.01))
                continue

            # Before the deadline, a leader that exited while a descendant
            # still holds a pipe is drained under the same deadline.
            events = selector.select(min(remaining, 0.1))
            if not events:
                continue

            for key, _ in events:
                kind = key.data
                if kind == "stdin":
                    try:
                        written = os.write(key.fd, input_view[:65536])
                        input_view = input_view[written:]
                        if not input_view:
                            selector.unregister(key.fileobj)
                            close_stream(process.stdin)
                    except BlockingIOError:
                        continue
                    except (BrokenPipeError, OSError):
                        selector.unregister(key.fileobj)
                        close_stream(process.stdin)
                else:
                    try:
                        chunk = os.read(key.fd, 65536)
                    except OSError:
                        chunk = b""
                    if not chunk:
                        try:
                            selector.unregister(key.fileobj)
                        except KeyError:
                            pass
                        close_stream(key.fileobj)
                        continue

                    stream_size = stdout_size if kind == "stdout" else stderr_size
                    stream_limit = (
                        stdout_limit
                        if kind == "stdout" and capture_stdout
                        else stderr_limit
                        if kind == "stderr"
                        else None
                    )
                    total_size_before = total_output_size
                    total_output_size += len(chunk)
                    allowed = len(chunk)
                    if stream_limit is not None:
                        allowed = min(allowed, max(stream_limit - stream_size, 0))
                    if combined_limit is not None:
                        allowed = min(
                            allowed, max(combined_limit - total_size_before, 0)
                        )
                    retained = chunk[:allowed]
                    if capture_combined and retained:
                        combined_chunks.append(retained)
                    if kind == "stdout":
                        if retained and capture_stdout:
                            stdout_chunks.append(retained)
                            stdout_size += len(retained)
                        if on_stdout_chunk is not None and not stopped_early:
                            try:
                                callback_chunk = (
                                    chunk if not capture_stdout else retained
                                )
                                if on_stdout_chunk(callback_chunk) is False:
                                    stopped_early = True
                                    stop_group()
                            except Exception as exc:
                                kill(f"stdout callback failed: {exc}")
                    else:
                        if retained:
                            stderr_chunks.append(retained)
                            stderr_size += len(retained)

                    exceeded_stream = (
                        stream_limit is not None
                        and stream_size + len(chunk) > stream_limit
                    )
                    exceeded_combined = (
                        combined_limit is not None
                        and total_size_before + len(chunk) > combined_limit
                    )
                    if exceeded_stream or exceeded_combined:
                        if exceeded_stream:
                            description = (
                                f"{kind} exceeded limit of {stream_limit} bytes"
                            )
                        elif exceeded_combined:
                            description = f"combined output exceeded limit of {combined_limit} bytes"
                        kill(description, is_limit=True)

            if killed:
                try:
                    selector.unregister(process.stdin)
                except (KeyError, ValueError):
                    pass
                close_stream(process.stdin)

        returncode = process.wait()
    except BaseException:
        # KeyboardInterrupt or cancellation from a callback or a signal: the
        # caller stops waiting, so nothing it started may keep running.
        _kill_group(process)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        raise
    finally:
        selector.close()
        close_stream(process.stdin)
        close_stream(process.stdout)
        close_stream(process.stderr)

    return BoundedResult(
        args,
        None if killed else returncode,
        b"".join(stdout_chunks),
        b"".join(stderr_chunks),
        error=failure,
        timed_out=timed_out,
        limited=limited,
        combined_output=b"".join(combined_chunks),
        stopped_early=stopped_early,
        exit_status=returncode,
        output_incomplete=output_incomplete,
    )


def run(
    argv: Sequence[str],
    *,
    timeout: float,
    cwd: Path | str | None = None,
) -> Result:
    """Run *argv* to completion or to *timeout*, and always return a Result.

    ``timeout`` is required: an unbounded probe is how a collector becomes
    the outage it was watching.
    """
    result = run_bounded(argv, timeout=timeout, cwd=cwd)
    return Result(
        result.argv,
        NO_EXIT_STATUS if result.returncode is None else result.returncode,
        _decoded(result.stdout),
        _decoded(result.stderr),
        error=result.error,
    )
