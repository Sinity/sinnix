"""The /terminals/* contract as absorbed from an earlier standalone
terminal-viewing daemon (sinnix-859p) -- URL routing, the body cap, the named-key mapping, and
the history filename join. Live kitty/asciinema behavior (an actual window
snapshot, an actual live-stream join) is not mockable here and is a
post-switch coordinator check.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest
from sinnix_ops_reducer import terminals
from sinnix_ops_reducer.reducer import Reducer
from sinnix_ops_reducer.server import Handler


def test_named_keys_reject_anything_not_in_the_quick_action_set() -> None:
    # send_key looks the socket up only after confirming the name maps to a
    # real kitty key; an unmapped name must never reach find_socket_for_pid.
    assert terminals.send_key(999999, 1, "not-a-real-key") is False
    assert set(terminals.NAMED_KEYS) == {
        "enter",
        "ctrl-c",
        "ctrl-d",
        "tab",
        "up",
        "escape",
    }


def test_history_for_joins_by_pid_and_window_id(tmp_path: Path) -> None:
    matching = {
        "ansi_file": "2026-08-18T00-00-00-prime-pid111-win222-bash.ansi",
        "captured_at": "2026-08-18T00:00:00Z",
        "title": "bash",
    }
    (tmp_path / "2026-08-18T00-00-00-prime-pid111-win222-bash.meta.json").write_text(
        json.dumps(matching)
    )
    # A different window's capture must not leak into pid111/win222's history
    # -- this is the mutation that would let the wrong scrollback render.
    other = {"ansi_file": "x.ansi", "captured_at": "t", "title": "other"}
    (tmp_path / "2026-08-18T00-00-01-prime-pid111-win333-zsh.meta.json").write_text(
        json.dumps(other)
    )

    rows = terminals.history_for(tmp_path, 111, 222)
    assert len(rows) == 1
    assert rows[0]["ansi_file"] == matching["ansi_file"]


def test_history_for_a_directory_that_does_not_exist_yet_is_empty(
    tmp_path: Path,
) -> None:
    assert terminals.history_for(tmp_path / "nope", 1, 2) == []


@pytest.mark.parametrize(
    ("path", "expect_pid", "expect_win"),
    [
        ("/terminals/v1/windows/111/222/content", "111", "222"),
        ("/terminals/v1/windows/111/222/history", "111", "222"),
        ("/terminals/v1/windows/111/222/send", "111", "222"),
    ],
)
def test_route_regexes_extract_pid_and_window_id(
    path: str, expect_pid: str, expect_win: str
) -> None:
    for pattern in (terminals.CONTENT_RE, terminals.HISTORY_RE, terminals.SEND_RE):
        match = pattern.match(path)
        if match:
            assert match.group(1) == expect_pid
            assert match.group(2) == expect_win
            return
    raise AssertionError(f"no route regex matched {path}")


def test_history_file_route_only_matches_dot_ansi_names() -> None:
    assert terminals.HISTORY_FILE_RE.match("/terminals/v1/windows/1/2/history/x.ansi")
    assert (
        terminals.HISTORY_FILE_RE.match(
            "/terminals/v1/windows/1/2/history/../../etc/passwd"
        )
        is None
    )
    assert (
        terminals.HISTORY_FILE_RE.match("/terminals/v1/windows/1/2/history/x.txt")
        is None
    )


def test_live_route_captures_optional_rest_segment() -> None:
    bare = terminals.LIVE_RE.match("/terminals/v1/live/111/222")
    assert bare and bare.group("rest") is None
    ws = terminals.LIVE_RE.match("/terminals/v1/live/111/222/ws")
    assert ws and ws.group("rest") == "/ws"


def test_is_terminal_route_does_not_capture_the_estate_root() -> None:
    assert not terminals.is_terminal_route("/")
    assert not terminals.is_terminal_route("/work/")
    assert terminals.is_terminal_route("/terminals")
    assert terminals.is_terminal_route("/terminals/")
    assert terminals.is_terminal_route("/terminals/v1/windows")


@pytest.fixture
def hub_server(tmp_path: Path):
    reducer = Reducer(tmp_path / "status.json", tmp_path / "token", lambda: {})
    reducer.refresh()
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.reducer = reducer
    server.token = "fixture-token"
    server.is_unix = True
    server.hub_manifest = None
    server.inventory_path = tmp_path / "missing-inventory.json"
    server.feedback = None
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def get(url: str) -> tuple[int, str, str]:
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return (
                response.status,
                response.headers["Content-Type"],
                response.read().decode(),
            )
    except urllib.error.HTTPError as error:
        return error.code, error.headers["Content-Type"], error.read().decode()


def test_the_terminal_index_page_is_reachable_over_the_shared_listener(
    hub_server: str,
) -> None:
    status, content_type, body = get(hub_server + "/terminals/")
    assert status == 200
    assert content_type.startswith("text/html")
    assert "sinnix terminals" in body
    # Without the trailing slash too -- the client-side JS hardcodes
    # /terminals/v1/... paths regardless of which alias loaded the page.
    assert get(hub_server + "/terminals")[0] == 200


def test_windows_list_is_json_on_the_shared_listener(
    hub_server: str, monkeypatch
) -> None:
    monkeypatch.setattr(terminals, "list_windows", lambda: [{"kitty_pid": 1}])
    status, content_type, body = get(hub_server + "/terminals/v1/windows")
    assert status == 200
    assert content_type == "application/json"
    assert json.loads(body) == [{"kitty_pid": 1}]


def test_an_unknown_terminal_path_is_a_json_404(hub_server: str) -> None:
    status, content_type, body = get(hub_server + "/terminals/v1/nope")
    assert status == 404
    assert content_type == "application/json"
    assert json.loads(body)["error"] == "not_found"


def test_the_ops_json_api_still_answers_alongside_terminals(hub_server: str) -> None:
    # The route merge must not shadow the pre-existing /v1/* namespace: proof
    # that /terminals and /v1/health are dispatched by disjoint branches.
    status, content_type, body = get(hub_server + "/v1/health")
    assert status == 200
    assert content_type == "application/json"
    assert json.loads(body)["schema"] == "sinnix-ops-v1"


def post(url: str, body: bytes, headers: dict[str, str]) -> tuple[int, str]:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()


def test_send_rejects_a_body_over_the_64kib_cap(hub_server: str) -> None:
    oversized = json.dumps({"text": "x" * (terminals.MAX_BODY + 1)}).encode()
    status, body = post(
        hub_server + "/terminals/v1/windows/1/2/send",
        oversized,
        {"Content-Type": "application/json", "Content-Length": str(len(oversized))},
    )
    assert status == 400
    assert "oversized" in json.loads(body)["error"]


def test_send_requires_text_or_key(hub_server: str) -> None:
    empty = json.dumps({}).encode()
    status, body = post(
        hub_server + "/terminals/v1/windows/1/2/send",
        empty,
        {"Content-Type": "application/json", "Content-Length": str(len(empty))},
    )
    assert status == 400
    assert "text" in json.loads(body)["error"]


def test_send_dispatches_text_and_key_to_the_kitty_helpers(
    hub_server: str, monkeypatch
) -> None:
    calls = []
    monkeypatch.setattr(
        terminals,
        "send_text",
        lambda pid, win, text: calls.append(("text", pid, win, text)) or True,
    )
    monkeypatch.setattr(
        terminals,
        "send_key",
        lambda pid, win, key: calls.append(("key", pid, win, key)) or True,
    )

    payload = json.dumps({"text": "ls\r"}).encode()
    status, body = post(
        hub_server + "/terminals/v1/windows/111/222/send",
        payload,
        {"Content-Type": "application/json", "Content-Length": str(len(payload))},
    )
    assert status == 200
    assert json.loads(body) == {"status": "sent"}
    assert calls == [("text", 111, 222, "ls\r")]

    calls.clear()
    payload = json.dumps({"key": "ctrl-c"}).encode()
    status, _ = post(
        hub_server + "/terminals/v1/windows/111/222/send",
        payload,
        {"Content-Type": "application/json", "Content-Length": str(len(payload))},
    )
    assert status == 200
    assert calls == [("key", 111, 222, "ctrl-c")]


def test_send_answers_404_when_the_kitty_helper_refuses(
    hub_server: str, monkeypatch
) -> None:
    monkeypatch.setattr(terminals, "send_text", lambda pid, win, text: False)
    payload = json.dumps({"text": "ls\r"}).encode()
    status, body = post(
        hub_server + "/terminals/v1/windows/1/2/send",
        payload,
        {"Content-Type": "application/json", "Content-Length": str(len(payload))},
    )
    assert status == 404
    assert "window not found" in json.loads(body)["error"]
