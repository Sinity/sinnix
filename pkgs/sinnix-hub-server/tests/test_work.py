import json

import pytest
from sinnix_hub_server import work

PIN = {
    "kind": "conversation",
    "epoch": "browser-old",
    "id": "page-1",
    "url": "https://chatgpt.com/c/one",
}


@pytest.mark.parametrize(
    "change",
    [{"epoch": "browser-new"}, {"url": "https://chatgpt.com/c/two"}, {"id": "page-2"}],
)
def test_focus_rejects_reused_destination(monkeypatch, change):
    monkeypatch.setattr(work, "destinations", lambda: {"rows": [{"pin": PIN | change}]})
    monkeypatch.setattr(work, "urlopen", lambda *a, **k: pytest.fail("must not focus"))
    with pytest.raises(ValueError, match="stale/unverified"):
        work.focus(PIN)


def test_terminal_focus_uses_exact_socket_and_window(monkeypatch):
    pin = {
        "kind": "terminal",
        "endpoint": "/fixture/socket",
        "epoch": "boot:pid:start:inode",
        "id": "7",
    }
    monkeypatch.setattr(work, "destinations", lambda: {"rows": [{"pin": pin}]})
    calls = []
    monkeypatch.setattr(work, "command", calls.append)
    work.focus(pin)
    assert calls == [
        [
            "kitty",
            "@",
            "--to",
            "unix:/fixture/socket",
            "focus-window",
            "--match",
            "id:7",
        ]
    ]


def test_missing_sources_are_gaps(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))

    def unavailable(*args):
        raise OSError("unavailable")

    monkeypatch.setattr(work, "browser", unavailable)
    assert work.destinations() == {
        "rows": [],
        "gaps": [
            "No terminal destinations observed",
            "Conversation source unavailable",
        ],
        "omitted": 0,
    }


def test_work_route(hub_server_factory, http_get, monkeypatch):
    monkeypatch.setattr(
        work, "destinations", lambda: {"rows": [{"pin": PIN}], "gaps": []}
    )
    status, _, body = http_get(hub_server_factory() + "/v1/work")
    assert status == 200
    assert json.loads(body)["rows"][0]["pin"] == PIN
