"""Exercise the rendered daily backup's snapshot ownership and writer restoration."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory(prefix="telemetry-backup-owner-") as scratch:
    root = Path(scratch)
    body = Path(sys.argv[1]).read_text().replace("/realm/", str(root) + "/")
    assert "/realm/" not in body
    dbroot = root / "state/machine-telemetry"
    dbroot.mkdir(parents=True)
    snapshots = root / "state/machine-telemetry-backup-snapshots"
    snapshots.mkdir()
    bindir = root / "bin"
    bindir.mkdir()
    fake = bindir / "fixture"
    fake.write_text(
        f"#!{sys.executable}\n"
        + r"""
import json, os, sys
from pathlib import Path
root=Path(os.environ['OWNER_FIXTURE_ROOT'])
name=Path(sys.argv[0]).name
args=sys.argv[1:]
if name=='date':print('20000101T000000Z')
elif name=='install':Path(args[-1]).mkdir(parents=True,exist_ok=True)
elif name=='chown':pass
elif name=='systemctl':
    state=root/'collector-state'
    if args[0]=='is-active':raise SystemExit(0 if state.read_text()=='active' else 3)
    state.write_text('active' if args[0]=='start' else 'inactive')
elif name=='btrfs':
    path=Path(args[-1])
    if args[1]=='snapshot':path.mkdir()
    elif args[1]=='delete':
        with (root/'deleted').open('a') as stream:stream.write(str(path)+'\n')
        path.rmdir()
    else:raise AssertionError(args)
elif name=='sinnix-sqlite-backup':
    assert (root/'collector-state').read_text()=='active'
    if os.environ.get('FAIL_CHECK'):raise SystemExit(1)
    Path(args[-1]).write_bytes(b'fixture backup')
elif name in ('sqlite3','machine-telemetry-segments'):pass
else:raise AssertionError(name)
"""
    )
    fake.chmod(0o755)
    for name in (
        "date",
        "install",
        "chown",
        "systemctl",
        "btrfs",
        "sinnix-sqlite-backup",
        "sqlite3",
        "machine-telemetry-segments",
    ):
        (bindir / name).symlink_to(fake)
    script = root / "backup.sh"
    script.write_text(body)
    state = root / "collector-state"
    state.write_text("active")
    env = {
        **os.environ,
        "PATH": str(bindir) + os.pathsep + os.environ["PATH"],
        "OWNER_FIXTURE_ROOT": str(root),
    }

    def run(invocation, fail=False):
        result = subprocess.run(
            ["bash", str(script)],
            env={
                **env,
                "INVOCATION_ID": invocation,
                **({"FAIL_CHECK": "1"} if fail else {}),
            },
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert state.read_text() == "active", result.stderr
        return result

    occupied = snapshots / ("telemetry-20000101T000000Z-" + "a" * 32)
    occupied.mkdir()
    (occupied / "retained").write_text("preexisting native package")
    result = run("a" * 32)
    assert result.returncode != 0
    assert (occupied / "retained").read_text() == "preexisting native package"
    assert not (root / "deleted").exists()
    result = run("b" * 32)
    assert result.returncode == 0, result.stderr
    proofs = list((root / "state/db-dumps/machine-telemetry").glob("*.sqlite.zst"))
    assert len(proofs) == 1
    proof = proofs[0].read_bytes()
    result = run("c" * 32, fail=True)
    assert result.returncode != 0
    assert proofs[0].read_bytes() == proof
    assert len(list(proofs[0].parent.glob("*.sqlite.zst"))) == 1
    deleted = (root / "deleted").read_text().splitlines()
    assert len(deleted) == 2 and all(str(occupied) != p for p in deleted)
    assert all(not Path(p).exists() for p in deleted)
    print(
        "rendered daily backup: unique artifacts, preserved success, owned snapshot cleanup and writer restoration passed"
    )
