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
        ("realm-day-a", 30),
        ("realm-day-b", 30),
        ("genome-genome.current", 0),
        ("genome-genome.old", 400),
        ("genome-genome.day-a", 30),
        ("genome-genome.day-b", 30),
        ("genome-unrelated", 400),
        ("sinnix-prime-realm-expired", 400),
        ("sinnix-prime-realm-a", 100),
        ("sinnix-prime-realm-b", 99),
        ("sinnix-prime-realm-c", 98),
        ("unrelated", 400),
    ]:
        moment = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=age)
        if "day-" in name:
            moment = moment.replace(
                hour=12, minute=10 if name.endswith("-a") else 20, second=0
            )
        stamp = moment.strftime("%Y-%m-%dT%H:%M:%S")
        run(
            ["borg", "create", "--timestamp", stamp, f"{repo}::{name}", "payload"],
            cwd=root,
            env=env,
        )
    native_repositories = []
    for name in ("borg-sinex-core-v1", "borg-sinex-keys-v1"):
        native = repo.parent / name
        run(["borg", "init", "--encryption=none", str(native)], env=env)
        for suffix, age in (("current", 0), ("old", 400), ("day-a", 30), ("day-b", 30)):
            moment = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=age)
            if suffix.startswith("day-"):
                moment = moment.replace(
                    hour=12, minute=10 if suffix.endswith("a") else 20, second=0
                )
            run(
                [
                    "borg", "create", "--timestamp",
                    moment.strftime("%Y-%m-%dT%H:%M:%S"),
                    f"{native}::sinex-core-{suffix}", "payload",
                ],
                cwd=root,
                env=env,
            )
        native_repositories.append(native)

    script = root / "maintenance.sh"
    script.write_text(Path(sys.argv[1]).read_text())

    def archives(repository=repo):
        return {
            a["name"]
            for a in json.loads(
                run(["borg", "list", "--json", str(repository)], env=env).stdout
            )["archives"]
        }

    before = {
        repository: archives(repository)
        for repository in [repo, *native_repositories]
    }
    run(["bash", str(script)], env=dict(env, SINNIX_BORG_MAINTENANCE_DRY_RUN="1"))
    assert all(
        archives(repository) == names for repository, names in before.items()
    ), "preview changed archives"
    run(["bash", str(script)], env=env)
    # Borg preserves the oldest endpoint while fewer than six months exist.
    assert archives() == {
        "realm-current",
        "realm-old",
        "realm-day-b",
        "genome-genome.current",
        "genome-genome.old",
        "genome-genome.day-b",
        "genome-unrelated",
        "sinnix-prime-realm-a",
        "sinnix-prime-realm-c",
        "unrelated",
    }, archives()
    restored = run(
        ["borg", "extract", "--stdout", f"{repo}::realm-current", "payload"], env=env
    ).stdout
    assert restored == (root / "payload").read_text()
    for native in native_repositories:
        assert archives(native) == {
            "sinex-core-current",
            "sinex-core-old",
            "sinex-core-day-b",
        }, archives(native)
        restored = run(
            ["borg", "extract", "--stdout", f"{native}::sinex-core-current", "payload"],
            env=env,
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
