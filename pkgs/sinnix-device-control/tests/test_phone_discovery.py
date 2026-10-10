"""Exercise the production resolver with reachable, untrusted SSH candidates."""

import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts/sinnix-phone"


def resolve(tmp_path, authentic_host, *, pin=True, override=None):
    binary = tmp_path / "bin"
    binary.mkdir()
    fixtures = {
        "timeout": "exit 0",  # Every candidate has an open port.
        "tailscale": "printf '%s' "
        + shlex.quote(
            json.dumps(
                {
                    "Peer": {
                        "peer": {
                            "Online": True,
                            "OS": "android",
                            "HostName": "Redmi Note 11",
                            "TailscaleIPs": ["198.51.100.66"],
                        }
                    }
                }
            )
        ),
        "ip": "exit 1",  # This fixture has no additional subnet to scan.
        "ssh": r"""printf '%s\n' "$*" >> "$SSH_CALLS"
case " $* " in *" StrictHostKeyChecking=yes "*) ;; *) exit 0 ;; esac
case " $* " in *" HostKeyAlias=sinnix-phone "*) ;; *) exit 255 ;; esac
case " $* " in *" UserKnownHostsFile=$SINNIX_PHONE_STATE_DIR/known_hosts "*) ;; *) exit 255 ;; esac
test -f "$SINNIX_PHONE_STATE_DIR/known_hosts" || exit 255
case " $* " in *" fixture@$AUTHENTIC_HOST "*) exit 0 ;; *) exit 255 ;; esac
""",
    }
    for name, body in fixtures.items():
        path = binary / name
        path.write_text(f"#!{shutil.which('bash')}\n" + body + "\n")
        path.chmod(0o755)
    state = tmp_path / "state"
    state.mkdir()
    (state / "last-host").write_text("198.51.100.42\n")
    if pin:
        (state / "known_hosts").write_text("synthetic enrolled pin\n")
    env = {
        **os.environ,
        "PATH": f"{binary}:{os.environ['PATH']}",
        "HOME": str(tmp_path),
        "SINNIX_PHONE_STATE_DIR": str(state),
        "SINNIX_PHONE_SSH_CONTROL_DIR": str(tmp_path / "control"),
        "SINNIX_PHONE_USER": "fixture",
        "AUTHENTIC_HOST": authentic_host,
        "SSH_CALLS": str(tmp_path / "calls"),
    }
    for key in ("SINNIX_PHONE_IP", "SINNIX_PHONE_KNOWN_HOSTS", "SINNIX_PHONE_MDNS"):
        env.pop(key, None)
    if override:
        env["SINNIX_PHONE_IP"] = override
    prefix = SCRIPT.read_text().split('PHONE_TS_IP="${SINNIX_PHONE_IP:-')[0]
    result = subprocess.run(
        ["bash", "-c", prefix + "\nresolve_phone_host\n"],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result, state, tmp_path / "calls"


@pytest.mark.parametrize("host", ["redmi-note-11.local", "198.51.100.42"])
def test_reachable_impostor_cannot_win_or_poison_address_cache(tmp_path, host):
    result, state, calls = resolve(tmp_path, host)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == host
    assert (state / "last-host").read_text().strip() == host
    assert "fixture@198.51.100.66" in calls.read_text()


@pytest.mark.parametrize("pin", [True, False])
def test_unknown_or_unenrolled_candidates_remain_unavailable(tmp_path, pin):
    result, state, _ = resolve(tmp_path, "not-present", pin=pin)
    assert result.returncode == 1
    assert (state / "last-host").read_text() == "198.51.100.42\n"


def test_explicit_address_override_does_not_enroll_or_probe_candidates(tmp_path):
    result, state, calls = resolve(tmp_path, "not-present", override="198.51.100.77")
    assert result.returncode == 0
    assert result.stdout.strip() == "198.51.100.77"
    assert not calls.exists()
    assert (state / "last-host").read_text() == "198.51.100.42\n"
