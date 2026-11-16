"""The maintenance pass against disposable real Borg repositories."""

import datetime as dt
import fcntl
import json
from pathlib import Path

from fakes import FakeHost
from sinnix_backup import cli


def test_retention_preview_expiry_restore_cadence_and_contention(fixture_config, backup_root, monkeypatch, capfd):
    config_path, config = fixture_config
    host = FakeHost(backup_root, config.lock_path)
    host.apply(monkeypatch)
    # The fixture creates Realm and both Sinex repositories; other
    # repositories stay uninitialized.
    repo = config.repository("realm").path
    repo.parent.mkdir(parents=True, exist_ok=True)
    host.borg("init", "--encryption=none", str(repo))
    payload = backup_root / "payload"
    payload.write_text("synthetic recoverable payload\n")
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
            moment = moment.replace(hour=12, minute=10 if name.endswith("-a") else 20, second=0)
        stamp = moment.strftime("%Y-%m-%dT%H:%M:%S")
        host.borg("create", "--timestamp", stamp, f"{repo}::{name}", "payload", cwd=backup_root)
    sinex_repositories = []
    for name in ("sinex-core", "sinex-keys"):
        sinex = config.repository(name).path
        host.borg("init", "--encryption=none", str(sinex))
        for suffix, age in (("current", 0), ("old", 400), ("day-a", 30), ("day-b", 30)):
            moment = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=age)
            if suffix.startswith("day-"):
                moment = moment.replace(hour=12, minute=10 if suffix.endswith("a") else 20, second=0)
            host.borg(
                "create",
                "--timestamp",
                moment.strftime("%Y-%m-%dT%H:%M:%S"),
                f"{sinex}::sinex-core-{suffix}",
                "payload",
                cwd=backup_root,
            )
        sinex_repositories.append(sinex)

    def archives(repository=repo):
        return {a["name"] for a in json.loads(host.borg("list", "--json", str(repository)).stdout)["archives"]}

    def maintain(*options):
        assert cli.main(["maintain", *options, "--config", str(config_path)]) == 0

    before = {repository: archives(repository) for repository in [repo, *sinex_repositories]}
    maintain("--dry-run")
    assert all(archives(repository) == names for repository, names in before.items()), "preview changed archives"
    maintain()
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
    restored = host.borg("extract", "--stdout", f"{repo}::realm-current", "payload").stdout
    assert restored == payload.read_text()
    for sinex in sinex_repositories:
        assert archives(sinex) == {"sinex-core-current", "sinex-core-old", "sinex-core-day-b"}, archives(sinex)
        restored = host.borg("extract", "--stdout", f"{sinex}::sinex-core-current", "payload").stdout
        assert restored == payload.read_text()
    marker = Path(config.jobs["maintenance"]["marker"])
    stamp = marker.read_bytes()
    assert stamp.decode().strip().isdigit()
    assert marker.stat().st_mode & 0o777 == 0o600
    runs = sorted(Path(config.jobs["maintenance"]["retention_directory"]).iterdir())
    assert sorted(path.name for path in runs[-1].iterdir()) == [
        "borg-realm-v2.after.json",
        "borg-realm-v2.before.json",
        "borg-sinex-core-v1.after.json",
        "borg-sinex-core-v1.before.json",
        "borg-sinex-keys-v1.after.json",
        "borg-sinex-keys-v1.before.json",
    ]
    maintain()
    assert marker.read_bytes() == stamp, "completed pass should not repeat while not due"
    marker.unlink()
    capfd.readouterr()
    with config.lock_path.open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        maintain()
        assert "remains_due=true" in capfd.readouterr().out
        assert not marker.exists(), "contention falsely marked maintenance complete"
    maintain()
    assert marker.exists(), "maintenance did not retry after contention"
