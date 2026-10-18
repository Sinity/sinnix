"""Exercise the rendered weekly seal unit without touching host storage."""

import fcntl
import os
from pathlib import Path
import subprocess
import sys
import tempfile


with tempfile.TemporaryDirectory(prefix="telemetry-seal-") as scratch:
    root = Path(scratch)
    body = Path(sys.argv[1]).read_text()
    assert "/realm/" in body
    body = body.replace("/realm/", str(root) + "/")
    dbroot = root / "state/machine-telemetry"
    dbroot.mkdir(parents=True)
    maintenance = dbroot / ".maintenance.lock"
    maintenance.write_bytes(b"existing owner evidence must not be truncated")
    bindir = root / "bin"
    bindir.mkdir()
    fake = bindir / "owner-fixture"
    fake.write_text(f"#!{sys.executable}\n" + r'''
import os,sys
from pathlib import Path
root=Path(os.environ['OWNER_FIXTURE_ROOT'])
name=Path(sys.argv[0]).name
args=sys.argv[1:]
if name=='chown':pass
elif name=='systemctl':
    state=root/'collector-state'
    assert args[-1]=='machine-telemetry.service'
    if args[0]=='is-active':raise SystemExit(0 if state.read_text()=='active' else 3)
    state.write_text('active' if args[0]=='start' else 'inactive')
elif name=='machine-telemetry-segments':
    with (root/'calls').open('a') as stream:stream.write(args[0]+'\n')
    if args[0]=='seal':
        assert (root/'collector-state').read_text()=='inactive'
        if os.environ.get('FAIL_SEAL'):raise SystemExit(1)
    else:
        assert (root/'collector-state').read_text()=='active'
else:raise AssertionError(name)
''')
    fake.chmod(0o755)
    for name in ("systemctl", "chown", "machine-telemetry-segments"):
        (bindir / name).symlink_to(fake)
    script = root / "seal.sh"
    script.write_text(body)
    state = root / "collector-state"
    state.write_text("active")
    environment = {**os.environ, "PATH": str(bindir) + os.pathsep + os.environ["PATH"],
                   "OWNER_FIXTURE_ROOT": str(root)}

    def run(**extra):
        return subprocess.run(["bash", str(script)], env={**environment, **extra},
                              capture_output=True, text=True, timeout=10)

    with maintenance.open("a") as held:
        fcntl.flock(held.fileno(), fcntl.LOCK_EX)
        busy = run()
    assert busy.returncode == 75, busy.stderr
    assert not (root / "calls").exists()

    failed = run(FAIL_SEAL="1")
    assert failed.returncode != 0
    assert state.read_text() == "active", "a failed seal must restart the collector"
    assert (root / "calls").read_text().split() == ["seal"]

    (root / "calls").unlink()
    done = run()
    assert done.returncode == 0, done.stderr
    assert state.read_text() == "active"
    assert (root / "calls").read_text().split() == ["seal", "archive", "verify"]
    assert maintenance.read_bytes() == b"existing owner evidence must not be truncated"
    print("rendered seal unit: lock serialization, writer restoration and once-only checks after sealing")
