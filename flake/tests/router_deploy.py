"""Exercise the generated deploy entrypoint without router access or credentials."""

import json
import os
import re
import runpy
import shutil
import subprocess
import sys
from pathlib import Path

executable, config, helper, health = sys.argv[1:]
# A preview must work before staging or reading any secret.
env = os.environ | {"TMPDIR": str(Path.cwd() / "uncreated-scratch")}
for flag in ["--dry-run", "-n"]:
    result = subprocess.run([executable, flag], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    for script in ["install-packages.sh", "configure.sh", "health-check.sh"]:
        assert (Path(config) / script).read_text() in result.stdout
    for marker in ["@@WIFI_PSK@@", "@@SINNIX_PRIME_MAC@@", "@@ROUTER_AUTHORIZED_KEY@@"]:
        assert marker in result.stdout
    assert not Path(env["TMPDIR"]).exists()
for flag in ["--dryrun", "--dry-run=1"]:
    result = subprocess.run([executable, flag], env=env, capture_output=True, text=True)
    assert result.returncode == 64, result.stderr
    assert "Unknown option" in result.stderr
result = subprocess.run([executable, "--help"], env=env, capture_output=True, text=True)
assert result.returncode == 0 and "Usage:" in result.stdout
# In the Nix sandbox credentials are absent; deployment must stop before SSH.
assert not Path("/run/agenix/wifi-psk").exists()
result = subprocess.run([executable], capture_output=True, text=True)
assert result.returncode == 66, result.stderr
assert "WiFi PSK is missing" in result.stderr

# Validate the real template and injector using only neutral synthetic inputs.
inject = runpy.run_path(helper)["inject"]
wifi = "synthetic'&|$()\\`@@ROUTER_AUTHORIZED_KEY@@"
key = 'ssh-ed25519 AAAAsynthetic comment"$()`\\'
secrets = [Path("wifi"), Path("mac"), Path("key")]
for path, value in zip(secrets, [wifi, "02:00:00:00:00:01", key], strict=True):
    path.write_text(value)
template = (Path(config) / "configure.sh").read_text()
script = Path("configure.sh")
script.write_text(template)
inject(script, *secrets)
assert script.stat().st_mode & 0o777 == 0o600
subprocess.run(["bash", "-n", str(script)], check=True)
uci = [line for line in script.read_text().splitlines() if ".key=" in line]
assert len(uci) == 3
for line in uci:
    value = subprocess.check_output(
        ["bash", "-c", line.replace("uci set", "printf '%s'", 1)], text=True
    )
    assert value.split("=", 1)[1] == wifi
key_lines = [
    line.strip()
    for line in script.read_text().splitlines()
    if line.strip().startswith('echo "ssh-')
]
assert len(key_lines) == 1
value = subprocess.check_output(
    ["bash", "-c", key_lines[0].split(" >> ")[0]], text=True
)
assert value.rstrip("\n") == key
script.write_text(template)
secrets[1].write_text("invalid")
try:
    inject(script, *secrets)
except ValueError:
    pass
else:
    raise AssertionError("invalid MAC accepted")
assert script.read_text() == template
secrets[1].write_text("02:00:00:00:00:01")
for secret in secrets:
    saved = secret.read_text()
    secret.unlink()
    try:
        inject(script, *secrets)
    except ValueError:
        pass
    else:
        raise AssertionError("missing secret accepted")
    finally:
        secret.write_text(saved)
    assert script.read_text() == template
script.write_text(template.replace("@@WIFI_PSK@@", "missing", 1))
saved = script.read_text()
try:
    inject(script, *secrets)
except ValueError:
    pass
else:
    raise AssertionError("changed template accepted")
assert script.read_text() == saved
print("router preview, argument and missing-secret controls passed")

# Run the real rendered entrypoint with only SSH/SCP and credentials relocated.
# No connection, real secret or router mutation is permitted by this fixture.
root = Path.cwd() / "deploy-controls"
root.mkdir(mode=0o700)
for name, value in [
    ("wifi", "synthetic-password"),
    ("mac", "02:00:00:00:00:01"),
    ("key", "ssh-ed25519 AAAAsynthetic fixture"),
]:
    (root / name).write_text(value)
mock = root / "transport"
mock.write_text(
    f"#!{sys.executable}\n"
    + r"""
import io, json, os, shlex, shutil, subprocess, sys, tarfile
from pathlib import Path
record = Path(os.environ["HOME"]) / "stage.txt"
with open(os.environ["ROUTER_FIXTURE_LOG"], "a") as stream:
    stream.write(json.dumps(sys.argv) + "\n")
if Path(sys.argv[0]).name == "ssh":
    command = sys.argv[-1]
    if command == "umask 077; mktemp -d /tmp/sinnix-gw.XXXXXX":
        if os.environ.get("ROUTER_FIXTURE_STAGE") == "invalid":
            print("/tmp/sinnix-gw.bad;false")
        elif os.environ.get("ROUTER_FIXTURE_STAGE") == "fail":
            sys.exit(1)
        else:
            stage = subprocess.check_output(["mktemp", "-d", "/tmp/sinnix-gw.XXXXXX"], text=True).strip()
            assert Path(stage).stat().st_mode & 0o777 == 0o700
            record.write_text(stage)
            print(stage)
    elif command.startswith("sh "):
        path = Path(shlex.split(command)[1])
        assert path.parent == Path(record.read_text())
        assert path.is_file()
        if path.name == "health-check.sh":
            sys.exit(int(os.environ.get("ROUTER_FIXTURE_HEALTH", "0")))
    elif "tar czf" in command:
        assert record.read_text() + "/backup.tar.gz" in command
        sys.exit(int(os.environ.get("ROUTER_FIXTURE_BACKUP", "0")))
    elif command.startswith("rm -rf "):
        path = Path(shlex.split(command)[2])
        assert path == Path(record.read_text())
        if os.environ.get("ROUTER_FIXTURE_CLEANUP") == "fail":
            sys.exit(1)
        shutil.rmtree(path)
else:
    if sys.argv[-2].endswith("/backup.tar.gz"):
        if os.environ.get("ROUTER_FIXTURE_COPY") == "fail":
            sys.exit(1)
        target = Path(sys.argv[-1])
        if os.environ.get("ROUTER_FIXTURE_COPY") == "invalid":
            target.write_text("not an archive")
        else:
            with tarfile.open(target, "w:gz") as archive:
                info = tarfile.TarInfo("etc/config/dhcp")
                info.size = 7
                archive.addfile(info, io.BytesIO(b"fixture"))
    else:
        stage = Path(sys.argv[-1].split(":", 1)[1])
        assert stage == Path(record.read_text())
        for source in sys.argv[1:-1]:
            if Path(source).is_file():
                shutil.copyfile(source, stage / Path(source).name)
"""
)
mock.chmod(0o700)
for name in ["ssh", "scp"]:
    (root / name).symlink_to(mock)


def relocate(program):
    body = Path(program).read_text()
    body = re.sub(r"/nix/store/[^/]+/bin/(ssh|scp)\b", lambda m: str(root / m[1]), body)
    for original, name in [
        ("wifi-psk", "wifi"),
        ("router-sinnix-prime-mac", "mac"),
        ("router-authorized-key", "key"),
    ]:
        body = body.replace("/run/agenix/" + original, str(root / name))
    entry = root / Path(program).name
    entry.write_text(body)
    entry.chmod(0o700)
    return entry


entry = relocate(executable)
health_entry = relocate(health)
stages = []
for name, overrides, expected, command in [
    ("healthy", {}, 0, entry),
    ("unhealthy", {"ROUTER_FIXTURE_HEALTH": "1"}, 1, entry),
    ("disconnected", {"ROUTER_FIXTURE_HEALTH": "255"}, 255, entry),
    ("backup-failed", {"ROUTER_FIXTURE_BACKUP": "1"}, 1, entry),
    ("copy-failed", {"ROUTER_FIXTURE_COPY": "fail"}, 1, entry),
    ("invalid-backup", {"ROUTER_FIXTURE_COPY": "invalid"}, None, entry),
    ("cleanup-failed", {"ROUTER_FIXTURE_CLEANUP": "fail"}, 1, entry),
    ("invalid-stage", {"ROUTER_FIXTURE_STAGE": "invalid"}, 1, entry),
    ("stage-failed", {"ROUTER_FIXTURE_STAGE": "fail"}, 1, entry),
    ("health-only", {}, 0, health_entry),
    ("health-only-failed", {"ROUTER_FIXTURE_HEALTH": "255"}, 255, health_entry),
]:
    home = root / name
    home.mkdir(mode=0o700)
    log = home / "transport.jsonl"
    result = subprocess.run(
        [str(command)],
        env=os.environ
        | {
            "HOME": str(home),
            "ROUTER_FIXTURE_LOG": str(log),
            **overrides,
        },
        capture_output=True,
        text=True,
    )
    if expected is None:
        assert result.returncode != 0, name
    else:
        assert result.returncode == expected, (name, result.returncode, result.stderr)
    assert ("deployment complete!" in result.stdout) == (
        expected == 0 and command == entry
    ), name
    assert "/tmp/health-check.sh" not in result.stderr, name
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    if "backup" in name or name == "copy-failed" or "stage" in name:
        assert not any(call[-1].startswith("sh ") for call in calls), name
    record = home / "stage.txt"
    if record.exists():
        stage = Path(record.read_text())
        stages.append(stage)
        assert stage.exists() == (name == "cleanup-failed"), name
        if stage.exists():
            shutil.rmtree(stage)  # Only this fixture's allocated, recorded directory.
    if command == entry and name in ["healthy", "unhealthy", "disconnected"]:
        backups = list((home / ".cache/sinnix-gw-backups").iterdir())
        assert len(backups) == 1
        assert backups[0].stat().st_mode & 0o777 == 0o600
        assert backups[0].parent.stat().st_mode & 0o777 == 0o700
assert len(stages) == len(set(stages))
print("router backup, private staging, cleanup and health-result controls passed")
