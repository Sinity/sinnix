"""Contracts of the one subprocess wrapper and the lenient scalar reads."""

import errno
import os
import sys
import time

from sinnix_lib import process as process_module
from sinnix_lib.process import NO_EXIT_STATUS, run, run_bounded
from sinnix_lib.values import float_or_none, int_or_none, read_text

SLEEP = [sys.executable, "-c", "import time; time.sleep(30)"]


def test_run_reports_stdout_and_success():
    result = run([sys.executable, "-c", "print('hello')"], timeout=30)
    assert result.ok
    assert result.returncode == 0
    assert result.text == "hello"


def test_run_reports_a_nonzero_exit_without_raising():
    result = run([sys.executable, "-c", "import sys; sys.exit(3)"], timeout=30)
    assert not result.ok
    assert result.returncode == 3
    # A command that ran has no `error`: the exit status already said it all.
    assert result.error is None
    assert result.text is None


def test_run_returns_a_result_when_the_command_hangs():
    """A probe that outlives its timeout is an outcome, not an exception.

    Mutation: drop TimeoutExpired from the wrapper's except clause and this
    test errors out with subprocess.TimeoutExpired instead of failing an
    assertion -- the caller would inherit the raise the wrapper exists to
    absorb.
    """
    result = run(SLEEP, timeout=0.2)
    assert not result.ok
    assert result.returncode == NO_EXIT_STATUS
    assert result.error is not None
    assert "timed out" in result.error


def test_run_timeout_kills_descendants_that_hold_its_pipes():
    started = time.monotonic()
    result = run(
        [
            sys.executable,
            "-c",
            "import os, time; os.fork() and os._exit(0); time.sleep(0.8)",
        ],
        timeout=0.05,
    )
    assert result.returncode == NO_EXIT_STATUS
    assert result.error is not None
    assert time.monotonic() - started < 0.4


def test_run_timeout_survives_a_leader_that_closes_both_pipes():
    started = time.monotonic()
    result = run(
        [
            sys.executable,
            "-c",
            "import os, time; os.close(1); os.close(2); time.sleep(0.8)",
        ],
        timeout=0.05,
    )
    assert result.returncode == NO_EXIT_STATUS
    assert result.error is not None
    assert time.monotonic() - started < 0.4


def test_run_returns_a_result_when_the_binary_is_missing():
    result = run(["sinnix-no-such-binary-4f2a"], timeout=30)
    assert not result.ok
    assert result.returncode == NO_EXIT_STATUS
    assert result.error is not None


def test_run_honours_cwd(tmp_path):
    result = run(
        [sys.executable, "-c", "import os; print(os.getcwd())"],
        timeout=30,
        cwd=tmp_path,
    )
    assert result.text == str(tmp_path.resolve())


def test_run_bounded_accepts_bytes_stdin_and_environment(tmp_path):
    result = run_bounded(
        [
            sys.executable,
            "-c",
            "import os, sys; sys.stdout.buffer.write(os.environ['MARK'].encode() + b':' + sys.stdin.buffer.read())",
        ],
        timeout=30,
        cwd=tmp_path,
        env={"MARK": "from-env", "PATH": os.environ["PATH"]},
        stdin=b"from-stdin",
    )
    assert result.ok
    assert result.stdout == b"from-env:from-stdin"
    assert result.combined_output == b""


def test_run_bounded_retries_stdin_after_would_block(monkeypatch):
    original_write = os.write
    writes = 0

    def write_with_one_would_block(fd, data):
        nonlocal writes
        writes += 1
        if writes == 1:
            raise BlockingIOError(errno.EAGAIN, "temporarily unavailable")
        return original_write(fd, data)

    monkeypatch.setattr(process_module.os, "write", write_with_one_would_block)
    payload = b"stdin survives a readiness race"
    result = run_bounded(
        [
            sys.executable,
            "-c",
            "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())",
        ],
        timeout=5,
        stdin=payload,
    )

    assert result.ok
    assert result.stdout == payload
    assert writes >= 2


def test_run_bounded_drains_both_streams_and_reports_stdout_chunks():
    chunks = []
    result = run_bounded(
        [
            sys.executable,
            "-c",
            "import sys; sys.stdout.buffer.write(b'a'*100000); sys.stderr.buffer.write(b'b'*100000)",
        ],
        timeout=30,
        on_stdout_chunk=chunks.append,
    )
    assert result.ok
    assert result.stdout == b"a" * 100000
    assert result.stderr == b"b" * 100000
    assert b"".join(chunks) == result.stdout
    assert len(chunks) > 1


def test_run_bounded_enforces_per_stream_and_combined_limits():
    per_stream = run_bounded(
        [sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'x'*1000)"],
        timeout=30,
        stdout_limit=31,
    )
    assert per_stream.limited
    assert per_stream.stdout == b"x" * 31
    assert "stdout exceeded" in (per_stream.error or "")

    combined = run_bounded(
        [
            sys.executable,
            "-c",
            "import sys; sys.stdout.buffer.write(b'x'*20); sys.stderr.buffer.write(b'y'*20)",
        ],
        timeout=30,
        combined_limit=25,
        capture_combined=True,
    )
    assert combined.limited
    assert len(combined.stdout) + len(combined.stderr) == 25
    assert len(combined.combined_output) == 25
    assert "combined output exceeded" in (combined.error or "")


def test_run_bounded_timeout_kills_pipe_holding_descendants():
    started = time.monotonic()
    result = run_bounded(
        [
            sys.executable,
            "-c",
            "import os, time; os.fork() and os._exit(0); time.sleep(30)",
        ],
        timeout=0.05,
    )
    assert result.timed_out
    assert result.returncode is None
    assert time.monotonic() - started < 0.4


def test_run_bounded_missing_command_is_a_failure():
    result = run_bounded(["sinnix-no-such-binary-4f2a"], timeout=30)
    assert not result.ok
    assert result.returncode is None
    assert result.error


def test_read_text_strips_and_survives_absence(tmp_path):
    path = tmp_path / "value"
    path.write_text("  7\n")
    assert read_text(path) == "7"
    assert read_text(tmp_path / "absent") is None
    assert read_text(tmp_path) is None


def test_scalar_parsers_return_none_for_unusable_values():
    assert int_or_none("12") == 12
    assert int_or_none("1.5") is None
    assert int_or_none(None) is None
    assert float_or_none("1.5") == 1.5
    assert float_or_none("") is None
    assert float_or_none(None) is None


# A descendant that leaves the process group (setsid) survives the group kill
# and keeps the output pipe open for 1.5 s.
_SESSION_ESCAPEE = (
    "import os, time\n"
    "if os.fork() == 0:\n"
    "    os.setsid()\n"
    "    time.sleep(1.5)\n"
    "    os._exit(0)\n"
    "time.sleep(30)\n"
)


def test_run_bounded_drain_after_timeout_is_finite_and_reported():
    """Fails if a pipe held outside the killed group extends the deadline.

    Before the final drain bound, the loop kept selecting in 0.1 s steps
    until the escaped descendant exited, so a 0.35 s timeout took ~1.5 s.
    """
    started = time.monotonic()
    result = run_bounded([sys.executable, "-c", _SESSION_ESCAPEE], timeout=0.35)
    elapsed = time.monotonic() - started

    assert result.timed_out is True
    assert result.output_incomplete is True
    assert elapsed < 0.35 + process_module.DRAIN_GRACE_SECONDS + 0.4


def test_run_bounded_group_kill_reports_complete_output_when_pipes_close():
    """The incomplete flag is not set when the killed group held every pipe."""
    result = run_bounded(SLEEP, timeout=0.1)

    assert result.timed_out is True
    assert result.output_incomplete is False


def test_run_bounded_callback_interrupt_kills_and_reaps_the_group(tmp_path):
    """Fails if a KeyboardInterrupt from the callback leaves the child running.

    The child prints READY, then writes a marker after 0.5 s. Without the
    BaseException cleanup the interrupt escaped through ``finally`` and the
    child later wrote the marker.
    """
    marker = tmp_path / "marker"
    script = (
        "import sys, time\n"
        "print('READY', flush=True)\n"
        "time.sleep(0.5)\n"
        f"open({str(marker)!r}, 'w').write('late')\n"
    )

    def interrupt(chunk: bytes) -> None:
        if b"READY" in chunk:
            raise KeyboardInterrupt

    try:
        run_bounded(
            [sys.executable, "-c", script], timeout=10, on_stdout_chunk=interrupt
        )
    except KeyboardInterrupt:
        pass
    else:
        raise AssertionError("the callback's KeyboardInterrupt must propagate")

    time.sleep(1.0)
    assert not marker.exists()
