"""Exercise the generated deploy entrypoint without router access or credentials."""

import os
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
