"""The cached nix-develop realization."""

from __future__ import annotations

import os
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
