from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import SimpleNamespace


def load_script():
    root = Path(__file__).parents[3]
    return SourceFileLoader("sinnix_ytdlp", str(root / "scripts/sinnix-ytdlp")).load_module()


def test_canonical_page_alias_does_not_retry(monkeypatch, tmp_path):
    downloader = load_script()
    page = "https://catalog.example.test/watch/item?from=list"
    calls = []

    def run(command, **_kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=23)

    monkeypatch.setattr(downloader.subprocess, "run", run)
    monkeypatch.setattr(downloader, "structured_video_url", lambda _page: "https://catalog.example.test/watch/item#player")
    monkeypatch.setattr(downloader, "browser_video_url", lambda _page: (_ for _ in ()).throw(AssertionError("page alias must not open a browser")))
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
