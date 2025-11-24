import datetime
import json
import os
import socket
import time
import urllib.error
import urllib.request
from functools import partial
from typing import Dict, Optional

from qutebrowser.api import hook, message
from qutebrowser.qt.core import QTimer, QUrl
from qutebrowser.utils import objreg

try:
    config  # provided by qutebrowser at runtime
except NameError:  # pragma: no cover - fallback for linting/tests
    from qutebrowser.api import config as _config_stub

    config = _config_stub

try:
    config.load_autoconfig(False)
except AttributeError:
    from qutebrowser.config import configfiles

    configfiles.read_autoconfig()

try:
    c = config.config  # old API
except AttributeError:
    c = config  # new ConfigAPI provides what we need directly
c.session.lazy_restore = True
c.new_instance_open_target = "window"
c.new_instance_open_target_window = "last-opened"
c.tabs.show = "never"
c.tabs.tabs_are_windows = True
c.tabs.focus_stack_size = 30
c.tabs.last_close = "close"
c.tabs.new_position.related = "next"
c.tabs.new_position.unrelated = "next"
c.tabs.select_on_remove = "prev"
c.tabs.background = True
c.tabs.close_mouse_button = "middle"
c.tabs.close_mouse_button_on_bar = "ignore"

# Content controls --------------------------------------------------------- #
c.content.blocking.enabled = True
c.content.blocking.method = "both"
c.content.blocking.hosts.lists = [
    "https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts",
]
c.content.blocking.adblock.lists = [
    "https://easylist.to/easylist/easylist.txt",
    "https://easylist.to/easylist/easyprivacy.txt",
    "https://secure.fanboy.co.nz/fanboy-cookiemonster.txt",
    "https://raw.githubusercontent.com/brave/adblock-lists/master/brave-lists/brave-social.txt",
    "https://raw.githubusercontent.com/uBlockOrigin/uAssets/master/filters/annoyances.txt",
]
c.content.blocking.whitelist = [
    "https://pay.google.com/*",
    "https://payments.google.com/*",
]
c.content.cookies.accept = "no-3rdparty"
c.content.autoplay = False
c.content.notifications.default = False
c.content.webrtc_ip_handling_policy = "default-public-interface-only"
c.content.websocket_accept_all_requests = False
c.content.pdfjs = True
c.content.headers.accept_language = "en-US,en;q=0.9"
c.content.geolocation = False
c.content.javascript.clipboard = "access"
c.content.javascript.can_access_clipboard = True

# Appearance --------------------------------------------------------------- #
c.window.title_format = "{perc}{audio}{title} — {host}"
c.statusbar.padding = {"top": 2, "bottom": 2, "left": 8, "right": 8}
c.scrolling.smooth = True
c.fonts.default_size = "11pt"
c.fonts.web.family.standard = "Inter"
c.content.user_stylesheets = ["~/.config/qutebrowser/user.css"]

# Pages & search ----------------------------------------------------------- #
c.url.default_page = "about:blank"
c.url.start_pages = ["about:blank"]
c.url.searchengines = {
    "DEFAULT": "https://duckduckgo.com/?q={}",
    "ddg": "https://duckduckgo.com/?q={}",
    "g": "https://google.com/search?q={}",
    "gh": "https://github.com/search?q={}",
    "hn": "https://hn.algolia.com/?q={}",
    "man": "https://man.archlinux.org/search?q={}",
    "nix": "https://search.nixos.org/packages?query={}",
    "yt": "https://www.youtube.com/results?search_query={}",
    "ytm": "https://music.youtube.com/search?q={}",
    "rd": "https://www.reddit.com/search/?q={}",
    "w": "https://en.wikipedia.org/wiki/Special:Search?search={}",
}

# Editor integration ------------------------------------------------------- #
c.editor.command = [
    "kitty",
    "@",
    "launch",
    "--type=tab",
    "--title=qute-edit",
    "--cwd",
    "{cwd}",
    "nvr",
    "--servername",
    "qutebrowser",
    "--remote-wait",
    "{file}",
]

# Keybindings -------------------------------------------------------------- #
config.bind("F", "hint links open -w")
config.bind("gf", "hint links open -w")
config.bind("gn", "open -w")
config.bind("m", "spawn --userscript open-in-mpv")
config.bind("M", "spawn --userscript open-in-mpv-audio")
config.bind(";m", "hint links spawn --userscript open-in-mpv")
config.bind(";M", "hint links spawn --userscript open-in-mpv-audio")
config.bind(";y", "spawn --userscript yt-related")
config.bind(";a", "spawn --userscript archive-both")
config.bind(";r", "spawn --userscript research-capture")
config.bind(";s", "spawn --userscript raindrop-save")
config.bind("gt", "spawn --detach hyprctl dispatch changegroupactive f")
config.bind("gT", "spawn --detach hyprctl dispatch changegroupactive b")
config.bind("g`", "spawn --detach hyprctl dispatch togglegroup")
config.bind("g.", "spawn --detach hyprctl dispatch lockactivegroup toggle")
config.bind("xx", "config-cycle content.blocking.enabled ;; reload")


# Hyprland/tab-management integration ------------------------------------- #
TAB_LIMIT = int(os.environ.get("QUTE_TAB_LIMIT", "16"))
DEDUP_SCHEMES = {"http", "https"}
_connected_windows: set[int] = set()
_window_callbacks: Dict[int, list] = {}
_timers: list[QTimer] = []
_aw_endpoint = os.environ.get("QUTE_ACTIVITYWATCH_URL", "http://127.0.0.1:5600/api/0").rstrip("/")
_aw_bucket = os.environ.get("QUTE_ACTIVITYWATCH_BUCKET", "aw-watcher-window_qutebrowser")
_aw_client = os.environ.get("QUTE_ACTIVITYWATCH_CLIENT", "qutebrowser-hypr")
_aw_hostname = socket.gethostname()


def _normalize_url(url: QUrl) -> str:
    if not url.isValid():
        return ""
    normalized = QUrl(url)
    normalized.setPassword("")
    normalized.setFragment("")
    text = normalized.toString()
    return text.rstrip("/")


def _mark_seen(tab) -> None:
    tab.data.sinnix_last_seen = time.monotonic()


def _register_tab(tab) -> None:
    if getattr(tab.data, "sinnix_registered", False):
        return
    tab.data.sinnix_registered = True
    _mark_seen(tab)

    cb_url = partial(_handle_tab_url_changed, tab)
    cb_loaded = partial(_handle_tab_loaded, tab)
    tab.url_changed.connect(cb_url)
    tab.load_finished.connect(cb_loaded)
    callbacks = getattr(tab.data, "sinnix_callbacks", [])
    callbacks.extend([cb_url, cb_loaded])
    tab.data.sinnix_callbacks = callbacks


def _handle_tab_url_changed(tab, url: QUrl) -> None:
    _mark_seen(tab)
    _dedupe(tab.win_id)
    _enforce_tab_limit(tab.win_id)
    _send_aw_event(tab, url)


def _handle_tab_loaded(tab, ok: bool) -> None:
    if not ok:
        return
    _mark_seen(tab)
    _dedupe(tab.win_id)
    _enforce_tab_limit(tab.win_id)
    _send_aw_event(tab, tab.url())


def _iter_tabbed_browsers():
    for win_id, window in list(objreg.window_registry.items()):
        try:
            tabbed = objreg.get("tabbed-browser", scope="window", window=win_id)
        except objreg.RegistryUnavailableError:
            continue
        yield win_id, tabbed


def _dedupe(win_id: int) -> None:
    try:
        tabbed = objreg.get("tabbed-browser", scope="window", window=win_id)
    except objreg.RegistryUnavailableError:
        return

    keep: Dict[str, object] = {}
    duplicates = set()
    for tab in tabbed.widgets():
        url = tab.url()
        if not url.isValid() or url.scheme() not in DEDUP_SCHEMES:
            continue
        key = _normalize_url(url)
        if not key:
            continue

        existing = keep.get(key)
        last_seen = getattr(tab.data, "sinnix_last_seen", time.monotonic())
        if existing is None:
            keep[key] = tab
            continue

        existing_seen = getattr(existing.data, "sinnix_last_seen", 0.0)
        if last_seen > existing_seen:
            keep[key] = tab
            duplicates.add(existing)
        else:
            duplicates.add(tab)

    current = tabbed.widget.currentWidget()
    for tab in duplicates:
        if tab is current or tab.data.pinned:
            continue
        try:
            tabbed.close_tab(tab, add_undo=False, new_undo=False)
        except Exception:
            pass


def _enforce_tab_limit(win_id: int) -> None:
    if TAB_LIMIT <= 0:
        return
    try:
        tabbed = objreg.get("tabbed-browser", scope="window", window=win_id)
    except objreg.RegistryUnavailableError:
        return

    candidates = [tab for tab in tabbed.widgets() if not tab.data.pinned]
    if len(candidates) <= TAB_LIMIT:
        return

    candidates.sort(key=lambda t: getattr(t.data, "sinnix_last_seen", 0.0))
    current = tabbed.widget.currentWidget()
    to_close = len(candidates) - TAB_LIMIT

    for tab in candidates:
        if to_close <= 0:
            break
        if tab is current:
            continue
        try:
            tabbed.close_tab(tab, add_undo=False, new_undo=False)
            to_close -= 1
        except Exception:
            continue


def _on_current_tab_changed(tab) -> None:
    if tab is None:
        return
    _mark_seen(tab)
    _enforce_tab_limit(tab.win_id)


def _on_new_tab(tab, _index: int) -> None:
    _register_tab(tab)
    _dedupe(tab.win_id)
    _enforce_tab_limit(tab.win_id)


def _on_window_shutdown(win_id: int) -> None:
    _connected_windows.discard(win_id)
    _window_callbacks.pop(win_id, None)


def _ensure_connections() -> None:
    for win_id, tabbed in _iter_tabbed_browsers():
        if win_id in _connected_windows:
            continue

        tabbed.new_tab.connect(_on_new_tab)
        tabbed.current_tab_changed.connect(_on_current_tab_changed)

        shutdown_cb = partial(_on_window_shutdown, win_id)
        tabbed.shutting_down.connect(shutdown_cb)
        _window_callbacks.setdefault(win_id, []).append(shutdown_cb)

        for tab in tabbed.widgets():
            _register_tab(tab)

        current = tabbed.widget.currentWidget()
        if current is not None:
            _mark_seen(current)

        _connected_windows.add(win_id)


def _aw_request(method: str, path: str, payload: Optional[dict] = None) -> None:
    if not _aw_endpoint:
        return
    data_bytes = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data_bytes = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        f"{_aw_endpoint}{path}",
        data=data_bytes,
        headers=headers,
        method=method.upper(),
    )
    try:
        urllib.request.urlopen(req, timeout=1.0)
    except (urllib.error.URLError, TimeoutError):
        pass


def _ensure_aw_bucket() -> None:
    payload = {"client": _aw_client, "type": "app", "hostname": _aw_hostname}
    _aw_request("POST", f"/buckets/{_aw_bucket}", payload)


def _send_aw_event(tab, url: QUrl) -> None:
    if not url.isValid() or url.scheme() not in DEDUP_SCHEMES:
        return
    now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
    payload = {
        "timestamp": now.isoformat(),
        "duration": 0,
        "data": {
            "app": "qutebrowser",
            "title": tab.title() or url.toDisplayString(),
            "url": url.toString(),
        },
    }
    _aw_request("POST", f"/buckets/{_aw_bucket}/events", payload)


@hook.init()
def _sinnix_qute_init(_context) -> None:
    _ensure_aw_bucket()
    _ensure_connections()

    timer = QTimer()
    timer.setInterval(3000)
    timer.setSingleShot(False)
    timer.timeout.connect(_ensure_connections)
    timer.start()
    _timers.append(timer)

    message.info("Qutebrowser: Hyprland groups + ActivityWatch hooks loaded.")
