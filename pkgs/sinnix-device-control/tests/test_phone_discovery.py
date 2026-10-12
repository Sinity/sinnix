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


def run_command(tmp_path, command, *, adb_mode='usb', override=None):
    binary = tmp_path / 'bin'
    binary.mkdir()
    peers = json.dumps({'Peer': {'fixture': {'Online': True, 'OS': 'android',
                       'HostName': 'Redmi Note 11', 'TailscaleIPs': ['198.51.100.66']}}})
    fixtures = {
        'tailscale': 'printf %s ' + shlex.quote(peers),
        'timeout': 'printf "%s\\n" "$*" >> "$PROBE_CALLS"; exit 1',
        'ip': 'printf "LAN\\n" >> "$PROBE_CALLS"; exit 1',
        'ssh': 'printf "%s\\n" "$*" >> "$SSH_CALLS"; exit 0',
        'sinnix-phone-dispatcher': 'printf \'{"state":"missing"}\\n\'',
        'adb': r'''printf '%s %s\n' "${ANDROID_SERIAL:-none}" "$*" >> "$ADB_CALLS"
case "$1" in
 get-state) [ "$ADB_MODE" = tailnet ] || [ "${ANDROID_SERIAL:-}" = phone-fixture ] || { [ "$ADB_MODE" = cached ] && [ "${ANDROID_SERIAL:-}" = 198.51.100.42:5555 ]; } ;;
 devices)
  printf 'List of devices attached\n'
  case "$ADB_MODE" in
   usb) printf 'phone-fixture\tdevice\n' ;;
   multiple) printf 'phone-fixture\tdevice\nquest-fixture\tdevice\n' ;;
  esac ;;
 connect) exit 1 ;;
 *) exit 0 ;;
esac
''',
    }
    for name, body in fixtures.items():
        path = binary / name
        path.write_text(f"#!{shutil.which('bash')}\n" + body + '\n')
        path.chmod(0o755)
    env = {**os.environ, 'PATH': f"{binary}:{os.environ['PATH']}",
           'SINNIX_PHONE_STATE_DIR': str(tmp_path / 'state'),
           'SINNIX_PHONE_SSH_CONTROL_DIR': str(tmp_path / 'control'),
           'SINNIX_PHONE_LAKE': str(tmp_path / 'lake'),
           'ADB_MODE': adb_mode, 'ADB_CALLS': str(tmp_path / 'adb-calls'),
           'SSH_CALLS': str(tmp_path / 'ssh-calls'), 'PROBE_CALLS': str(tmp_path / 'probes')}
    env.pop('SINNIX_PHONE_IP', None)
    env.pop('ADB_RESOLVED', None)
    if override:
        env['SINNIX_PHONE_IP'] = override
    (tmp_path / 'state').mkdir()
    (tmp_path / 'state/last-host').write_text('198.51.100.42')
    result = subprocess.run(['bash', str(SCRIPT), *command], env=env,
                            capture_output=True, text=True, timeout=10)
    return result


@pytest.mark.parametrize('mode', ['usb', 'tailnet', 'absent'])
def test_adb_status_does_not_probe_ssh_or_lan(tmp_path, mode):
    result = run_command(tmp_path, ['app-status'], adb_mode=mode)
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / 'ssh-calls').exists()
    probes = (tmp_path / 'probes').read_text() if (tmp_path / 'probes').exists() else ''
    assert 'LAN' not in probes and '/dev/tcp' not in probes
    if mode == 'usb':
        assert 'phone-fixture shell pm list packages' in (tmp_path / 'adb-calls').read_text()
    if mode == 'absent':
        assert 'capture and upload state unavailable' in result.stdout


def test_multiple_usb_devices_are_not_selected_arbitrarily(tmp_path):
    result = run_command(tmp_path, ['app-status'], adb_mode='multiple')
    assert result.returncode == 0
    assert 'capture and upload state unavailable' in result.stdout
    assert 'shell pm list' not in (tmp_path / 'adb-calls').read_text()


def test_ssh_command_keeps_explicit_routing_and_strict_identity(tmp_path):
    result = run_command(tmp_path, ['shell', 'true'], override='198.51.100.77')
    assert result.returncode == 0, result.stderr
    calls = (tmp_path / 'ssh-calls').read_text()
    assert '@198.51.100.77' in calls and 'StrictHostKeyChecking=yes' in calls
    assert not (tmp_path / 'probes').exists()


def test_help_does_not_probe_any_transport(tmp_path):
    result = run_command(tmp_path, ['--help'])
    assert result.returncode == 0
    assert 'sinnix-phone <command>' in result.stdout
    assert not (tmp_path / 'ssh-calls').exists()
    assert not (tmp_path / 'adb-calls').exists()
    assert not (tmp_path / 'probes').exists()


def test_known_lan_adb_route_does_not_require_ssh(tmp_path):
    result = run_command(tmp_path, ['app-status'], adb_mode='cached')
    assert result.returncode == 0, result.stderr
    assert '198.51.100.42:5555 shell pm list packages' in (tmp_path / 'adb-calls').read_text()
    assert not (tmp_path / 'ssh-calls').exists()
    assert '/dev/tcp' not in (tmp_path / 'probes').read_text()
