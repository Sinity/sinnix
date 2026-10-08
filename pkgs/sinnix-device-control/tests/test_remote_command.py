"""Exercise the production scripts and the SSH/ADB joined-command parser.

Every transport is replaced; the remote POSIX shell sees only scratch files.
This deliberately parses the joined command, rather than trusting local argv.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"


def executable(path: Path, body: str) -> None:
    path.write_text(f"#!{sys.executable}\n" + body)
    path.chmod(0o755)


@pytest.fixture
def device(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    binary = tmp_path / "bin"
    binary.mkdir()
    remote = tmp_path / "remote"
    for child in ("Videoshots", "ambient", "bcr", "exports"):
        (remote / child).mkdir(parents=True)
    executable(
        binary / "wl-paste",
        """
import os,sys,pathlib
if '--list-types' in sys.argv: print('text/plain')
else: sys.stdout.buffer.write(pathlib.Path(os.environ['CLIPBOARD']).read_bytes())
""",
    )
    executable(
        binary / "termux-clipboard-set",
        """
import os,sys,json,pathlib
pathlib.Path(os.environ['CAPTURE']).write_text(json.dumps(sys.argv[1:]))
""",
    )
    executable(binary / "getprop", "print('Quest 3')\n")
    executable(binary / "pm", "print('package:com.termux.nix uid:2000')\n")
    executable(
        binary / "ls", "import os; print(os.environ['FIXTURE_CONTEXT']+' neutral')\n"
    )
    executable(
        binary / "su",
        """
import os,sys,subprocess
index=sys.argv.index('-c')
assert index+2 == len(sys.argv)
sys.exit(subprocess.run([os.environ['REMOTE_SHELL'],'-c',sys.argv[index+1]]).returncode)
""",
    )
    executable(
        binary / "chcon",
        """
import os,sys,json,pathlib
pathlib.Path(os.environ['LABEL_CAPTURE']).write_text(json.dumps(sys.argv[1:]))
""",
    )
    executable(
        binary / "login",
        """
import os,sys,json,pathlib
if sys.argv[1] == 'nix-on-droid':
    pathlib.Path(os.environ['CAPTURE']).write_text(json.dumps(sys.argv[1:]))
else: print('neutral nvim fixture')
""",
    )
    executable(
        binary / "run.sh",
        """
import os,sys,json,pathlib
pathlib.Path(os.environ['CAPTURE']).write_text(json.dumps(sys.argv[1:]))
""",
    )
    find_program = shutil.which("find")
    assert find_program
    executable(
        binary / "find",
        f"""
import os,sys,subprocess
if sys.argv[1].startswith('/data/data/com.termux.nix/'):
    sys.stdout.buffer.write(b'neutral-file\\0')
else: sys.exit(subprocess.run([{find_program!r},*sys.argv[1:]]).returncode)
""",
    )
    executable(
        binary / "ssh",
        """
import os,sys,subprocess
host=sys.argv.index('fixture@fixture')
command=' '.join(sys.argv[host+1:])
if command == 'test -r /sdcard/sinnix-ambient': sys.exit(1)
sys.exit(subprocess.run([os.environ['REMOTE_SHELL'],'-c',command]).returncode)
""",
    )
    executable(
        binary / "adb",
        """
import os,sys,subprocess,pathlib,shutil
args=sys.argv[1:]
if args[:1] == ['-s']: args=args[2:]
if args == ['get-state']: print('device'); sys.exit(0)
mapping={'/sdcard/Oculus/Videoshots':str(pathlib.Path(os.environ['REMOTE'])/'Videoshots'),
         '/sdcard/sinnix-ambient':str(pathlib.Path(os.environ['REMOTE'])/'ambient'),
         '/sdcard/Android/data/com.chiller3.bcr/files':str(pathlib.Path(os.environ['REMOTE'])/'bcr'),
         '/sdcard/sinnix-calls':str(pathlib.Path(os.environ['REMOTE'])/'exports')}
def mapped(value):
    for source,target in mapping.items(): value=value.replace(source,target)
    for source,name in [('/system/bin/ls','ls'),('/system/bin/find','find'),
                        ('/data/data/com.termux.nix/files/usr/bin/login','login'),
                        ('/data/adb/modules/sinnix_debian_chroot/run.sh','run.sh')]:
        value=value.replace(source,str(pathlib.Path(os.environ['FIXTURE_ROOT'])/'bin'/name))
    return value
if args[:1] == ['shell']:
    args=args[1:]
    if args[:1] in (['-T'],['-t']): args=args[1:]
    command=mapped(' '.join(args))
    if os.environ.get('FAIL_INVENTORY') and command.startswith('find '):
        sys.stdout.buffer.write(b'1|/sdcard/Oculus/Videoshots/partial.mp4\\0')
        sys.exit(1)
    result=subprocess.run([os.environ['REMOTE_SHELL'],'-c',command],capture_output=True)
    output=result.stdout
    for source,target in mapping.items(): output=output.replace(os.fsencode(target),os.fsencode(source))
    sys.stdout.buffer.write(output); sys.stderr.buffer.write(result.stderr)
    sys.exit(result.returncode)
if args[:1] == ['pull']:
    shutil.copyfile(mapped(args[1]),args[2]); sys.exit(0)
raise SystemExit('unexpected fixture ADB call: '+repr(args))
""",
    )
    # Even an accidental parser regression cannot remove a file outside scratch.
    executable(
        binary / "rm",
        """
import os,sys,pathlib
root=pathlib.Path(os.environ['FIXTURE_ROOT']).resolve()
for value in sys.argv[1:]:
    if value in ('-f','--'): continue
    path=pathlib.Path(value); path.resolve().relative_to(root)
    path.unlink(missing_ok=True)
""",
    )
    clipboard = tmp_path / "clipboard"
    clipboard.write_bytes(b"")
    env = {
        **os.environ,
        "PATH": f"{binary}:{SCRIPTS}:{os.environ['PATH']}",
        "HOME": str(tmp_path),
        "TMPDIR": str(tmp_path),
        "FIXTURE_ROOT": str(tmp_path),
        "REMOTE": str(remote),
        "REMOTE_SHELL": shutil.which("dash") or shutil.which("sh") or "sh",
        "CLIPBOARD": str(clipboard),
        "CAPTURE": str(tmp_path / "capture.json"),
        "LABEL_CAPTURE": str(tmp_path / "labels.json"),
        "FIXTURE_CONTEXT": "u:object_r:app_data_file:s0:c1$(touch${IFS}sentinel)",
        "SINNIX_PHONE_IP": "fixture",
        "SINNIX_PHONE_USER": "fixture",
        "SINNIX_PHONE_SSH_CONTROL_DIR": str(tmp_path / "ssh-cache"),
        "SINNIX_PHONE_LAKE": str(tmp_path / "lake"),
        "SINNIX_QUEST_TRANSPORT": "usb",
        "SINNIX_QUEST_SERIAL": "fixture",
        "SINNIX_QUEST_STATE_DIR": str(tmp_path / "quest-state"),
        "SINNIX_QUEST_MEDIA_DIR": str(tmp_path / "media"),
        "SINNIX_QUEST_ARCHIVE_DIR": str(tmp_path / "archive"),
        "SINNIX_QUEST_BACKUP_MARKER": str(tmp_path / "receipt"),
    }
    return tmp_path, env


def run(
    device: tuple[Path, dict[str, str]], script: str, *args: str
) -> subprocess.CompletedProcess[str]:
    root, env = device
    return subprocess.run(
        ["bash", str(SCRIPTS / script), *args],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )


@pytest.mark.parametrize(
    "value",
    [
        b"",
        b"\n",
        b"text\n\n",
        b"-leading",
        "雪 'quotes' \"double\" \\ | $HOME\r\n".encode(),
        b"literal; touch sentinel; #",
        b"$(touch sentinel)",
    ],
)
def test_clipboard_crosses_the_remote_parser_literally(device, value: bytes) -> None:
    root, _env = device
    (root / "clipboard").write_bytes(value)
    result = run(device, "sinnix-phone", "clip-push")
    assert result.returncode == 0, result.stderr
    assert json.loads((root / "capture.json").read_text()) == ["--", value.decode()]
    assert not (root / "sentinel").exists()


def test_clipboard_nul_refuses_before_remote_effect(device) -> None:
    root, _env = device
    (root / "clipboard").write_bytes(b"before\0after")
    result = run(device, "sinnix-phone", "clip-push")
    assert result.returncode != 0 and "NUL" in result.stderr
    assert not (root / "capture.json").exists()


@pytest.mark.parametrize(
    "name",
    ["neutral; touch sentinel; #.mp4", "neutral'雪\n\r|\\name.mp4", "-leading.mp4"],
)
def test_quest_pull_archive_and_prune_preserve_filenames(device, name: str) -> None:
    root, _env = device
    source = root / "remote" / "Videoshots" / name
    payload = b"neutral fixture bytes"
    source.write_bytes(payload)
    os.utime(source, (time.time() - 50 * 86400,) * 2)
    result = run(
        device, "sinnix-quest", "media", "pull", f"/sdcard/Oculus/Videoshots/{name}"
    )
    assert result.returncode == 0, result.stderr
    assert (root / "media" / name).read_bytes() == payload
    result = run(device, "sinnix-quest", "media", "archive", str(root / "media" / name))
    assert result.returncode == 0, result.stderr
    archive = root / "archive" / f"{hashlib.sha256(payload).hexdigest()}-{name}"
    assert archive.read_bytes() == payload
    os.utime(archive, (time.time() - 86400,) * 2)
    (root / "receipt").write_text("neutral fixture receipt")
    result = run(device, "sinnix-quest", "media", "prune")
    assert result.returncode == 0 and source.exists(), result.stderr
    result = run(device, "sinnix-quest", "media", "prune", "--apply")
    assert result.returncode == 0 and not source.exists(), result.stderr
    assert archive.read_bytes() == payload
    assert not (root / "sentinel").exists()


def test_partial_failed_inventory_never_reaches_pruning(device) -> None:
    root, env = device
    (root / "archive").mkdir()
    (root / "receipt").write_text("neutral fixture receipt")
    env["FAIL_INVENTORY"] = "1"
    result = run(device, "sinnix-quest", "media", "prune", "--apply")
    assert result.returncode != 0 and "inventory failed" in result.stderr
    assert not (root / "sentinel").exists()


def test_prune_refuses_a_corrupt_content_addressed_archive(device) -> None:
    root, _env = device
    payload = b"neutral original"
    source = root / "remote" / "Videoshots" / "neutral.mp4"
    source.write_bytes(payload)
    os.utime(source, (time.time() - 50 * 86400,) * 2)
    archive = root / "archive" / f"{hashlib.sha256(payload).hexdigest()}-neutral.mp4"
    archive.parent.mkdir()
    archive.write_bytes(b"corrupt archive")
    os.utime(archive, (time.time() - 86400,) * 2)
    (root / "receipt").write_text("neutral fixture receipt")
    result = run(device, "sinnix-quest", "media", "prune", "--apply")
    assert result.returncode == 0 and "archive hash mismatch" in result.stdout
    assert source.read_bytes() == payload


def test_ambient_drain_preserves_remote_names(device) -> None:
    root, _env = device
    names = ["ambient'; touch sentinel; #.m4a", "ambient-雪\n\r.m4a"]
    for name in names:
        (root / "remote" / "ambient" / name).write_bytes(b"neutral fixture")
    result = run(device, "sinnix-phone", "pull-ambient")
    assert result.returncode == 0, result.stderr
    for name in names:
        assert (root / "lake" / "ambient" / name).read_bytes() == b"neutral fixture"
    assert not (root / "sentinel").exists()


def test_privileged_phone_routes_keep_both_shell_layers_literal(device) -> None:
    root, env = device
    flake = "github:neutral/fixture#phone; touch sentinel; #\n雪"
    result = run(device, "sinnix-phone", "nix-switch", flake)
    assert result.returncode == 0, result.stderr
    assert json.loads((root / "capture.json").read_text()) == [
        "nix-on-droid",
        "switch",
        "--flake",
        flake,
    ]
    assert json.loads((root / "labels.json").read_text()) == [
        "-h",
        env["FIXTURE_CONTEXT"],
        "neutral-file",
    ]
    values = ["-leading", "", "literal; touch sentinel; #", "雪\n\n"]
    result = run(device, "sinnix-phone", "chroot", *values)
    assert result.returncode == 0, result.stderr
    assert json.loads((root / "capture.json").read_text()) == values
    assert not (root / "sentinel").exists()


def test_bcr_literal_filename_is_audited_only_once(device) -> None:
    root, _env = device
    name = "neutral'雪\n\r;$(touch sentinel).oga"
    source = root / "remote" / "bcr" / name
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=0.2",
            "-c:a",
            "libopus",
            str(source),
        ],
        check=True,
    )
    os.utime(source, (time.time() - 120,) * 2)
    for _ in range(2):
        result = run(device, "sinnix-phone", "bcr-sync")
        assert result.returncode == 0, result.stderr
    assert (root / "lake" / "calls" / name).read_bytes() == source.read_bytes()
    ledger = root / "lake" / "calls" / "levels.jsonl"
    rows = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert len(rows) == 1 and rows[0]["file"] == name
    assert rows[0]["captured_nothing"] is False
    assert not (root / "sentinel").exists()
