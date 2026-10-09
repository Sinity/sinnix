from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import SimpleNamespace
import os

import pytest


@pytest.fixture(autouse=True)
def restore_caller_umask():
    prior = os.umask(0o022)
    try:
        yield
    finally:
        os.umask(prior)


def test_downloader_children_create_private_outputs(monkeypatch, tmp_path):
    downloader = load_script()
    real_run = downloader.subprocess.run
    output = tmp_path / "download"

    def run(_command, **_kwargs):
        return real_run(
            [downloader.sys.executable, "-c",
             "from pathlib import Path; import sys; p=Path(sys.argv[1]); p.mkdir(); (p/'receipt').write_text('neutral')",
             str(output)],
            check=False,
        )

    monkeypatch.setattr(downloader.subprocess, "run", run)
    monkeypatch.setattr(downloader.sys, "argv", ["sinnix-ytdlp", "https://example.invalid/neutral"])
    monkeypatch.setenv("SINNIX_CHROME_PROFILE", str(tmp_path / "no-profile"))
    assert downloader.main() == 0
    assert output.stat().st_mode & 0o777 == 0o700
    assert (output / "receipt").stat().st_mode & 0o777 == 0o600
    assert (output / "receipt").read_text() == "neutral"


def load_script():
    root = Path(__file__).parents[3]
    return SourceFileLoader(
        "sinnix_ytdlp", str(root / "scripts/sinnix-ytdlp")
    ).load_module()


def test_canonical_page_alias_does_not_retry(monkeypatch, tmp_path):
    downloader = load_script()
    page = "https://catalog.example.test/watch/item?from=list"
    calls = []

    def run(command, **_kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=23)

    monkeypatch.setattr(downloader.subprocess, "run", run)
    monkeypatch.setattr(
        downloader,
        "structured_video_url",
        lambda _page: "https://catalog.example.test/watch/item#player",
    )
    monkeypatch.setattr(
        downloader,
        "browser_video_url",
        lambda _page: (_ for _ in ()).throw(
            AssertionError("page alias must not open a browser")
        ),
    )
    monkeypatch.setattr(downloader.sys, "argv", ["sinnix-ytdlp", page])
    monkeypatch.setenv("SINNIX_CHROME_PROFILE", str(tmp_path / "no-profile"))

    assert downloader.main() == 23
    assert calls == [["yt-dlp", page]]


def test_distinct_media_url_retries_once_with_source_headers(monkeypatch, tmp_path):
    downloader = load_script()
    page = "https://catalog.example.test/watch/item?from=list"
    media = "https://media.example.test/streams/item.m3u8"
    calls = []
    outcomes = iter([17, 0])

    def run(command, **_kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=next(outcomes))

    monkeypatch.setattr(downloader.subprocess, "run", run)
    monkeypatch.setattr(downloader, "structured_video_url", lambda _page: media)
    monkeypatch.setattr(downloader.sys, "argv", ["sinnix-ytdlp", page])
    monkeypatch.setenv("SINNIX_CHROME_PROFILE", str(tmp_path / "no-profile"))

    assert downloader.main() == 0
    assert calls == [
        ["yt-dlp", page],
        [
            "yt-dlp",
            "--referer",
            page,
            "--add-header",
            "Origin:https://catalog.example.test",
            media,
        ],
    ]
