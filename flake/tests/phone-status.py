"""Distinguish an empty phone recording directory from an unavailable one."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

source = Path(sys.argv[1]).read_text()
status = source.split("\napp-status)\n", 1)[1].split("\n  ;;\napp-install)", 1)[0]
mock = r"""
adb_any() {
  case "$*" in
    get-state) return 0 ;;
    'shell pm list packages fixture') echo package:fixture ;;
    'shell cat /sdcard/sinnix-ambient/status.json') cat "$FIXTURE/status.json" ;;
    shell*)
      shift
      [ "${FIXTURE_MODE:-}" != transport-failed ] || return 1
      command=${1//\/sdcard\/sinnix-ambient/$FIXTURE/remote}
      bash -c "$command"
      ;;
    pull) cp "$2" "$3" ;;
    *) return 1 ;;
  esac
}
ffprobe() { echo 300; }
ffmpeg() { echo 'mean_volume: -20 dB' >&2; }
"""

with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    (root / "lake/ambient").mkdir(parents=True)
    (root / "lake/ambient/ambient-20000101.m4a").touch()
    (root / "status.json").write_text(
        json.dumps(
            {
                "updated_at": "2000-01-01T00:00:00Z",
                "recording": True,
                "chunk_dir_is_shared": True,
                "package": "fixture",
                "app_version": 1,
                "failures": 0,
            }
        )
    )

    def run():
        return subprocess.run(
            [
                "bash",
                "-c",
                "set -euo pipefail\nAPP_ID=fixture\n"
                'LAKE_ROOT="$FIXTURE/lake"\n' + mock + status,
            ],
            env={**os.environ, "FIXTURE": str(root), "TMPDIR": str(root)},
            text=True,
            capture_output=True,
            timeout=5,
        )

    # The remote ls|head predecessor hides ls failure and claims a drained phone.
    missing = run()
    assert missing.returncode != 0, missing.stdout
    assert "unavailable" in missing.stderr, missing.stderr
    assert "newest in the lake" not in missing.stdout, missing.stdout

    (root / "remote").write_text("wrong object type")
    wrong_type = run()
    assert wrong_type.returncode != 0, wrong_type.stdout
    assert "unavailable" in wrong_type.stderr, wrong_type.stderr
    (root / "remote").unlink()

    (root / "remote").mkdir()
    (root / "mocks").write_text(
        'if [ "${FIXTURE_MODE:-}" = listing-failed ]; then ls() { return 42; }; fi\n'
    )
    (root / "remote/ambient-fixture.m4a").touch()
    for mode in ("listing-failed", "transport-failed"):
        os.environ["FIXTURE_MODE"] = mode
        os.environ["BASH_ENV"] = str(root / "mocks")
        unavailable = run()
        assert unavailable.returncode != 0, unavailable.stdout
        assert "unavailable" in unavailable.stderr, unavailable.stderr
        assert "newest in the lake" not in unavailable.stdout, unavailable.stdout
    del os.environ["FIXTURE_MODE"]
    del os.environ["BASH_ENV"]
    (root / "remote/ambient-fixture.m4a").unlink()
    empty = run()
    assert empty.returncode == 0, empty.stderr
    assert "newest in the lake" in empty.stdout, empty.stdout

    for name, mtime in (("ambient-new-name.m4a", 1), ("ambient-old-name.m4a", 2)):
        path = root / "remote" / name
        path.write_bytes(b"synthetic audio")
        os.utime(path, (mtime, mtime))
    present = run()
    assert present.returncode == 0, present.stderr
    assert "last chunk: ambient-old-name.m4a" in present.stdout, present.stdout
    assert not list(root.glob("sinnix-phone-status.*"))

print(
    "Phone status: missing/wrong-type refused, empty fallback and newest-mtime measurement passed"
)
