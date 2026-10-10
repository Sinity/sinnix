import os
import shutil
import subprocess
from pathlib import Path

import pytest


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
