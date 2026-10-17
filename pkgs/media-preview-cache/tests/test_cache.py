"""Exercise disposable thumbnail staging and actual warm failure propagation."""

import hashlib
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts/media-preview-cache"


@pytest.fixture
def cache(tmp_path):
    binary = tmp_path / "bin"
    binary.mkdir()
    tool = binary / "ffmpegthumbnailer"
    tool.write_text(
        f"#!{sys.executable}\n"
        + """
import os, pathlib, sys, time
args = sys.argv[1:]
source = pathlib.Path(args[args.index('-i') + 1])
output = pathlib.Path(args[args.index('-o') + 1])
mode = os.environ['THUMBNAIL_MODE']
output.write_bytes(b'' if mode == 'empty' else b'fixture thumbnail')
(pathlib.Path(os.environ['CALLS']) / source.name).touch()
if mode == 'wait':
    time.sleep(30)
sys.exit(7 if mode == 'fail' else 0)
"""
    )
    tool.chmod(0o755)
    calls = tmp_path / "calls"
    calls.mkdir()
    videos = tmp_path / "videos"
    videos.mkdir()
    for name in ("first.mp4", "second.mp4"):
        (videos / name).write_bytes(b"synthetic source")
    env = {
        "PATH": f"{binary}:{os.environ['PATH']}",
        "HOME": str(tmp_path),
        "XDG_CACHE_HOME": str(tmp_path / "cache"),
        "THUMBNAIL_MODE": "success",
        "CALLS": str(calls),
        "MEDIA_PREVIEW_JOBS": "2",
    }
    return tmp_path, videos, calls, env


def run(cache, *args, mode="success"):
    root, _videos, _calls, env = cache
    result = subprocess.run(
        ["bash", str(SCRIPT), *map(str, args)],
        env={**env, "THUMBNAIL_MODE": mode},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert not list((root / "cache").rglob("*.tmp.*")), "disposable staging file leaked"
    return result


def test_generator_failure_removes_partial_stage_and_preserves_source(cache):
    _root, videos, _calls, _env = cache
    source = videos / "first.mp4"
    result = run(cache, "ensure", source, mode="fail")
    assert result.returncode == 7
    assert not result.stdout
    assert source.read_bytes() == b"synthetic source"


def test_empty_generator_output_is_not_published(cache):
    _root, videos, _calls, _env = cache
    result = run(cache, "ensure", videos / "first.mp4", mode="empty")
    assert result.returncode != 0
    assert not result.stdout


def test_successful_cached_result_is_reused_without_generator(cache):
    _root, videos, calls, _env = cache
    first = run(cache, "ensure", videos / "first.mp4")
    assert first.returncode == 0, first.stderr
    output = Path(first.stdout.strip())
    before = (output.read_bytes(), output.stat().st_ino, output.stat().st_mtime_ns)
    (calls / "first.mp4").unlink()
    second = run(cache, "ensure", videos / "first.mp4", mode="fail")
    assert second.returncode == 0 and second.stdout == first.stdout
    assert not list(calls.iterdir())
    assert (
        output.read_bytes(),
        output.stat().st_ino,
        output.stat().st_mtime_ns,
    ) == before


@pytest.mark.parametrize("mode", ["fail", "success"])
def test_warm_attempts_all_files_and_reports_failure(cache, mode):
    _root, videos, calls, _env = cache
    result = run(cache, "warm", videos, mode=mode)
    assert (result.returncode == 0) == (mode == "success")
    assert {p.name for p in calls.iterdir()} == {"first.mp4", "second.mp4"}


def test_terminated_generation_removes_disposable_stage(cache):
    root, videos, calls, env = cache
    proc = subprocess.Popen(
        ["bash", str(SCRIPT), "ensure", str(videos / "first.mp4")],
        env={**env, "THUMBNAIL_MODE": "wait"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        deadline = time.monotonic() + 5
        while not (calls / "first.mp4").exists():
            assert proc.poll() is None, (
                "generator exited before cancellation fixture was ready"
            )
            assert time.monotonic() < deadline, (
                "generator never entered its staging phase"
            )
            time.sleep(0.01)
        os.killpg(proc.pid, signal.SIGTERM)
        proc.communicate(timeout=5)
        assert proc.returncode != 0
        assert not list((root / "cache").rglob("*.tmp.*"))
    finally:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.communicate(timeout=5)


def test_trailing_newline_filename_has_distinct_identity(cache):
    _root, videos, calls, _env = cache
    ordinary = videos / "first.mp4"
    newline = videos / "first.mp4\n"
    newline.write_bytes(b"different synthetic source")
    first = run(cache, "thumb-path", ordinary)
    second = run(cache, "thumb-path", newline)
    assert first.returncode == second.returncode == 0
    assert first.stdout != second.stdout
    generated = run(cache, "ensure", newline)
    assert generated.returncode == 0, generated.stderr
    assert {p.name for p in calls.iterdir()} == {"first.mp4\n"}


def test_warm_preserves_trailing_newline_directory(cache):
    _root, videos, calls, _env = cache
    renamed = videos.with_name("videos\n")
    videos.rename(renamed)
    result = run(cache, "warm", renamed)
    assert result.returncode == 0, result.stderr
    assert {p.name for p in calls.iterdir()} == {"first.mp4", "second.mp4"}


def test_ordinary_paths_retain_existing_cache_keys(cache):
    _root, videos, _calls, env = cache
    source = videos / "first.mp4"
    metadata = source.stat()
    data = f"{source.resolve()}\t{metadata.st_size}\t{int(metadata.st_mtime)}\t{int(metadata.st_ctime)}\t10\n"
    digest = hashlib.sha256(data.encode()).hexdigest()
    expected = (
        Path(env["XDG_CACHE_HOME"])
        / "media-preview-cache/v1/video"
        / digest[:2]
        / f"{digest}.jpg"
    )
    result = run(cache, "thumb-path", source)
    assert result.returncode == 0
    assert result.stdout == str(expected) + "\n"


def test_missing_input_does_not_invoke_generator(cache):
    _root, videos, calls, _env = cache
    result = run(cache, "ensure", videos / "absent.mp4")
    assert result.returncode != 0
    assert not result.stdout
    assert not list(calls.iterdir())
