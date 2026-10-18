"""Exercise the generated deploy entrypoint without router access or credentials."""

import os
import json
import re
import runpy
import subprocess
import sys
from pathlib import Path

executable, config, helper = sys.argv[1:]
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
for name, value in [("wifi", "synthetic-password"), ("mac", "02:00:00:00:00:01"),
                    ("key", "ssh-ed25519 AAAAsynthetic fixture")]:
    (root / name).write_text(value)
mock = root / "transport"
mock.write_text(f"#!{sys.executable}\n" + r"""
import io, json, os, sys, tarfile
from pathlib import Path
with open(os.environ["ROUTER_FIXTURE_LOG"], "a") as stream:
    stream.write(json.dumps(sys.argv) + "\n")
if Path(sys.argv[0]).name == "ssh":
    if sys.argv[-1] == "sh /tmp/health-check.sh":
        sys.exit(int(os.environ.get("ROUTER_FIXTURE_HEALTH", "0")))
    if "tar czf" in sys.argv[-1]:
        sys.exit(int(os.environ.get("ROUTER_FIXTURE_BACKUP", "0")))
else:
    if ":/tmp/sinnix-gw-backup.tar.gz" in sys.argv[-2]:
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
""")
mock.chmod(0o700)
for name in ["ssh", "scp"]:
    (root / name).symlink_to(mock)
body = Path(executable).read_text()
body = re.sub(r"/nix/store/[^/]+/bin/(ssh|scp)\b", lambda m: str(root / m[1]), body)
for original, name in [("wifi-psk", "wifi"), ("router-sinnix-prime-mac", "mac"),
                       ("router-authorized-key", "key")]:
    body = body.replace("/run/agenix/" + original, str(root / name))
entry = root / "deploy"
entry.write_text(body)
entry.chmod(0o700)
for name, overrides, expected in [
    ("healthy", {}, 0),
    ("unhealthy", {"ROUTER_FIXTURE_HEALTH": "1"}, 1),
    ("disconnected", {"ROUTER_FIXTURE_HEALTH": "255"}, 255),
    ("backup-failed", {"ROUTER_FIXTURE_BACKUP": "1"}, 1),
    ("copy-failed", {"ROUTER_FIXTURE_COPY": "fail"}, 1),
    ("invalid-backup", {"ROUTER_FIXTURE_COPY": "invalid"}, None),
]:
    home = root / name
    home.mkdir(mode=0o700)
    log = home / "transport.jsonl"
    result = subprocess.run([str(entry)], env=os.environ | {
        "HOME": str(home), "ROUTER_FIXTURE_LOG": str(log), **overrides,
    }, capture_output=True, text=True)
    if expected is None:
        assert result.returncode != 0, name
    else:
        assert result.returncode == expected, (name, result.returncode, result.stderr)
    assert ("deployment complete!" in result.stdout) == (expected == 0), name
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    if "backup" in name or name == "copy-failed":
        assert not any(call[-1] == "sh /tmp/configure.sh" for call in calls), name
    else:
        assert any(call[-1] == "rm -f /tmp/install-packages.sh /tmp/configure.sh /tmp/health-check.sh" for call in calls), name
        backups = list((home / ".cache/sinnix-gw-backups").iterdir())
        assert len(backups) == 1
        assert backups[0].stat().st_mode & 0o777 == 0o600
        assert backups[0].parent.stat().st_mode & 0o777 == 0o700
print("router backup preconditions, private preimages and health-result controls passed")
