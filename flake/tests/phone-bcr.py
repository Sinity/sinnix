"""Exercise BCR intake with real decoding and a controlled ADB transport."""

import hashlib
import fcntl
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

source = Path(sys.argv[1]).read_text()
function = source[
    source.index("drain_bcr_calls_adb() (") : source.index("nix_userland_identity() {")
]
builder = source[
    source.index("adb_shell_args() {") : source.index("# The grants the app needs")
]
mock = r"""
sinnix-remote-command() { python3 "$BCR_ENCODER" "$@"; }
adb_resolve() { return 0; }
mv() {
  local target="${@: -1}"
  if [ "$BCR_MODE" = "second-publish-failed" ] && [[ "$target" == */debug/* ]]; then
    printf 'concurrent archive writer' > "$LAKE_ROOT/calls/neutral call.oga"
    return 1
  fi
  command mv "$@"
}
adb_any() {
  case "$1" in
    pull)
      source="$BCR_REMOTE_ROOT/${2#"$BCR_REMOTE_PREFIX"/}"
      if [ "$BCR_MODE" = "failed" ]; then printf cut > "$3"; return 1; fi
      cp -- "$source" "$3"
      ;;
    shell)
      shift
      [ "$1" = -T ] && shift
      command=${1//"$BCR_REMOTE_PREFIX"/$BCR_REMOTE_ROOT}
      if [ "$BCR_MODE" = "inventory-failed" ] && [[ "$command" == find* ]]; then return 1; fi
      if [ "$BCR_MODE" = "bad-stat" ] && [[ "$command" == stat* ]]; then echo malformed; return 0; fi
      if [[ "$command" == *sha256sum* ]]; then printf x >> "$BCR_HASH_LOG"; fi
      if [[ "$command" == find* ]]; then
        bash -c "$command" | python3 -c 'import os,sys; b=sys.stdin.buffer.read(); sys.stdout.buffer.write(b.replace(os.environ["BCR_REMOTE_ROOT"].encode(), os.environ["BCR_REMOTE_PREFIX"].encode()))'
        return
      fi
      if [ "$BCR_MODE" = "stdin-consuming" ] && [[ "$command" == test* ]]; then
        cat >/dev/null
      fi
      bash -c "$command"
      ;;
    *) return 1 ;;
  esac
}
"""
with tempfile.TemporaryDirectory() as scratch:
    root = Path(scratch)
    remote_root = root / "remote"
    remote_root.mkdir()
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
            "-b:a",
            "64k",
            "-vbr",
            "off",
            str(remote_root / "neutral call.oga"),
        ],
        check=True,
    )
    alternate_audio = root / "alternate.oga"
    third_audio = root / "third.oga"
    for frequency, output in ((660, alternate_audio), (880, third_audio)):
        subprocess.run(
            ["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
             f"sine=frequency={frequency}:duration=0.2", "-c:a", "libopus",
             "-b:a", "64k", "-vbr", "off", str(output)],
            check=True,
        )
    assert len(alternate_audio.read_bytes()) == (remote_root / "neutral call.oga").stat().st_size
    assert len(third_audio.read_bytes()) == (remote_root / "neutral call.oga").stat().st_size
    sidecar = remote_root / "neutral call.log.txt"
    sidecar.write_bytes(b"neutral synthetic BCR metadata v1\n")
    old = int(__import__("time").time()) - 180
    for path in (remote_root / "neutral call.oga", sidecar):
        os.utime(path, (old, old))
    harness = (
        "set -euo pipefail\n" + mock + builder + function + "\ndrain_bcr_calls_adb\n"
    )

    def run(mode, lake):
        return subprocess.run(
            ["bash", "-c", harness],
            env={
                **os.environ,
                "BCR_MODE": mode,
                "BCR_REMOTE_ROOT": str(remote_root),
                "BCR_REMOTE_PREFIX": "/sdcard/Android/data/com.chiller3.bcr/files",
                "LAKE_ROOT": str(lake),
                "BCR_ENCODER": sys.argv[2],
                "BCR_HASH_LOG": str(root / "remote-hashes"),
            },
            capture_output=True,
            text=True,
        )

    # ADB shell forwards stdin unless it is detached. A metadata existence
    # check must not consume the remaining NUL-delimited inventory.
    second_audio = remote_root / "second neutral call.oga"
    second_sidecar = remote_root / "second neutral call.log.txt"
    second_audio.write_bytes((remote_root / "neutral call.oga").read_bytes())
    second_sidecar.write_bytes(sidecar.read_bytes())
    for path in (second_audio, second_sidecar):
        os.utime(path, (old, old))
    multiple = root / "multiple"
    result = run("stdin-consuming", multiple)
    assert result.returncode == 0, result.stderr + result.stdout
    multi_ledger = multiple / "calls" / "levels.jsonl"
    assert len(multi_ledger.read_text().splitlines()) == 2, result.stdout
    assert (multiple / "calls" / second_audio.name).read_bytes() == second_audio.read_bytes()
    assert (multiple / "calls" / "debug" / second_sidecar.name).read_bytes() == second_sidecar.read_bytes()
    hashes_before = (root / "remote-hashes").stat().st_size
    result = run("stdin-consuming", multiple)
    assert result.returncode == 0, result.stderr + result.stdout
    assert len(multi_ledger.read_text().splitlines()) == 2
    assert (root / "remote-hashes").stat().st_size == hashes_before
    second_audio.unlink()
    second_sidecar.unlink()

    # A second writer must refuse before loading or mutating call receipts.
    locked_lake = root / "locked-lake"
    (locked_lake / "calls").mkdir(parents=True)
    with (locked_lake / "calls" / ".sync.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        hashes_before = (root / "remote-hashes").stat().st_size
        result = run("normal", locked_lake)
        assert result.returncode == 75, result.stderr + result.stdout
        assert "sync already active" in result.stderr
        assert not (locked_lake / "calls" / "levels.jsonl").exists()
        assert (root / "remote-hashes").stat().st_size == hashes_before
    result = run("normal", locked_lake)
    assert result.returncode == 0, result.stderr + result.stdout
    assert len((locked_lake / "calls" / "levels.jsonl").read_text().splitlines()) == 1

    lake = root / "lake"
    result = run("normal", lake)
    assert result.returncode == 0, result.stderr + result.stdout
    archive = lake / "calls" / "neutral call.oga"
    assert archive.read_bytes() == (remote_root / "neutral call.oga").read_bytes()
    archived_sidecar = lake / "calls" / "debug" / "neutral call.log.txt"
    assert archived_sidecar.read_bytes() == sidecar.read_bytes()
    ledger = lake / "calls" / "levels.jsonl"
    row = json.loads(ledger.read_text())
    assert row["duration_seconds"] > 0 and row["captured_nothing"] is False
    assert row["audio_revision"]["source_sha256"] == row["audio_revision"]["archive_sha256"]
    assert row["sidecar_revision"]["source_sha256"] == row["sidecar_revision"]["archive_sha256"]
    hashes_before = (root / "remote-hashes").stat().st_size
    result = run("normal", lake)
    assert result.returncode == 0 and len(ledger.read_text().splitlines()) == 1
    assert (root / "remote-hashes").stat().st_size == hashes_before

    # Same-name/same-size in-place updates with restored mtime are caught via
    # ctime and retained as exact preimages, including independent sidecars.
    audio = remote_root / "neutral call.oga"
    audio_stat = audio.stat()
    old_audio = audio.read_bytes()
    replacement_audio = alternate_audio.read_bytes()
    audio.write_bytes(replacement_audio)
    os.utime(audio, ns=(audio_stat.st_atime_ns, audio_stat.st_mtime_ns))
    assert audio.stat().st_size == audio_stat.st_size and audio.stat().st_mtime_ns == audio_stat.st_mtime_ns
    assert audio.stat().st_ctime_ns != audio_stat.st_ctime_ns
    sidecar_stat = sidecar.stat()
    old_sidecar = sidecar.read_bytes()
    sidecar.write_bytes(b"neutral synthetic BCR metadata v2\n")
    os.utime(sidecar, ns=(sidecar_stat.st_atime_ns, sidecar_stat.st_mtime_ns))
    result = run("normal", lake)
    assert result.returncode == 0, result.stderr + result.stdout
    assert archive.read_bytes() == replacement_audio and archived_sidecar.read_bytes() == sidecar.read_bytes()
    latest = json.loads(ledger.read_text().splitlines()[-1])
    assert latest["audio_revision"]["source_sha256"] != row["audio_revision"]["source_sha256"]
    assert latest["sidecar_revision"]["source_sha256"] != row["sidecar_revision"]["source_sha256"]
    assert latest["previous_audio"] and latest["previous_sidecar"]
    assert (lake / "calls" / latest["previous_audio"]["history_path"]).read_bytes() == old_audio
    assert (lake / "calls" / latest["previous_sidecar"]["history_path"]).read_bytes() == old_sidecar
    stable_count = len(ledger.read_text().splitlines())
    result = run("normal", lake)
    assert result.returncode == 0 and len(ledger.read_text().splitlines()) == stable_count

    # Failure publishing the sidecar after publishing audio rolls audio back.
    before_audio = archive.read_bytes()
    before_sidecar = archived_sidecar.read_bytes()
    before = ledger.read_bytes()
    audio.write_bytes(third_audio.read_bytes())
    os.utime(audio, ns=(audio.stat().st_atime_ns, audio_stat.st_mtime_ns))
    sidecar.write_bytes(b"neutral synthetic BCR metadata v3\n")
    result = run("second-publish-failed", lake)
    assert result.returncode != 0, result.stderr + result.stdout
    concurrent_audio = b"concurrent archive writer"
    assert archive.read_bytes() == concurrent_audio, result.stderr + result.stdout
    prior_path = lake / "calls" / "history" / hashlib.sha256(before_audio).hexdigest() / archive.name
    assert prior_path.read_bytes() == before_audio
    assert archived_sidecar.read_bytes() == before_sidecar
    assert ledger.read_bytes() == before

    # A cut retry keeps the prior pair intact and creates no successful row.
    result = run("failed", lake)
    assert result.returncode != 0
    assert archive.read_bytes() == concurrent_audio and archived_sidecar.read_bytes() == before_sidecar
    assert ledger.read_bytes() == before
    assert not list((lake / "calls").glob(".audio-incoming.*"))
    result = run("normal", lake)
    assert result.returncode == 0 and archive.read_bytes() == audio.read_bytes()
    latest_after_retry = json.loads(ledger.read_text().splitlines()[-1])
    assert (lake / "calls" / latest_after_retry["previous_audio"]["history_path"]).read_bytes() == concurrent_audio
    assert prior_path.read_bytes() == before_audio

    before = ledger.read_bytes()
    result = run("bad-stat", lake)
    assert result.returncode != 0 and ledger.read_bytes() == before
    result = run("inventory-failed", lake)
    assert result.returncode != 0
    # Legacy rows are upgraded by hashing once; exact matching bytes need no pull.
    legacy = root / "legacy"
    (legacy / "calls" / "debug").mkdir(parents=True)
    (legacy / "calls" / "neutral call.oga").write_bytes(audio.read_bytes())
    (legacy / "calls" / "debug" / "neutral call.log.txt").write_bytes(sidecar.read_bytes())
    (legacy / "calls" / "levels.jsonl").write_text('{"file":"neutral call.oga","bytes":1933}\n')
    result = run("normal", legacy)
    assert result.returncode == 0, result.stderr + result.stdout
    upgraded = json.loads((legacy / "calls" / "levels.jsonl").read_text().splitlines()[-1])
    assert upgraded["audio_revision"]["source_sha256"] == upgraded["audio_revision"]["archive_sha256"]
    assert upgraded["sidecar_revision"]["source_sha256"] == upgraded["sidecar_revision"]["archive_sha256"]
    # Invalid audio must not be cached as successfully audited.
    (remote_root / "neutral call.oga").write_bytes(b"invalid audio")
    os.utime(remote_root / "neutral call.oga", (old, old))
    good_audio_before = archive.read_bytes()
    good_sidecar_before = archived_sidecar.read_bytes()
    good_ledger_before = ledger.read_bytes()
    result = run("normal", lake)
    assert result.returncode != 0
    assert archive.read_bytes() == good_audio_before and archived_sidecar.read_bytes() == good_sidecar_before
    assert ledger.read_bytes() == good_ledger_before
    broken = root / "broken"
    result = run("normal", broken)
    assert result.returncode != 0, result.stderr + result.stdout
    assert (broken / "calls" / "levels.jsonl").read_text() == ""
print(
    "BCR intake: real decode, repeat, cut transfer, recovery, inventory and corrupt audio passed"
)

# Transport selection must follow changing TLS ports and ignore other devices.
resolver = source[source.index("adb_resolve() {"):source.index("\nadb_any() {")]
transport_mock = r"""
timeout() { shift; "$@"; }
adb() {
  case "$1" in
    devices) printf 'List of devices attached\nother-device\tdevice\n' ;;
    connect) printf '%s\n' "$2" >> "$CONNECT_LOG" ;;
    -s)
      case "$3" in
        get-state) [ "$2" = other-device ] ;;
        shell)
          case "$2" in
            other-device) echo other-serial ;;
            192.0.2.5:45678) echo enrolled ;;
            *) return 1 ;;
          esac ;;
      esac ;;
  esac
}
avahi-browse() {
  printf '%s\n' '=;eth0;IPv4;adb-other-random;_adb-tls-connect._tcp;local;other.local;192.0.2.6;44444;'
  [ "$DISCOVERY" != missing ] || return 0
  printf '%s\n' '=;eth0;IPv4;adb-enrolled-random;_adb-tls-connect._tcp;local;phone.local;192.0.2.5;45678;'
}
"""
with tempfile.TemporaryDirectory() as scratch:
    log = Path(scratch) / "connections"
    for mode in ("available", "missing"):
        result = subprocess.run(["bash", "-c", "set -euo pipefail\nADB_RESOLVED=''\n" + transport_mock + resolver + "\nadb_resolve\nprintf '%s' \"$ADB_RESOLVED\""], env={**os.environ, "SINNIX_PHONE_ADB_SERIAL":"enrolled", "DISCOVERY":mode, "CONNECT_LOG":str(log)}, capture_output=True, text=True)
        if mode == "available":
            assert result.returncode == 0, result.stderr
            assert result.stdout == "192.0.2.5:45678"
            assert log.read_text().splitlines() == ["192.0.2.5:45678"]
        else:
            assert result.returncode != 0
            assert "unavailable" in result.stderr
print("Wireless ADB: changing TLS endpoint, enrolled serial, wrong device and unavailable discovery passed")

restore = source.split("adb-restore)\n", 1)[1].split("  ;;\nclip-push)", 1)[0]
result = subprocess.run(["bash", "-c", "set -euo pipefail\nadb() { return 0; }\ninstall_wireless_adb_boot() { echo boot-installed; }\nset -- --persistent\n" + restore], env={**os.environ,"SINNIX_PHONE_ADB_SERIAL":"enrolled"}, capture_output=True, text=True)
assert result.returncode == 0, result.stderr
assert "boot-installed" in result.stdout

# Ambient recovery must qualify bytes rather than infer identity from length.
ambient = source[source.index("drain_ambient_adb() {"):source.index("# Preserve and audit BCR call recordings.")]
ambient_mock = r'''
sinnix-remote-command() { python3 "$BCR_ENCODER" "$@"; }
adb_resolve() { return 0; }
adb_any() {
  case "$1" in
    pull)
      case "$AMBIENT_MODE" in
        failed) printf cut > "$3"; return 1 ;;
        truncated) printf cut > "$3" ;;
        changed) cp "$BCR_FIXTURE" "$3"; printf changed > "$BCR_FIXTURE" ;;
        *) cp "$BCR_FIXTURE" "$3" ;;
      esac
      ;;
    shell)
      shift
      if [ "$1" = -T ]; then shift; fi
      case "$1" in
        find*) printf '%s\0' '/sdcard/sinnix-ambient/neutral chunk.m4a' ;;
        sha256sum*)
          [ "$AMBIENT_MODE" != unavailable ] || return 1
          sha256sum "$BCR_FIXTURE" ;;
        *) return 1 ;;
      esac
      ;;
    *) return 1 ;;
  esac
}
'''
with tempfile.TemporaryDirectory() as scratch:
    root = Path(scratch)
    fixture = root / "payload"
    fixture.write_bytes(b"verified neutral fixture")
    lake = root / "lake"
    harness = "set -euo pipefail\n" + ambient_mock + builder + ambient + "\ndrain_ambient_adb\n"

    def run_ambient(mode):
        fixture.write_bytes(b"verified neutral fixture")
        return subprocess.run(["bash", "-c", harness], capture_output=True, text=True,
                              env={**os.environ, "AMBIENT_MODE": mode, "BCR_FIXTURE": str(fixture),
                                   "BCR_ENCODER": sys.argv[2], "LAKE_ROOT": str(lake)})

    result = run_ambient("normal")
    assert result.returncode == 0, result.stdout + result.stderr
    target = lake / "ambient" / "neutral chunk.m4a"
    assert target.read_bytes() == fixture.read_bytes()
    # Same length is not continuity. Preserve both versions; retries are stable.
    original = b"X" * fixture.stat().st_size
    target.write_bytes(original)
    result = run_ambient("normal")
    assert result.returncode == 0, result.stdout + result.stderr
    versions = list(target.parent.glob("*.conflict-*"))
    assert len(versions) == 1 and versions[0].read_bytes() == fixture.read_bytes()
    assert target.read_bytes() == original
    result = run_ambient("normal")
    assert result.returncode == 0 and len(list(target.parent.glob("*.conflict-*"))) == 1
    for mode in ["failed", "truncated", "unavailable", "changed"]:
        result = run_ambient(mode)
        assert result.returncode != 0
        assert target.read_bytes() == original
        assert any(p.read_bytes() == b"cut" for p in target.parent.glob(".incoming.*"))
    outside = root / "outside"
    outside.write_bytes(b"unrelated")
    target.unlink()
    target.symlink_to(outside)
    result = run_ambient("normal")
    assert result.returncode == 0 and outside.read_bytes() == b"unrelated"

    # A directory at the conflict destination must never receive a nested link.
    versions[0].unlink()
    versions[0].mkdir()
    result = run_ambient("normal")
    assert result.returncode != 0 and not list(versions[0].iterdir())
    assert outside.read_bytes() == b"unrelated"
