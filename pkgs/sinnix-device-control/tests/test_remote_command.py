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
    # The logcat watchdog consults the selected always-on VPN. This fixture
    # has none; it must not execute Android settings on the host shell.
    executable(binary / "settings", "print('null')\n")
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
import os,sys,subprocess,pathlib,shutil,json
args=sys.argv[1:]
if args[:1] == ['-s']: args=args[2:]
if args == ['devices']: print('List of devices attached\\nfixture\\tdevice'); sys.exit(0)
if args == ['shell', 'getprop', 'ro.serialno']: print('fixture'); sys.exit(0)
if args == ['get-state']: print('device'); sys.exit(int(os.environ.get('ADB_STATE_STATUS','0')))
if args[:1] == ['logcat']:
    if '-d' in args:
        payload=pathlib.Path(os.environ['LOGCAT_CAPTURE']).read_bytes()
        if os.environ.get('LOGCAT_ARGS'): pathlib.Path(os.environ['LOGCAT_ARGS']).write_text(json.dumps(args))
        if os.environ.get('LOGCAT_ENFORCE_CURSOR') and '-T' in args and payload and args[args.index('-T')+1] > payload[:23].decode(): payload=b''
        if os.environ.get('LOGCAT_STREAM'):
            while True:
                os.write(1, payload)
        sys.stdout.buffer.write(payload)
        sys.stdout.buffer.flush()
        if os.environ.get('LOGCAT_HANG'):
            import time
            time.sleep(60)
        sys.exit(int(os.environ.get('LOGCAT_STATUS','0')))
    sys.exit(0)
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
        "SINNIX_PHONE_ADB_SERIAL": "fixture",
        "SINNIX_PHONE_SSH_CONTROL_DIR": str(tmp_path / "ssh-cache"),
        "SINNIX_PHONE_LAKE": str(tmp_path / "lake"),
        "SINNIX_PHONE_STATE_DIR": str(tmp_path / "phone-state"),
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
        umask=0,
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
    names = [
        "ambient'; touch sentinel; #.m4a",
        "ambient-雪\n\r.m4a",
        "ambient-back\\slash.m4a",
    ]
    for name in names:
        (root / "remote" / "ambient" / name).write_bytes(b"neutral fixture")
    result = run(device, "sinnix-phone", "pull-ambient")
    assert result.returncode == 0, result.stderr
    for name in names:
        assert (root / "lake" / "ambient" / name).read_bytes() == b"neutral fixture"
    retry = run(device, "sinnix-phone", "pull-ambient")
    assert retry.returncode == 0, retry.stderr
    assert {path.name for path in (root / "lake" / "ambient").iterdir()} == set(names)
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
    metadata = source.with_suffix(".log.txt")
    metadata.write_text("synthetic call metadata\n")
    for _ in range(2):
        result = run(device, "sinnix-phone", "bcr-sync")
        assert result.returncode == 0, result.stderr
    assert (root / "lake" / "calls" / name).read_bytes() == source.read_bytes()
    assert (
        root / "lake" / "calls" / "debug" / metadata.name
    ).read_bytes() == metadata.read_bytes()
    ledger = root / "lake" / "calls" / "levels.jsonl"
    rows = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert len(rows) == 1 and rows[0]["file"] == name
    assert rows[0]["captured_nothing"] is False
    assert not (root / "sentinel").exists()


@pytest.mark.parametrize("existing", [None, b"", b"--------- beginning of main\n"])
@pytest.mark.parametrize(
    "incoming",
    [
        b"",
        b"--------- beginning of system\n",
        b"2026-10-09 00:00:01.123 neutral record\n",
    ],
)
def test_logcat_zero_matches_are_one_numeric_count(device, existing, incoming):
    root, env = device
    capture = root / "logcat-input"
    capture.write_bytes(incoming)
    env["LOGCAT_CAPTURE"] = str(capture)
    day = time.strftime("%Y%m%d", time.gmtime())
    output = root / "lake" / "logcat" / f"logcat-{day}.txt"
    output.parent.mkdir(parents=True)
    if existing is not None:
        output.write_bytes(existing)
    result = run(device, "sinnix-phone", "logcat")
    assert result.returncode == 0, result.stderr
    expected = 1 if incoming.startswith(b"2026-") else 0
    assert f"logcat: {expected} new lines in " in result.stdout
    chunks = list(output.parent.glob("logcat-????????-*.txt"))
    assert len(chunks) == 1
    assert chunks[0].read_bytes() == incoming
    if existing is not None:
        assert output.read_bytes() == existing
    else:
        assert not output.exists()
    cursor = root / "phone-state" / "logcat.cursor"
    if expected:
        assert cursor.read_text().strip() == "2026-10-09 00:00:01.123"
    else:
        assert not cursor.exists()


@pytest.mark.parametrize(
    "incoming", [b"", b"2026-10-09 00:00:02.123 incomplete record",
                 b"2026-10-09 00:00:02.123 complete record\npartial"]
)
def test_failed_logcat_pull_preserves_bytes_and_cursor_and_still_checks_bcr(
    device, incoming
):
    root, env = device
    capture = root / "logcat-input"
    capture.write_bytes(incoming)
    env.update(LOGCAT_CAPTURE=str(capture), LOGCAT_STATUS="1")
    day = time.strftime("%Y%m%d", time.gmtime())
    output = root / "lake" / "logcat" / f"logcat-{day}.txt"
    output.parent.mkdir(parents=True)
    original = b"2026-10-09 00:00:01.123 previous complete record\n"
    output.write_bytes(original)
    cursor = root / "phone-state" / "logcat.cursor"
    cursor.parent.mkdir()
    cursor.write_text("2026-10-09 00:00:01.123\n")
    result = run(device, "sinnix-phone", "logcat")
    assert result.returncode != 0
    assert "pull failed" in result.stderr
    assert "bcr: synced" in result.stdout
    assert output.read_bytes() == original
    assert cursor.read_text() == "2026-10-09 00:00:01.123\n"
    pending = list(output.parent.glob(".logcat-pull.*"))
    assert len(pending) == bool(incoming)
    if incoming:
        assert pending[0].read_bytes() == incoming
        assert pending[0].stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("previous", ["2099-01-01 00:00:00.000", "invalid timestamp"])
def test_invalid_or_future_logcat_cursor_requests_full_dump(device, previous):
    root, env = device
    capture = root / "logcat-input"
    incoming = b"2026-10-09 00:00:01.123 complete record\n"
    capture.write_bytes(incoming)
    args = root / "logcat-args.json"
    env.update(
        LOGCAT_CAPTURE=str(capture), LOGCAT_ENFORCE_CURSOR="1", LOGCAT_ARGS=str(args)
    )
    cursor = root / "phone-state" / "logcat.cursor"
    cursor.parent.mkdir()
    cursor.write_text(previous + "\n")
    result = run(device, "sinnix-phone", "logcat")
    assert result.returncode == 0, result.stderr
    assert "-T" not in json.loads(args.read_text())
    assert cursor.read_text().strip() == "2026-10-09 00:00:01.123"
    output = next((root / "lake" / "logcat").glob("logcat-*.txt"))
    assert output.read_bytes() == incoming
    assert output.stat().st_mode & 0o777 == 0o600
    assert not list(output.parent.glob(".logcat-pull.*"))


def test_logcat_without_transport_is_not_success(device):
    _, env = device
    env["ADB_STATE_STATUS"] = "1"
    result = run(device, "sinnix-phone", "logcat")
    assert result.returncode != 0
    assert "no adb transport" in result.stdout


@pytest.mark.parametrize(
    "status,maximum,expected",
    [(1, "-1.0", None), (0, "", None), (0, "-91.0", True), (0, "-10.0", False)],
)
def test_ambient_audit_distinguishes_failed_unknown_silent_and_sound(
    device, status, maximum, expected
):
    root, env = device
    ambient = root / "lake" / "ambient"
    ambient.mkdir(parents=True)
    (ambient / "neutral.m4a").write_bytes(b"neutral audio fixture")
    executable(root / "bin" / "ffprobe", "print('3600')")
    executable(
        root / "bin" / "ffmpeg",
        f"import sys\nprint('mean_volume: -20.0 dB', file=sys.stderr)\nprint('max_volume: {maximum} dB', file=sys.stderr)\nsys.exit({status})",
    )
    result = run(device, "sinnix-phone", "ambient-audit")
    assert result.returncode == 0, result.stderr
    row = json.loads((root / "lake" / "ambient-levels.jsonl").read_text())
    assert row["decode_ok"] is (status == 0)
    assert row["captured_nothing"] is expected
    assert row["sha256"] == hashlib.sha256(b"neutral audio fixture").hexdigest()
    if expected is None:
        assert (
            "1 unknown" in result.stdout
            and "0 hours in sound-bearing chunks" in result.stdout
        )


def test_ambient_audit_revises_legacy_and_same_size_replacements(device):
    root, env = device
    ambient = root / "lake" / "ambient"
    ambient.mkdir(parents=True)
    capture = ambient / "neutral.m4a"
    capture.write_bytes(b"first")
    ledger = root / "lake" / "ambient-levels.jsonl"
    original = '{"chunk":"neutral.m4a","bytes":5,"captured_nothing":false}\n'
    ledger.write_text(original)
    executable(root / "bin" / "ffprobe", "print('3600')")
    executable(
        root / "bin" / "ffmpeg",
        "import sys\nprint('mean_volume: -20.0 dB\\nmax_volume: -10.0 dB', file=sys.stderr)",
    )
    assert run(device, "sinnix-phone", "ambient-audit").returncode == 0
    assert ledger.read_text().startswith(original)
    assert len(ledger.read_text().splitlines()) == 2
    assert run(device, "sinnix-phone", "ambient-audit").returncode == 0
    assert len(ledger.read_text().splitlines()) == 2
    capture.write_bytes(b"other")
    assert run(device, "sinnix-phone", "ambient-audit").returncode == 0
    rows = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert len(rows) == 3 and rows[-1]["sha256"] != rows[-2]["sha256"]


def test_ambient_audit_missing_source_is_not_empty(device):
    root, _ = device
    result = run(device, "sinnix-phone", "ambient-audit")
    assert result.returncode != 0 and "source unavailable" in result.stderr
    assert not (root / "lake" / "ambient").exists()


@pytest.mark.parametrize("bound", ["bytes", "timeout"])
def test_logcat_bounded_stream_publishes_and_resumes(device, bound):
    root, env = device
    payload = b"2026-10-09 00:00:02.123  100  200 E NoisyTag: repeated error\n"
    capture = root / "logcat-input"
    capture.write_bytes(payload)
    args = root / "logcat-args.json"
    env.update(LOGCAT_CAPTURE=str(capture), LOGCAT_ARGS=str(args))
    if bound == "bytes":
        env.update(LOGCAT_STREAM="1", SINNIX_LOGCAT_MAX_BYTES=str(len(payload) * 4 + 9))
    else:
        env.update(LOGCAT_HANG="1", SINNIX_LOGCAT_TIMEOUT_SECONDS="0.3")
    started = time.monotonic()
    result = run(device, "sinnix-phone", "logcat")
    assert result.returncode == 0, result.stderr
    assert time.monotonic() - started < 10
    directory = root / "lake" / "logcat"
    chunks = list(directory.glob("logcat-*.txt"))
    assert len(chunks) == 1
    expected = payload * 4 + payload[:9] if bound == "bytes" else payload
    assert chunks[0].read_bytes() == expected
    metadata = json.loads(chunks[0].with_suffix(".json").read_text())
    assert metadata["reason"] == ("byte-cap" if bound == "bytes" else "timeout")
    assert metadata["top_tag"] == "NoisyTag"
    assert "top repeated tag: NoisyTag" in result.stderr
    assert (root / "phone-state" / "logcat.cursor").read_text().strip() == "2026-10-09 00:00:02.123"
    assert not list(directory.glob(".logcat-pull.*"))
    env.pop("LOGCAT_STREAM", None)
    env.pop("LOGCAT_HANG", None)
    result = run(device, "sinnix-phone", "logcat")
    assert result.returncode == 0, result.stderr
    arguments = json.loads(args.read_text())
    assert arguments[arguments.index("-T") + 1] == "2026-10-09 00:00:02.123"
    assert len(list(directory.glob("logcat-*.txt"))) == 2


def test_logcat_publication_renames_the_pull_inode(device):
    root, env = device
    capture = root / "logcat-input"
    capture.write_bytes(b"2026-10-09 00:00:01.123  100  200 I Neutral: normal\n")
    env.update(LOGCAT_CAPTURE=str(capture))
    # Record the inode from the writer's open descriptor before publication.
    adb = root / "bin" / "adb"
    source = adb.read_text().replace(
        "payload=pathlib.Path(os.environ['LOGCAT_CAPTURE']).read_bytes()",
        """payload=pathlib.Path(os.environ['LOGCAT_CAPTURE']).read_bytes()
        stages=list((pathlib.Path(os.environ['FIXTURE_ROOT'])/'lake'/'logcat').glob('.logcat-pull.*'))
        pathlib.Path(os.environ['FIXTURE_ROOT'],'pull-inode').write_text(str(stages[0].stat().st_ino))""",
    )
    adb.write_text(source)
    result = run(device, "sinnix-phone", "logcat")
    assert result.returncode == 0, result.stderr
    chunk = next((root / "lake" / "logcat").glob("logcat-*.txt"))
    assert chunk.stat().st_ino == int((root / "pull-inode").read_text())
    assert chunk.read_bytes() == capture.read_bytes()


def test_logcat_long_complete_line_advances_but_partial_does_not(device):
    root, env = device
    complete = b"2026-10-09 00:00:02.123  100  200 I Neutral: " + b"x" * 70000 + b"\n"
    incoming = complete + b"2026-10-09 00:00:03.123 partial"
    capture = root / "logcat-input"
    capture.write_bytes(incoming)
    env.update(LOGCAT_CAPTURE=str(capture))
    directory = root / "lake" / "logcat"
    directory.mkdir(parents=True)
    old_stage = directory / ".logcat-pull.legacy"
    old_stage.write_bytes(b"existing recovery evidence")
    result = run(device, "sinnix-phone", "logcat")
    assert result.returncode == 0, result.stderr
    assert "logcat: 1 new lines" in result.stdout
    assert next(directory.glob("logcat-*.txt")).read_bytes() == incoming
    assert (root / "phone-state" / "logcat.cursor").read_text().strip() == "2026-10-09 00:00:02.123"
    assert old_stage.read_bytes() == b"existing recovery evidence"
