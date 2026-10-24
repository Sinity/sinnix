"""Exercise the rendered maintenance policy against a disposable real Borg repo."""

import datetime as dt
import fcntl
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def run(command, **kwargs):
    return subprocess.run(command, check=True, capture_output=True, text=True, **kwargs)


with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    repo = root / "dead-holder/repos/borg-realm-v2"
    repo.parent.mkdir(parents=True)
    env = dict(
        os.environ,
        TMPDIR=str(root),
        BORG_PASSPHRASE="",
        BORG_CACHE_DIR=str(root / "cache"),
    )
    run(["borg", "init", "--encryption=none", str(repo)], env=env)
    (root / "payload").write_text("synthetic recoverable payload\n")
    for name, age in [
        ("realm-current", 0),
        ("realm-old", 400),
        ("sinnix-prime-realm-expired", 400),
        ("sinnix-prime-realm-a", 100),
        ("sinnix-prime-realm-b", 99),
        ("sinnix-prime-realm-c", 98),
        ("unrelated", 400),
    ]:
        stamp = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=age)).strftime(
            "%Y-%m-%dT%H:%M:%S"
        )
        run(
            ["borg", "create", "--timestamp", stamp, f"{repo}::{name}", "payload"],
            cwd=root,
            env=env,
        )
    script = root / "maintenance.sh"
    script.write_text(Path(sys.argv[1]).read_text())

    def archives():
        return {
            a["name"]
            for a in json.loads(
                run(["borg", "list", "--json", str(repo)], env=env).stdout
            )["archives"]
        }

    before = archives()
    run(["bash", str(script)], env=dict(env, SINNIX_BORG_MAINTENANCE_DRY_RUN="1"))
    assert archives() == before, "preview changed archives"
    run(["bash", str(script)], env=env)
    # Borg preserves the oldest endpoint while fewer than six months exist.
    assert archives() == {
        "realm-current",
        "realm-old",
        "sinnix-prime-realm-a",
        "sinnix-prime-realm-c",
        "unrelated",
    }, archives()
    restored = run(
        ["borg", "extract", "--stdout", f"{repo}::realm-current", "payload"], env=env
    ).stdout
    assert restored == (root / "payload").read_text()
    marker = root / "dead-holder/cache-drain/maintenance.last-success"
    stamp = marker.read_bytes()
    run(["bash", str(script)], env=env)
    assert marker.read_bytes() == stamp, (
        "completed pass should not repeat while not due"
    )
    marker.unlink()
    with (root / "dead-holder/global.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        result = run(["bash", str(script)], env=env)
        assert "remains_due=true" in result.stdout
        assert not marker.exists(), "contention falsely marked maintenance complete"
    run(["bash", str(script)], env=env)
    assert marker.exists(), "maintenance did not retry after contention"
print(
    "retention preview, expiry, active preservation, restore, cadence and contention retry passed"
)
