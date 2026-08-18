"""Terminal contents and control as a first-class remote surface (sinnix-qxm8).

Absorbed from an earlier standalone terminal-viewing daemon (sinnix-859p),
same move as the hub feedback spool before it (see feedback.py): the routes, the
response shapes, and the design doctrine below carry over unchanged. Only the
transport changes -- this used to be its own Unix-socket process behind
`handle_path /terminals/*`; it is now a route family on the reducer's own
listeners, reached at the literal `/terminals/*` prefix (Caddy no longer
strips it, so every path here still starts with `/terminals`, matching what
the client-side JS in INDEX_HTML already hardcodes).

The operator should never have to learn tmux to read or drive their own
terminals remotely. This serves, using nothing but the recorders and captures
this host already runs -- asciinema on every shell, kitty's own remote-control
protocol, and the scrollback captures sinnix-capture-kitty-scrollback already
writes --

  * a live stream -- the browser and the desktop window showing the same PTY
    at the same time, not a periodic snapshot. Every kitty shell already runs
    under asciinema (that is how the capture lake is written); asciinema's
    `session` mode writes that recording *and* serves the same byte stream
    live, so the mirror is the recorder already present rather than a new
    mechanism. A viewer joining late is sent the current screen first, so the
    browser opens on what the window shows now. This is why there is still no
    multiplexer here: the PTY stays exactly where it was, owned by the same
    kitty window, and nothing has to be attached, detached, or learned;

  * a snapshot -- current on-screen contents via kitty's own remote control,
    for any window without a live stream (each kitty instance has its own
    control socket under $XDG_RUNTIME_DIR/kitty-*);
  * history -- the existing full-ANSI scrollback captures for that same
    window, joined by (kitty_pid, window_id) which is exactly the filename
    key sinnix-capture-kitty-scrollback already uses;
  * control -- sending text and key presses into a live window via kitty's
    own `send-text`/`send-key`, operator-initiated from the hub page. This is
    the operator's own deliberate typing, routed through a browser instead of
    a local keyboard -- it is not the "never inject into a live agent TUI
    while it is sampling" case (that rule is about *automated* interruption
    of a session an agent doesn't own; a human choosing to type into their
    own window is the window's owner acting, same as sitting at the desk).

NON-GOALS, deliberately: no tmux/screen/multiplexer of any kind; no second
capture lane (scrollback capture already exists, this only reads it); no
server-side shell-completion engine (real bash/zsh completion needs a shell
process to ask, which is a much larger lift with its own correctness
problems) -- the client-side autocomplete here is a plain per-window recently-
sent-text history, cheap and genuinely useful, not a completion engine.

Deliberately minimal, matching the hub feedback spool's own decisions:
  * no auth of its own -- the merged Handler's `_authorized()` gate applies to
    every route on these listeners, same as the pages; the retired standalone
    daemon relied on the tailnet boundary alone, which is a subset of that;
  * no database -- kitty's own `ls`/`get-text` and the scrollback capture's
    files on disk are the only state; sent-text history lives in the
    browser's own localStorage, not server state;
  * synchronous, direct action for control (not a spooled/queued write like
    the feedback annotations) -- send-text has to reach the window now,
    queuing it for later would be actively wrong.
"""

from __future__ import annotations

import html
import http.client
import json
import os
import re
import socket
import subprocess
from pathlib import Path
from typing import Any

KITTY_BIN = "kitty"
AHA_BIN = "aha"
MAX_BODY = 1 << 16  # 64 KiB: a pasted command, not a file upload

# sinnix-capture-kitty-scrollback's own write location and filename
# convention: <TIMESTAMP>-<host>-pid<pid>-win<id>-<title-slug>.ansi (+
# .meta.json sibling). No host ever ran the retired daemon with a different
# --history-dir than this, so the value is now a fixed convention rather than
# a reducer CLI flag.
HISTORY_DIR = Path("/realm/data/activity/kitty-scrollback")
HISTORY_NAME_RE = re.compile(
    r"^(?P<ts>[^-]+)-(?P<host>[^-]+)-pid(?P<pid>\d+)-win(?P<winid>\d+)-"
)

LIVE_RE = re.compile(r"^/terminals/v1/live/(\d+)/(\d+)(?P<rest>/[A-Za-z0-9._-]*)?$")
CONTENT_RE = re.compile(r"^/terminals/v1/windows/(\d+)/(\d+)/content$")
HISTORY_RE = re.compile(r"^/terminals/v1/windows/(\d+)/(\d+)/history$")
HISTORY_FILE_RE = re.compile(
    r"^/terminals/v1/windows/(\d+)/(\d+)/history/([A-Za-z0-9._-]+\.ansi)$"
)
SEND_RE = re.compile(r"^/terminals/v1/windows/(\d+)/(\d+)/send$")


def is_terminal_route(path: str) -> bool:
    return (
        path == "/terminals"
        or path.startswith("/terminals/")
        or path.startswith("/terminals?")
    )


def discover_kitty_sockets() -> list[Path]:
    runtime_dir = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
    if not runtime_dir.is_dir():
        return []
    return sorted(p for p in runtime_dir.glob("kitty-*") if p.is_socket())


def kitty_ls(sock: Path) -> list[dict[str, Any]]:
    try:
        out = subprocess.run(
            [KITTY_BIN, "@", "--to", f"unix:{sock}", "ls"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if out.returncode != 0:
        return []
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError:
        return []


def pid_from_socket(sock: Path) -> int | None:
    # kitty-<user>-<pid>
    m = re.match(r"^kitty-.*-(\d+)$", sock.name)
    return int(m.group(1)) if m else None


def list_windows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    streams = live_streams()
    for sock in discover_kitty_sockets():
        pid = pid_from_socket(sock)
        for os_window in kitty_ls(sock):
            for tab in os_window.get("tabs", []):
                for win in tab.get("windows", []):
                    rows.append(
                        {
                            "socket": str(sock),
                            "kitty_pid": pid,
                            "window_id": win.get("id"),
                            "title": win.get("title") or tab.get("title") or "",
                            "cwd": win.get("cwd", ""),
                            "is_focused": bool(win.get("is_focused")),
                            "lines": win.get("lines"),
                            "live": (pid, win.get("id")) in streams,
                        }
                    )
    return rows


def find_socket_for_pid(pid: int) -> Path | None:
    for sock in discover_kitty_sockets():
        if pid_from_socket(sock) == pid:
            return sock
    return None


def get_window_text(pid: int, window_id: int) -> str | None:
    sock = find_socket_for_pid(pid)
    if sock is None:
        return None
    try:
        out = subprocess.run(
            [
                KITTY_BIN,
                "@",
                "--to",
                f"unix:{sock}",
                "get-text",
                "--match",
                f"id:{window_id}",
                "--extent",
                "screen",
                "--ansi",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    return out.stdout


def send_text(pid: int, window_id: int, text: str) -> bool:
    sock = find_socket_for_pid(pid)
    if sock is None:
        return False
    try:
        out = subprocess.run(
            [
                KITTY_BIN,
                "@",
                "--to",
                f"unix:{sock}",
                "send-text",
                "--match",
                f"id:{window_id}",
                text,
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return out.returncode == 0


# Named key sends the UI offers as quick-action buttons -- kitty's send-key
# syntax for control characters, not a full keymap.
NAMED_KEYS = {
    "enter": "enter",
    "ctrl-c": "ctrl+c",
    "ctrl-d": "ctrl+d",
    "tab": "tab",
    "up": "up",
    "escape": "escape",
}


def send_key(pid: int, window_id: int, name: str) -> bool:
    key = NAMED_KEYS.get(name)
    if key is None:
        return False
    sock = find_socket_for_pid(pid)
    if sock is None:
        return False
    try:
        out = subprocess.run(
            [
                KITTY_BIN,
                "@",
                "--to",
                f"unix:{sock}",
                "send-key",
                "--match",
                f"id:{window_id}",
                key,
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return out.returncode == 0


def live_streams() -> dict[tuple[int, int], int]:
    """Map (kitty_pid, window_id) -> the asciinema live-stream port for that window.

    sinnix-captured-shell runs every kitty shell under `asciinema session
    --stream-local`, which serves the session's own PTY live on an ephemeral
    loopback port. Nothing writes that port down: the recorder inherited
    KITTY_PID/KITTY_WINDOW_ID from the window it belongs to, so the process
    table already states which window each stream is, and the listening socket
    already states which port. Reading both back is exact and self-healing --
    a dead recorder simply stops appearing.
    """
    streams: dict[tuple[int, int], int] = {}
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            if (proc / "comm").read_text().strip() != "asciinema":
                continue
            env = dict(
                item.split("=", 1)
                for item in (proc / "environ")
                .read_bytes()
                .decode("utf-8", "replace")
                .split("\0")
                if "=" in item
            )
        except OSError:
            continue
        try:
            key = (int(env["KITTY_PID"]), int(env["KITTY_WINDOW_ID"]))
        except (KeyError, ValueError):
            continue
        port = listening_port(int(proc.name))
        if port is not None:
            streams[key] = port
    return streams


def listening_port(pid: int) -> int | None:
    """The IPv4 port `pid` is listening on, via its socket inodes in /proc."""
    inodes: set[str] = set()
    try:
        for fd in (Path("/proc") / str(pid) / "fd").iterdir():
            try:
                target = os.readlink(fd)
            except OSError:
                continue
            if target.startswith("socket:["):
                inodes.add(target[len("socket:[") : -1])
    except OSError:
        return None
    if not inodes:
        return None
    try:
        lines = Path("/proc/net/tcp").read_text().splitlines()[1:]
    except OSError:
        return None
    for line in lines:
        fields = line.split()
        # st == 0A is TCP_LISTEN; field 9 is the socket inode.
        if len(fields) < 10 or fields[3] != "0A" or fields[9] not in inodes:
            continue
        return int(fields[1].split(":")[1], 16)
    return None


# asciinema serves its own player page; these are the only two things in it
# that assume the stream sits at the server root, which it does not once the
# hub proxies it under a per-window path.
PLAYER_WS_SRC = "loc.host + '/ws'"
PLAYER_WS_PROXIED = "loc.host + loc.pathname + 'ws'"
PLAYER_FONT_SRC = 'url("/SymbolsNerdFont'
PLAYER_FONT_PROXIED = 'url("SymbolsNerdFont'


def fetch_upstream(port: int, path: str) -> tuple[int, str, bytes] | None:
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        conn.request("GET", path)
        response = conn.getresponse()
        return (
            response.status,
            response.getheader("Content-Type", "application/octet-stream"),
            response.read(),
        )
    except (OSError, http.client.HTTPException):
        return None
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001 -- best-effort close of a dead connection
            pass


def connect_live_ws(port: int, headers) -> socket.socket:
    """Open the raw TCP connection the /ws relay splices onto, with the
    upstream request already sent. Callers pump bytes both ways; nothing
    here interprets the stream (see server.Handler for why)."""
    upstream = socket.create_connection(("127.0.0.1", port), timeout=10)
    request = ["GET /ws HTTP/1.1", f"Host: 127.0.0.1:{port}"]
    request += [
        f"{name}: {value}"
        for name, value in headers.items()
        if name.lower() not in ("host", "content-length")
    ]
    upstream.sendall(("\r\n".join(request) + "\r\n\r\n").encode())
    return upstream


def ansi_to_html(ansi_text: str, title: str) -> str:
    try:
        out = subprocess.run(
            [AHA_BIN, "--black", "--title", title],
            input=ansi_text,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if out.returncode == 0 and out.stdout:
            return out.stdout
    except (OSError, subprocess.TimeoutExpired):
        pass
    # Fallback: plain <pre>, still readable, just no ANSI color.
    return (
        f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title>"
        "<style>body{background:#111;color:#ddd;font-family:monospace}</style></head>"
        f"<body><pre>{html.escape(ansi_text)}</pre></body></html>"
    )


def history_for(history_dir: Path, pid: int, window_id: int) -> list[dict[str, Any]]:
    needle = f"-pid{pid}-win{window_id}-"
    rows: list[dict[str, Any]] = []
    if not history_dir.is_dir():
        return rows
    for meta_path in sorted(history_dir.glob("*.meta.json"), reverse=True):
        if needle not in meta_path.name:
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rows.append(meta)
    return rows[:50]


INDEX_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>sinnix terminals</title>
<style>
  body{background:#111;color:#ddd;font-family:monospace;margin:0;display:flex;height:100vh}
  #list{width:320px;overflow-y:auto;border-right:1px solid #333;padding:8px}
  #view{flex:1;overflow:auto}
  #view iframe{width:100%;height:100%;border:0;background:#111}
  .win{padding:6px;border-bottom:1px solid #222;cursor:pointer}
  .win:hover{background:#1a1a1a}
  .win.focused{color:#8f8}
  .title{font-weight:bold}
  .cwd{color:#888;font-size:0.85em}
  .hist{padding:2px 0 2px 12px;color:#88f;cursor:pointer;font-size:0.85em}
  button{background:#222;color:#ddd;border:1px solid #444;padding:2px 8px;margin:4px 0;cursor:pointer}
  #control{display:flex;gap:4px;padding:6px;border-top:1px solid #333;background:#161616}
  #sendbox{flex:1;background:#111;color:#ddd;border:1px solid #444;padding:4px 6px;font-family:monospace}
  #keys button{margin:0 2px}
</style></head>
<body>
<div id="list">Loading...</div>
<div style="flex:1;display:flex;flex-direction:column">
  <div id="view">Select a window on the left.</div>
  <div id="control" style="display:none">
    <input id="sendbox" list="sendhist" placeholder="type, Enter to send (kitty send-text)" autocomplete="off">
    <datalist id="sendhist"></datalist>
    <span id="keys">
      <button data-key="enter">Enter</button>
      <button data-key="ctrl-c">Ctrl-C</button>
      <button data-key="ctrl-d">Ctrl-D</button>
      <button data-key="tab">Tab</button>
      <button data-key="up">Up</button>
      <button data-key="escape">Esc</button>
    </span>
  </div>
</div>
<script>
let current = null; // {pid, winId}

async function load() {
  const res = await fetch('/terminals/v1/windows');
  const wins = await res.json();
  const list = document.getElementById('list');
  list.innerHTML = '';
  for (const w of wins) {
    const div = document.createElement('div');
    div.className = 'win' + (w.is_focused ? ' focused' : '');
    div.innerHTML = `<div class="title">${w.live ? '● ' : ''}${w.title || '(untitled)'}</div><div class="cwd">${w.cwd}</div>`;
    div.onclick = () => (w.live ? showStream(w.kitty_pid, w.window_id) : showLive(w.kitty_pid, w.window_id));
    list.appendChild(div);
    if (w.live) {
      const snapBtn = document.createElement('div');
      snapBtn.className = 'hist';
      snapBtn.textContent = '↳ snapshot';
      snapBtn.onclick = (e) => { e.stopPropagation(); showLive(w.kitty_pid, w.window_id); };
      list.appendChild(snapBtn);
    }
    const histBtn = document.createElement('div');
    histBtn.className = 'hist';
    histBtn.textContent = '↳ history';
    histBtn.onclick = (e) => { e.stopPropagation(); showHistory(w.kitty_pid, w.window_id); };
    list.appendChild(histBtn);
  }
}

// Per-window recently-sent-text history in localStorage, feeding a <datalist>
// autocomplete on the send box. Not a shell-completion engine -- just "what
// did I type into this window before" recall, which is the cheap useful part.
function histKey(pid, winId) { return `sinnix-terminal-sent:${pid}:${winId}`; }
function loadHist(pid, winId) {
  try { return JSON.parse(localStorage.getItem(histKey(pid, winId)) || '[]'); }
  catch { return []; }
}
function pushHist(pid, winId, text) {
  const h = loadHist(pid, winId).filter(x => x !== text);
  h.unshift(text);
  localStorage.setItem(histKey(pid, winId), JSON.stringify(h.slice(0, 50)));
}
function renderHistDatalist(pid, winId) {
  const dl = document.getElementById('sendhist');
  dl.innerHTML = loadHist(pid, winId).map(t => `<option value="${t.replace(/"/g, '&quot;')}">`).join('');
}

// The live stream is the same PTY the desktop window is showing, rendered by
// asciinema's own player -- so it needs no refresh, and must not be reloaded
// on send (that would drop the WebSocket mid-session).
function showStream(pid, winId) {
  current = { pid, winId, streaming: true };
  document.getElementById('view').innerHTML =
    `<iframe src="/terminals/v1/live/${pid}/${winId}/"></iframe>`;
  document.getElementById('control').style.display = 'flex';
  renderHistDatalist(pid, winId);
}

// Fallback for windows with no live stream (a shell started before streaming
// was wired in, or one not launched through sinnix-captured-shell).
function showLive(pid, winId) {
  current = { pid, winId, streaming: false };
  document.getElementById('view').innerHTML =
    `<iframe src="/terminals/v1/windows/${pid}/${winId}/content"></iframe>`;
  document.getElementById('control').style.display = 'flex';
  renderHistDatalist(pid, winId);
}
async function showHistory(pid, winId) {
  current = null;
  document.getElementById('control').style.display = 'none';
  const res = await fetch(`/terminals/v1/windows/${pid}/${winId}/history`);
  const entries = await res.json();
  const view = document.getElementById('view');
  view.innerHTML = '<div style="padding:8px">' + entries.map(e =>
    `<div><a href="/terminals/v1/windows/${pid}/${winId}/history/${e.ansi_file}" target="_blank" style="color:#88f">${e.captured_at} -- ${e.title}</a></div>`
  ).join('') + (entries.length ? '' : '<i>no scrollback captures yet for this window</i>') + '</div>';
}

async function sendPayload(payload) {
  if (!current) return;
  await fetch(`/terminals/v1/windows/${current.pid}/${current.winId}/send`, {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
  });
  // The stream shows the effect on its own; only the snapshot view needs a
  // re-render to become visible.
  if (!current.streaming) {
    setTimeout(() => { if (current) showLive(current.pid, current.winId); }, 300);
  }
}

document.getElementById('sendbox').addEventListener('keydown', (e) => {
  if (e.key !== 'Enter' || !current) return;
  const text = e.target.value;
  if (!text) return;
  pushHist(current.pid, current.winId, text);
  renderHistDatalist(current.pid, current.winId);
  sendPayload({ text: text + '\r' });
  e.target.value = '';
});
document.getElementById('keys').addEventListener('click', (e) => {
  const key = e.target.dataset.key;
  if (key) sendPayload({ key });
});

load();
setInterval(load, 15000);
</script>
</body></html>
"""
