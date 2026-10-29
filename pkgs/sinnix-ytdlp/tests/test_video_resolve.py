import fcntl
import json
import os
import selectors
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


def test_default_reader_pins_generation_during_replacement(tmp_path):
    scripts = Path(__file__).parents[3] / "scripts"
    state = tmp_path / "state"
    state.mkdir()
    root = tmp_path / "derived"
    pointers = []
    retained = tmp_path / "retained-first"
    for name in ("first", "second"):
        (state / "urls.jsonl").write_text(
            json.dumps(
                {
                    "url": f"https://youtu.be/{name}",
                    "visits": ["2026-01-01T00:00:00Z"],
                    "visit_count": 1,
                }
            )
            + "\n"
        )
        build = subprocess.run(
            [
                sys.executable,
                str(scripts / "sinnix-url-ledger"),
                "build",
                "--state-root",
                str(state),
                "--derived-root",
                str(root),
            ],
            capture_output=True,
            text=True,
        )
        assert build.returncode == 0, build.stderr
        pointers.append((root / "current.json").read_bytes())
        if name == "first":
            first_generation = json.loads(pointers[0])["generation"]
            shutil.copytree(root / "generations" / first_generation, retained)
    # The publisher retires previous generations. Keep this fixture's first
    # payload available so the test isolates pointer selection during a swap.
    shutil.copytree(
        retained, root / "generations" / first_generation, dirs_exist_ok=True
    )
    (root / "current.json").write_bytes(pointers[0])
    replacement = tmp_path / "replacement.json"
    replacement.write_bytes(pointers[1])
    bindir = tmp_path / "bin"
    bindir.mkdir()
    receipt = tmp_path / "downloads"
    calls = tmp_path / "selections"
    shell = shutil.which("bash")
    helper = bindir / "sinnix-url-ledger"
    helper.write_text(
        f"#!{sys.executable}\n"
        "import os, subprocess, sys\n"
        f"selected = subprocess.run([sys.executable, {str(scripts / 'sinnix-url-ledger')!r}, *sys.argv[1:]], capture_output=True, text=True, check=True)\n"
        "with open(os.environ['SELECTION_RECEIPT'], 'a') as f: f.write('selected\\n')\n"
        "os.replace(os.environ['REPLACEMENT_POINTER'], os.environ['SINNIX_URL_LEDGER_ROOT'] + '/current.json')\n"
        "print(selected.stdout, end='')\n"
    )
    helper.chmod(0o700)
    downloader = bindir / "sinnix-ytdlp"
    downloader.write_text(
        f'#!{shell}\nprintf "%s\\n" "${{@: -1}}" >> "$DOWNLOAD_RECEIPT"\n'
    )
    downloader.chmod(0o700)
    env = {
        **os.environ,
        "PATH": f"{bindir}:{os.environ['PATH']}",
        "SINNIX_URL_LEDGER_ROOT": str(root),
        "SINNIX_VIDEO_ARCHIVE_ROOT": str(tmp_path / "archive"),
        "DOWNLOAD_RECEIPT": str(receipt),
        "SELECTION_RECEIPT": str(calls),
        "REPLACEMENT_POINTER": str(replacement),
    }
    env.pop("SINNIX_URL_LEDGER_PARQUET", None)
    result = subprocess.run(
        [shell, str(scripts / "sinnix-video-resolve")],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert receipt.read_text().splitlines() == ["https://youtu.be/first"]
    assert calls.read_text().splitlines() == ["selected"]
    assert (root / "current.json").read_bytes() == pointers[1]


@pytest.fixture
def resolver(tmp_path):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    shell = shutil.which("bash")
    for name, body in {
        "duckdb": 'printf "%s" "$QUERY_OUTPUT"; exit "$QUERY_EXIT"',
        "sinnix-ytdlp": 'printf "%s\\n" "${@: -1}" >> "$DOWNLOAD_RECEIPT"',
    }.items():
        executable = bindir / name
        executable.write_text(f"#!{shell}\n{body}\n")
        executable.chmod(0o700)
    ledger = tmp_path / "ledger.parquet"
    ledger.write_bytes(b"neutral fixture")
    archive = tmp_path / "archive"
    receipt = tmp_path / "download-receipt"
    env = {
        **os.environ,
        "PATH": f"{bindir}:{os.environ['PATH']}",
        "SINNIX_URL_LEDGER_PARQUET": str(ledger),
        "SINNIX_VIDEO_ARCHIVE_ROOT": str(archive),
        "DOWNLOAD_RECEIPT": str(receipt),
    }

    def run(output="", status=0):
        return subprocess.run(
            [shell, str(Path(__file__).parents[3] / "scripts/sinnix-video-resolve")],
            env={**env, "QUERY_OUTPUT": output, "QUERY_EXIT": str(status)},
            capture_output=True,
            text=True,
            umask=0o022,
        )

    return run, archive, receipt


def test_query_failure_is_not_an_empty_success(resolver):
    run, archive, receipt = resolver
    result = run(status=42)
    assert result.returncode != 0
    assert "ledger query failed" in result.stderr
    assert "0 candidate" not in result.stderr
    assert not archive.exists()
    assert not receipt.exists()


def test_empty_query_is_a_success_without_downloads(resolver):
    run, archive, receipt = resolver
    result = run()
    assert result.returncode == 0
    assert "0 candidate" in result.stderr
    assert not receipt.exists()
    assert archive.stat().st_mode & 0o777 == 0o700
    assert (archive / ".tried-urls").stat().st_mode & 0o777 == 0o600


def test_urls_and_private_attempt_history_are_preserved(resolver):
    run, archive, receipt = resolver
    urls = ["https://example.invalid/watch?a=one,two", "https://example.invalid/second"]
    result = run("\n".join(urls) + "\n")
    assert result.returncode == 0
    assert receipt.read_text().splitlines() == urls
    history = archive / ".tried-urls"
    assert history.read_text().splitlines() == urls
    assert history.stat().st_mode & 0o777 == 0o600


def test_real_ledger_filename_can_contain_an_apostrophe(tmp_path):
    """The actual SQL parser must accept an ordinary quoted filename."""
    ledger = tmp_path / "owner's ledger.parquet"
    literal = "'" + str(ledger).replace("'", "''") + "'"
    duckdb = shutil.which("duckdb")
    assert duckdb is not None
    subprocess.run(
        [
            duckdb,
            "-c",
            "COPY (SELECT 'https://youtu.be/fixture' AS normalized_url, "
            f"1 AS visit_count) TO {literal} (FORMAT PARQUET)",
        ],
        check=True,
        capture_output=True,
    )
    bindir = tmp_path / "bin"
    bindir.mkdir()
    shell = shutil.which("bash")
    receipt = tmp_path / "download-receipt"
    downloader = bindir / "sinnix-ytdlp"
    downloader.write_text(
        f'#!{shell}\nprintf "%s\\n" "${{@: -1}}" >> "$DOWNLOAD_RECEIPT"\n'
    )
    downloader.chmod(0o700)
    result = subprocess.run(
        [shell, str(Path(__file__).parents[3] / "scripts/sinnix-video-resolve")],
        env={
            **os.environ,
            "PATH": f"{bindir}:{os.environ['PATH']}",
            "SINNIX_URL_LEDGER_PARQUET": str(ledger),
            "SINNIX_VIDEO_ARCHIVE_ROOT": str(tmp_path / "archive"),
            "DOWNLOAD_RECEIPT": str(receipt),
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert receipt.read_text().splitlines() == ["https://youtu.be/fixture"]


def test_real_publisher_waits_for_selected_reader_then_retires(tmp_path):
    """A selected generation lives until DuckDB closes, then GC may retire it."""
    scripts = Path(__file__).parents[3] / "scripts"
    ledger = scripts / "sinnix-url-ledger"
    duckdb = shutil.which("duckdb")
    shell = shutil.which("bash")
    state, root, bindir = (tmp_path / name for name in ("state", "derived", "bin"))
    state.mkdir()
    bindir.mkdir()

    def input_url(name):
        (state / "urls.jsonl").write_text(
            json.dumps(
                {
                    "url": f"https://youtu.be/{name}",
                    "visits": ["2026-01-01T00:00:00Z"],
                    "visit_count": 1,
                }
            )
            + "\n"
        )

    build = [
        sys.executable,
        str(ledger),
        "build",
        "--state-root",
        str(state),
        "--derived-root",
        str(root),
        "--duckdb-bin",
        duckdb,
    ]
    input_url("first")
    first = subprocess.run(build, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    pointer = json.loads((root / "current.json").read_text())
    first_generation = root / "generations" / pointer["generation"]
    input_url("second")
    ready, release = tmp_path / "ready", tmp_path / "release"
    os.mkfifo(ready)
    os.mkfifo(release)
    ready_r = os.open(ready, os.O_RDWR | os.O_NONBLOCK)
    release_w = os.open(release, os.O_RDWR | os.O_NONBLOCK)
    helper = bindir / "duckdb"
    helper.write_text(
        f"#!{sys.executable}\nimport os, sys\n"
        "with open(os.environ['READER_READY'], 'wb', buffering=0) as f: f.write(b'Q')\n"
        "with open(os.environ['READER_RELEASE'], 'rb', buffering=0) as f: assert f.read(1) == b'R'\n"
        f"os.execv({duckdb!r}, [{duckdb!r}, *sys.argv[1:]])\n"
    )
    helper.chmod(0o700)
    helper = bindir / "sinnix-url-ledger"
    helper.write_text(f'#!{shell}\nexec {sys.executable} {ledger} "$@"\n')
    helper.chmod(0o700)
    receipt = tmp_path / "downloads"
    helper = bindir / "sinnix-ytdlp"
    helper.write_text(
        f'#!{shell}\nprintf "%s\\n" "${{@: -1}}" >> "$DOWNLOAD_RECEIPT"\n'
    )
    helper.chmod(0o700)
    env = {
        **os.environ,
        "PATH": f"{bindir}:{os.environ['PATH']}",
        "SINNIX_URL_LEDGER_ROOT": str(root),
        "SINNIX_VIDEO_ARCHIVE_ROOT": str(tmp_path / "archive"),
        "DOWNLOAD_RECEIPT": str(receipt),
        "READER_READY": str(ready),
        "READER_RELEASE": str(release),
    }
    env.pop("SINNIX_URL_LEDGER_PARQUET", None)
    reader = subprocess.Popen(
        [shell, str(scripts / "sinnix-video-resolve")],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    writer = None
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(ready_r, selectors.EVENT_READ)
            assert selector.select(15), (
                "reader never reached selected-generation DuckDB extraction"
            )
        assert os.read(ready_r, 1) == b"Q"
        # Probe the real kernel lock, rather than relying on a timing delay.
        with (root / ".build.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                protected = False
                fcntl.flock(lock, fcntl.LOCK_UN)
            except BlockingIOError:
                protected = True
        # Observe the actual publisher immediately before its real lock syscall.
        publisher = tmp_path / "publisher.py"
        publisher.write_text(
            "import fcntl, runpy, sys\n"
            "lock = fcntl.flock\n"
            "def observed(fd, operation):\n"
            "    if operation == fcntl.LOCK_EX:\n"
            f"        with open({str(ready)!r}, 'wb', buffering=0) as f: f.write(b'W')\n"
            "    return lock(fd, operation)\n"
            "fcntl.flock = observed\n"
            f"sys.argv = {build[1:]!r}\n"
            f"runpy.run_path({str(ledger)!r}, run_name='__main__')\n"
        )
        writer = subprocess.Popen(
            [sys.executable, str(publisher)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        with selectors.DefaultSelector() as selector:
            selector.register(ready_r, selectors.EVENT_READ)
            assert selector.select(15), "publisher never attempted its exclusive lock"
        assert os.read(ready_r, 1) == b"W"
        if not protected:
            # Old implementation: force actual publication and retirement before open.
            stdout, stderr = writer.communicate(timeout=20)
            assert writer.returncode == 0, (stdout, stderr)
            assert not first_generation.exists()
        os.write(release_w, b"R")
        stdout, stderr = reader.communicate(timeout=20)
        assert reader.returncode == 0, (stdout, stderr)
        stdout, stderr = writer.communicate(timeout=20)
        assert writer.returncode == 0, (stdout, stderr)
        assert protected, "selected reader held no publication lifetime lock"
        assert receipt.read_text().splitlines() == ["https://youtu.be/first"]
        assert not first_generation.exists()
        second = json.loads((root / "current.json").read_text())["generation"]
        assert second != pointer["generation"]
        assert (root / "generations" / second / "url_ledger.parquet").is_file()
        assert len(list((root / "generations").iterdir())) == 1
    finally:
        for child in (reader, writer):
            if child is not None and child.poll() is None:
                child.kill()
                child.communicate()
        for fd in (ready_r, release_w):
            os.close(fd)
