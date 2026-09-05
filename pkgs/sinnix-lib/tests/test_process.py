"""Contracts of the one subprocess wrapper and the lenient scalar reads."""

import sys

from sinnix_lib.process import NO_EXIT_STATUS, run
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
