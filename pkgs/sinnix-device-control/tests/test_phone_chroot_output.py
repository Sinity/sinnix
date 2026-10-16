"""Package destinations remain relative to the caller, not build scratch."""

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts/sinnix-phone"


@pytest.mark.parametrize("relative", [True, False])
def test_chroot_output_survives_scratch_cleanup(tmp_path, relative):
    module = tmp_path / "module"
    module.mkdir()
    for name in ("module.prop", "customize.sh", "run.sh"):
        (module / name).write_text("synthetic fixture\n")
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    destination = tmp_path / "results" / "phone package.zip"
    argument = str(destination.relative_to(tmp_path) if relative else destination)
    body = (
        SCRIPT.read_text()
        .split("\nchroot_build() (", 1)[1]
        .split("\nchroot_root()", 1)[0]
    )
    shell = r"""
set -euo pipefail
chroot_module_source() { printf '%s\n' "$MODULE"; }
sudo() {
  case "$1" in
    debootstrap) [[ "$6" == "$SCRATCH/"* ]] ;;
    tar|rm) local program="$1"; shift; command "$program" "$@" ;;
    *) return 99 ;;
  esac
}
# A synthetic archive writer exercises the real destination and cleanup route.
zip() { printf 'synthetic archive\n' > "$3"; }
"""
    result = subprocess.run(
        [
            "bash",
            "-c",
            shell + "\nchroot_build() (" + body + '\nchroot_build "$1"',
            "fixture",
            argument,
        ],
        cwd=tmp_path,
        env={
            "PATH": os.environ["PATH"],
            "MODULE": str(module),
            "SCRATCH": str(scratch),
            "TMPDIR": str(scratch),
        },
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0, result.stderr
    assert destination.read_text() == "synthetic archive\n"
    assert not list(scratch.iterdir())
