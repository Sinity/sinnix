"""The cached nix-develop realization."""

from __future__ import annotations

import os
import json
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
from agentctl import devenv


def _fake_nix(bin_dir: Path, log: Path) -> None:
    bin_dir.mkdir()
    script = bin_dir / "nix"
    script.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then echo "nix (Nix) 9.9"; exit 0; fi\n'
        f'echo realized >> "{log}"\n'
        "echo 'export DEVENV_MARK=from-cache'\n"
    )
    script.chmod(0o755)


@pytest.fixture
def workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    tree = tmp_path / "tree"
    (tree / "nix").mkdir(parents=True)
    (tree / "flake.nix").write_text("{ }\n")
    (tree / "flake.lock").write_text("{}\n")
    (tree / "nix" / "shell.sh").write_text("echo hi\n")
    (tree / "src.py").write_text("print(1)\n")
    log = tmp_path / "realizations.log"
    _fake_nix(tmp_path / "bin", log)
    monkeypatch.setenv("PATH", f"{tmp_path / 'bin'}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    return tree, log


INPUTS = ("flake.nix", "flake.lock", "nix")


def test_an_undeclared_file_edit_reuses_the_realization(
    workdir: tuple[Path, Path],
) -> None:
    """Anti-vacuity: key on the whole tree and the second call re-realizes."""
    tree, log = workdir
    first = devenv.realize(tree, INPUTS)
    (tree / "src.py").write_text("print(2)\n")
    second = devenv.realize(tree, INPUTS)

    assert first == second
    assert log.read_text().count("realized") == 1
    assert "DEVENV_MARK=from-cache" in first.read_text()


@pytest.mark.parametrize("changed", ["flake.nix", "flake.lock", "nix/shell.sh"])
def test_a_declared_input_change_re_realizes(
    workdir: tuple[Path, Path], changed: str
) -> None:
    """Anti-vacuity: drop an input from the key and its edit is never noticed."""
    tree, log = workdir
    devenv.realize(tree, INPUTS)
    (tree / changed).write_text("changed\n")
    devenv.realize(tree, INPUTS)

    assert log.read_text().count("realized") == 2


def test_the_working_directory_is_part_of_the_key(
    workdir: tuple[Path, Path], tmp_path: Path
) -> None:
    """nix embeds the working directory in the realized outputs' prefix."""
    tree, log = workdir
    other = tmp_path / "other"
    other.mkdir()
    for name in ("flake.nix", "flake.lock"):
        (other / name).write_text((tree / name).read_text())
    (other / "nix").mkdir()
    (other / "nix" / "shell.sh").write_text((tree / "nix" / "shell.sh").read_text())

    assert devenv.realize(tree, INPUTS) != devenv.realize(other, INPUTS)
    assert log.read_text().count("realized") == 2


def _temporary_environment_command(workdir, tmp_path, command):
    tree, _log = workdir
    script = devenv.realize(tree, INPUTS)
    script.write_text(
        'export NIX_BUILD_TOP="$(mktemp -d -t nix-shell.XXXXXX)"\n'
        'export TMPDIR="$NIX_BUILD_TOP"\n'
        'export DEVENV_MARK=from-cache\n'
        'false\n'  # A failed shellHook still permits the command, as nix develop does.
    )
    temporary = tmp_path / "command-temp"
    temporary.mkdir()
    (temporary / "keep").write_text("caller-owned")
    environment = dict(os.environ)
    environment["TMPDIR"] = str(temporary)
    environment["PYTHONPATH"] = os.pathsep.join([str(Path(devenv.__file__).parent.parent), *sys.path])
    argv = [sys.executable, "-m", "agentctl.devenv", "--input", "flake.nix",
            "--input", "flake.lock", "--input", "nix", "--", *command]
    return argv, environment, temporary, tree


@pytest.mark.parametrize("exit_code", [0, 7])
def test_temporary_environment_is_cleaned_after_command(workdir, tmp_path, exit_code):
    code = (
        'import os,sys,json;from pathlib import Path;'
        'p=Path(os.environ["TMPDIR"]);(p/"child-output").write_text("temporary");'
        'print(json.dumps([os.environ["DEVENV_MARK"],sys.argv[1:],sys.stdin.read()]));'
        f'sys.exit({exit_code})'
    )
    argv, env, temporary, cwd = _temporary_environment_command(
        workdir, tmp_path, [sys.executable, "-c", code, "argument with spaces"])
    result = subprocess.run(argv, cwd=cwd, env=env, input="input payload",
                            text=True, capture_output=True, timeout=10)
    assert result.returncode == exit_code, result.stderr
    assert json.loads(result.stdout) == ["from-cache", ["argument with spaces"], "input payload"]
    assert sorted(p.name for p in temporary.iterdir()) == ["keep"]


@pytest.mark.parametrize("stop_signal", [signal.SIGTERM, signal.SIGINT])
def test_temporary_environment_is_cleaned_after_termination(workdir, tmp_path, stop_signal):
    ready = tmp_path / "ready"
    code = 'import os,signal,sys;from pathlib import Path;Path(sys.argv[1]).write_text(str(os.getpid()));signal.pause()'
    argv, env, temporary, cwd = _temporary_environment_command(
        workdir, tmp_path, [sys.executable, "-c", code, str(ready)])
    process = subprocess.Popen(argv, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        deadline = time.monotonic() + 5
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert ready.exists()
        child_pid = int(ready.read_text())
        process.send_signal(stop_signal)
        process.communicate(timeout=5)
        assert process.returncode in (-stop_signal, 128 + stop_signal)
        with pytest.raises(ProcessLookupError):
            os.kill(child_pid, 0)
        assert sorted(p.name for p in temporary.iterdir()) == ["keep"]
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()


def test_temporary_environment_preserves_inherited_descriptor(workdir, tmp_path):
    channel = tmp_path / "inherited-channel"
    descriptor = os.open(channel, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        code = 'import os,sys;os.write(int(sys.argv[1]), b"inherited payload")'
        argv, env, temporary, cwd = _temporary_environment_command(
            workdir, tmp_path, [sys.executable, "-c", code, str(descriptor)])
        result = subprocess.run(argv, cwd=cwd, env=env, pass_fds=(descriptor,),
                                text=True, capture_output=True, timeout=10)
        assert result.returncode == 0, result.stderr
        assert channel.read_bytes() == b"inherited payload"
        assert sorted(p.name for p in temporary.iterdir()) == ["keep"]
    finally:
        os.close(descriptor)
