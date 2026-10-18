"""Exercise the rendered first-cutover owner without touching host storage."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


with tempfile.TemporaryDirectory(prefix="telemetry-owner-") as scratch:
    root = Path(scratch)
    body = Path(sys.argv[1]).read_text()
    assert "/realm/" in body
    body = body.replace("/realm/", str(root) + "/")
    assert "/realm/" not in body
    dbroot = root / "state/machine-telemetry"
    dbroot.mkdir(parents=True)
    maintenance = dbroot / ".maintenance.lock"
    maintenance.write_bytes(b"existing owner evidence must not be truncated")
    bindir = root / "bin"
    bindir.mkdir()
    fake = bindir / "owner-fixture"
    fake.write_text(f"#!{sys.executable}\n" + r'''
import json,os,sys
from pathlib import Path
root=Path(os.environ['OWNER_FIXTURE_ROOT'])
name=Path(sys.argv[0]).name
args=sys.argv[1:]
if name=='install':
    Path(args[-1]).mkdir(parents=True,exist_ok=True)
elif name=='systemctl':
    state=root/'collector-state'
    if args[0]=='is-active':
        if args[-1]=='machine-telemetry-sqlite-backup.service' and os.environ.get('ACTIVE_BACKUP'):raise SystemExit(0)
        raise SystemExit(0 if args[-1]=='machine-telemetry.service' and state.read_text()=='active' else 3)
    if args[0]=='show':
        print(os.getppid() if os.environ.get('ACTIVE_BACKUP')=='cooperating' else 0)
        raise SystemExit(0)
    assert args[-1]=='machine-telemetry.service'
    state.write_text('active' if args[0]=='start' else 'inactive')
elif name=='btrfs':
    assert args[:3]==['subvolume','snapshot','-r']
    Path(args[-1]).mkdir()
    with (root/'snapshot-paths').open('a') as stream:stream.write(args[-1]+'\n')
elif name=='machine-telemetry-rotate':
    db=Path(args[args.index('--db')+1])
    snapshot=Path(args[args.index('--preimage')+1])
    assert snapshot.is_dir()
    if os.environ.get('FAIL_BEFORE_JOURNAL')=='1':raise SystemExit(75)
    journal=db.with_name(db.name+'.rotation.json')
    if journal.exists():assert json.loads(journal.read_text())['snapshot']==str(snapshot)
    else:journal.write_text(json.dumps({'snapshot':str(snapshot)}))
else:raise AssertionError(name)
''')
    fake.chmod(0o755)
    for name in ("systemctl", "install", "btrfs", "machine-telemetry-rotate"):
        (bindir / name).symlink_to(fake)
    script = root / "rotate.sh"
    script.write_text(body)
    state = root / "collector-state"
    state.write_text("active")
    environment = {**os.environ, "PATH": str(bindir) + os.pathsep + os.environ["PATH"],
                   "OWNER_FIXTURE_ROOT": str(root)}
    deferred = subprocess.run(["bash", str(script)], env={**environment, "INVOCATION_ID": "d" * 32,
                              "ACTIVE_BACKUP": "old"}, capture_output=True, text=True, timeout=10)
    assert deferred.returncode == 75, deferred.stderr
    assert state.read_text() == "active" and not (root / "snapshot-paths").exists()
    first = subprocess.run(["bash", str(script)], env={**environment, "INVOCATION_ID": "a" * 32,
                           "FAIL_BEFORE_JOURNAL": "1"}, capture_output=True, text=True, timeout=10)
    assert first.returncode == 75, first.stderr
    assert state.read_text() == "active"
    assert not (dbroot / "telemetry.sqlite.rotation.json").exists()
    for invocation in ("b" * 32, "c" * 32):
        result = subprocess.run(["bash", str(script)], env={**environment, "INVOCATION_ID": invocation, "ACTIVE_BACKUP": "cooperating"},
                                capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, result.stderr
        assert state.read_text() == "active"
    paths = (root / "snapshot-paths").read_text().splitlines()
    assert len(paths) == 2 and paths[0] != paths[1]
    assert all(Path(path).is_dir() for path in paths)
    assert json.loads((dbroot / "telemetry.sqlite.rotation.json").read_text())["snapshot"] == paths[1]
    assert maintenance.read_bytes() == b"existing owner evidence must not be truncated"
    print("rendered telemetry owner: fresh retry, exact recovery, writer restoration and preimages verified")
