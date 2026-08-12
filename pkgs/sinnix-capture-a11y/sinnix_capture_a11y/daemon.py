"""AT-SPI2 accessibility-tree capture daemon.

Registers pyatspi listeners for focus-changed and text-changed events across
every running AT-SPI2-exposed application, and periodically dumps the
accessible subtree of the currently focused top-level window (bounded by
``subtree.build_subtree``'s max_depth/max_nodes -- this is deliberately NOT
a full-desktop walk).

Chromium-based apps (Chrome, Electron) only populate their AT-SPI tree when
launched with ``--force-renderer-accessibility`` (or the
``ACCESSIBILITY_ENABLED=1`` env var Chromium also honours); see
modules/services/capture-a11y.nix's module doc comment for where that flag
belongs (modules/features/desktop/browser.nix's Chrome wrapper -- out of
this module's scope, but a real coverage gap without it).

Only `run()` (and the pyatspi-typed helper it calls at listener-registration
time) touch the `pyatspi`/`gi` bindings; everything else in this module is
plain Python operating on duck-typed accessible objects, so it can be
exercised in tests without a live AT-SPI2 bus.
"""

from __future__ import annotations

import logging
import time

from sinnix_capture.writer import CaptureWriter

from .debounce import Debouncer
from .payloads import focus_payload, subtree_payload, text_changed_payload
from .subtree import build_subtree

logger = logging.getLogger("sinnix_capture_a11y")

_TOP_LEVEL_ROLE_NAMES = {"frame", "window", "dialog", "alert"}


class _AccessibleAdapter:
    """Adapts a live pyatspi Accessible into subtree.AccessibleNode."""

    __slots__ = ("_acc",)

    def __init__(self, acc) -> None:
        self._acc = acc

    def role_name(self) -> str:
        try:
            return self._acc.getRoleName() or ""
        except Exception:
            return ""

    def name(self) -> str:
        try:
            return self._acc.name or ""
        except Exception:
            return ""

    def text(self) -> str | None:
        try:
            iface = self._acc.queryText()
        except Exception:
            return None
        try:
            value = iface.getText(0, -1)
        except Exception:
            return None
        return value or None

    def children(self) -> list["_AccessibleAdapter"]:
        try:
            count = self._acc.getChildCount()
        except Exception:
            return []
        out: list[_AccessibleAdapter] = []
        for i in range(count):
            try:
                child = self._acc.getChildAtIndex(i)
            except Exception:
                continue
            if child is not None:
                out.append(_AccessibleAdapter(child))
        return out


def _app_name(acc) -> str:
    try:
        app = acc.getApplication()
        return (app.name if app else None) or "unknown"
    except Exception:
        return "unknown"


def _safe_role_name(acc) -> str:
    try:
        return acc.getRoleName() or ""
    except Exception:
        return ""


def _safe_name(acc) -> str:
    try:
        return acc.name or ""
    except Exception:
        return ""


def _top_level_window(acc):
    """Walk up parents to the nearest frame/window/dialog/alert ancestor.

    Compares AT-SPI role *names* (plain strings from getRoleName(), e.g.
    "frame") rather than the pyatspi.ROLE_* enum, so this stays pure Python
    with no `gi`/`pyatspi` import -- keeps it unit-testable and keeps the
    dependency footprint of the daemon's control-flow small.
    """
    node = acc
    seen = 0
    while node is not None and seen < 64:
        try:
            if node.getRoleName() in _TOP_LEVEL_ROLE_NAMES:
                return node
        except Exception:
            return node
        try:
            node = node.parent
        except Exception:
            return node
        seen += 1
    return acc


class A11yDaemon:
    def __init__(
        self,
        *,
        capture_root,
        subtree_interval_seconds: float,
        text_debounce_seconds: float,
        max_depth: int,
        max_nodes: int,
    ) -> None:
        self._writer = CaptureWriter(capture_root, "a11y")
        self._subtree_interval = subtree_interval_seconds
        self._max_depth = max_depth
        self._max_nodes = max_nodes
        self._text_debounce = Debouncer(text_debounce_seconds)
        self._focused_window = None
        self._last_subtree_dump = 0.0

    def _emit(self, payload: dict) -> None:
        try:
            self._writer.write(payload)
        except Exception:
            logger.exception(
                "sinnix-capture-a11y: failed to write %s record", payload.get("kind")
            )

    def on_focus(self, event) -> None:
        acc = event.source
        if acc is None:
            return
        self._focused_window = _top_level_window(acc)
        window_name = None
        if self._focused_window is not None:
            window_name = _safe_name(self._focused_window)
        self._emit(
            focus_payload(
                app=_app_name(acc),
                role=_safe_role_name(acc),
                name=_safe_name(acc),
                window_name=window_name,
            )
        )
        self._maybe_dump_subtree(force=True)

    def on_text_changed(self, event) -> None:
        acc = event.source
        if acc is None:
            return
        key = f"{id(acc)}:{event.type}"
        if not self._text_debounce.allow(key):
            return
        detail = None
        if getattr(event, "any_data", None) is not None:
            try:
                detail = str(event.any_data)
            except Exception:
                detail = None
        self._emit(
            text_changed_payload(
                app=_app_name(acc),
                role=_safe_role_name(acc),
                name=_safe_name(acc),
                change_type=str(event.type),
                detail=detail,
            )
        )

    def maybe_dump_subtree(self) -> None:
        """Periodic-timer entry point: dump only if the interval elapsed."""
        self._maybe_dump_subtree(force=False)

    def _maybe_dump_subtree(self, *, force: bool) -> None:
        if self._focused_window is None:
            return
        now = time.monotonic()
        if not force and (now - self._last_subtree_dump) < self._subtree_interval:
            return
        self._last_subtree_dump = now
        tree = build_subtree(
            _AccessibleAdapter(self._focused_window),
            max_depth=self._max_depth,
            max_nodes=self._max_nodes,
        )
        self._emit(
            subtree_payload(
                app=_app_name(self._focused_window),
                window_name=_safe_name(self._focused_window),
                tree=tree,
            )
        )


def run(
    *,
    capture_root,
    subtree_interval_seconds: float = 30.0,
    text_debounce_seconds: float = 2.0,
    max_depth: int = 40,
    max_nodes: int = 2000,
) -> int:
    # Deferred import: only this function (never imported at module load
    # time, so pure-logic tests never need a live AT-SPI2 bus or GI_TYPELIB_PATH
    # pointed at at-spi2-core) touches pyatspi/gi.
    import pyatspi
    from gi.repository import GLib

    daemon = A11yDaemon(
        capture_root=capture_root,
        subtree_interval_seconds=subtree_interval_seconds,
        text_debounce_seconds=text_debounce_seconds,
        max_depth=max_depth,
        max_nodes=max_nodes,
    )

    # Register both the legacy "focus:" event and the current AT-SPI2 spec
    # event ("object:state-changed:focused") -- toolkit AT-SPI2 bridges vary
    # in which one they actually emit.
    pyatspi.Registry.registerEventListener(daemon.on_focus, "focus:")
    pyatspi.Registry.registerEventListener(
        daemon.on_focus, "object:state-changed:focused"
    )
    pyatspi.Registry.registerEventListener(
        daemon.on_text_changed, "object:text-changed:insert"
    )
    pyatspi.Registry.registerEventListener(
        daemon.on_text_changed, "object:text-changed:delete"
    )

    def _on_timeout():
        daemon.maybe_dump_subtree()
        return True

    GLib.timeout_add_seconds(max(1, int(subtree_interval_seconds)), _on_timeout)

    logger.info("sinnix-capture-a11y: registered AT-SPI2 listeners, entering main loop")
    try:
        pyatspi.Registry.start()
    except KeyboardInterrupt:
        pass
    finally:
        pyatspi.Registry.stop()
    return 0
