"""Desktop actions: one Hyprland snapshot, screenshots as image blocks, AT-SPI
trees, and a discriminated operate union that always reports what is focused
afterwards."""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import ConfigDict, Field

from ..action import (
    OBSERVER_OPERATOR,
    OPERATOR_ONLY,
    Action,
    ActionResult,
    Example,
    MutationControls,
    RequestControls,
)
from ..content import Artifact, attach
from ..contracts import VerbFamily
from ..desktop import DesktopDiagnosticError, DesktopError
from ..locators import WindowLocator, window_ref
from ..results import ProtocolError
from ..schemas import GatewayModel

if TYPE_CHECKING:
    from ..runtime import Runtime

DESKTOP_REF = "sinnix://desktop/current"


def _owner_call(callback):
    """Translate owner failures into typed protocol errors."""
    try:
        return callback()
    except DesktopDiagnosticError as exc:
        raise ProtocolError(
            "unavailable",
            "desktop owner failed",
            details=dict(exc.response),
            diagnostic_refs=[
                f"sinnix://artifacts/{exc.response['diagnostic_artifact_id']}"
            ],
        ) from exc
    except DesktopError as exc:
        raise ProtocolError("owner_failed", str(exc)) from exc


class Point(GatewayModel):
    x: int
    y: int


class Geometry(GatewayModel):
    x: int
    y: int
    width: int
    height: int


class Window(GatewayModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    ref: str
    address: str
    title: str = ""
    class_: str = Field(default="", alias="class")
    initial_title: str = ""
    initial_class: str = ""
    pid: int | None = None
    workspace: str | None = None
    workspace_id: int | None = None
    monitor: int | None = None
    geometry: Geometry | None = None
    floating: bool = False
    fullscreen: int = 0
    mapped: bool = True
    hidden: bool = False
    focus_history_id: int | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


def _window(client: dict[str, Any]) -> Window:
    data = dict(client)
    at = data.pop("at", None)
    size = data.pop("size", None)
    workspace = data.pop("workspace", None) or {}
    geometry = None
    if (
        isinstance(at, list)
        and isinstance(size, list)
        and len(at) == 2
        and len(size) == 2
    ):
        geometry = Geometry(x=at[0], y=at[1], width=size[0], height=size[1])
    pid = data.pop("pid", None)
    known = {
        "address": str(data.pop("address", "")),
        "title": str(data.pop("title", "") or ""),
        "class": str(data.pop("class", "") or ""),
        "initial_title": str(data.pop("initialTitle", "") or ""),
        "initial_class": str(data.pop("initialClass", "") or ""),
        "pid": pid if isinstance(pid, int) and pid > 0 else None,
        "workspace": workspace.get("name") if isinstance(workspace, dict) else None,
        "workspace_id": workspace.get("id") if isinstance(workspace, dict) else None,
        "monitor": data.pop("monitor", None),
        "floating": bool(data.pop("floating", False)),
        "fullscreen": int(data.pop("fullscreen", 0) or 0),
        "mapped": bool(data.pop("mapped", True)),
        "hidden": bool(data.pop("hidden", False)),
        "focus_history_id": data.pop("focusHistoryID", None),
    }
    return Window(
        ref=window_ref(known["address"]), geometry=geometry, extra=data, **known
    )


class Monitor(GatewayModel):
    id: int | None = None
    name: str
    description: str = ""
    width: int | None = None
    height: int | None = None
    x: int | None = None
    y: int | None = None
    scale: float | None = None
    refresh_rate: float | None = None
    focused: bool = False
    active_workspace: str | None = None
    color_management_preset: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


def _monitor(raw: dict[str, Any]) -> Monitor:
    data = dict(raw)
    workspace = data.pop("activeWorkspace", None) or {}
    return Monitor(
        id=data.pop("id", None),
        name=str(data.pop("name", "")),
        description=str(data.pop("description", "") or ""),
        width=data.pop("width", None),
        height=data.pop("height", None),
        x=data.pop("x", None),
        y=data.pop("y", None),
        scale=data.pop("scale", None),
        refresh_rate=data.pop("refreshRate", None),
        focused=bool(data.pop("focused", False)),
        active_workspace=workspace.get("name") if isinstance(workspace, dict) else None,
        color_management_preset=data.pop("colorManagementPreset", None),
        extra=data,
    )


class Workspace(GatewayModel):
    id: int | None = None
    name: str
    monitor: str | None = None
    windows: int = 0
    has_fullscreen: bool = False
    last_window: str | None = None
    last_window_title: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)


def _workspace(raw: dict[str, Any]) -> Workspace:
    data = dict(raw)
    return Workspace(
        id=data.pop("id", None),
        name=str(data.pop("name", "")),
        monitor=data.pop("monitor", None),
        windows=int(data.pop("windows", 0) or 0),
        has_fullscreen=bool(data.pop("hasfullscreen", False)),
        last_window=data.pop("lastwindow", None) or None,
        last_window_title=str(data.pop("lastwindowtitle", "") or ""),
        extra=data,
    )


class SnapshotInput(RequestControls):
    include_windows: bool = Field(default=True, description="Include every client.")


class DesktopSnapshot(GatewayModel):
    ref: str = DESKTOP_REF
    generation: str = Field(description="Monotonic stamp of this observation.")
    monitors: list[Monitor]
    workspaces: list[Workspace]
    focused_monitor: str | None
    active_workspace: str | None
    active_window: Window | None
    windows: list[Window]
    cursor: Point | None = None
    affordances: list[str] = Field(default_factory=list)


def _snapshot(runtime: Runtime, inp: SnapshotInput) -> DesktopSnapshot:
    raw = _owner_call(
        lambda: runtime.desktop.invoke("hypr", ["snapshot"], mutating=False)
    )
    if not isinstance(raw, dict):
        raise ProtocolError("owner_failed", "hypr control did not return a snapshot")
    monitors = [_monitor(m) for m in raw.get("monitors", []) if isinstance(m, dict)]
    clients = [c for c in raw.get("clients", []) if isinstance(c, dict)]
    active = raw.get("active_window")
    active_ws = raw.get("active_workspace") or {}
    cursor = raw.get("cursor")
    return DesktopSnapshot(
        generation=str(raw.get("generation", "")),
        monitors=monitors,
        workspaces=[
            _workspace(w) for w in raw.get("workspaces", []) if isinstance(w, dict)
        ],
        focused_monitor=next((m.name for m in monitors if m.focused), None),
        active_workspace=active_ws.get("name") if isinstance(active_ws, dict) else None,
        active_window=_window(active)
        if isinstance(active, dict) and active.get("address")
        else None,
        windows=[_window(c) for c in clients] if inp.include_windows else [],
        cursor=Point(**cursor) if isinstance(cursor, dict) else None,
        affordances=["desktop.screenshot", "desktop.operate", "desktop.tree"],
    )


# ----------------------------------------------------------------- screenshot


class FullTarget(GatewayModel):
    kind: Literal["full"] = "full"


class MonitorTarget(GatewayModel):
    kind: Literal["monitor"] = "monitor"
    name: str = Field(min_length=1, max_length=128)


class WindowTarget(GatewayModel):
    kind: Literal["window"] = "window"
    window: WindowLocator


class ActiveWindowTarget(GatewayModel):
    kind: Literal["active_window"] = "active_window"


class RectTarget(GatewayModel):
    kind: Literal["rect"] = "rect"
    x: int
    y: int
    width: int = Field(ge=1)
    height: int = Field(ge=1)


ScreenshotTarget = (
    FullTarget | MonitorTarget | WindowTarget | ActiveWindowTarget | RectTarget
)


class ScreenshotInput(RequestControls):
    target: ScreenshotTarget = Field(
        default_factory=FullTarget,
        discriminator="kind",
        description="full = focused output; monitor, window, active_window or rect.",
    )
    fix_hdr: bool = Field(
        default=True,
        description="Also produce an SDR-corrected variant on HDR outputs.",
    )
    variant: Literal["auto", "raw", "corrected"] = Field(
        default="auto",
        description="Which file rides in the image block; auto prefers corrected.",
    )


class ScreenshotVariant(GatewayModel):
    artifact_id: str
    artifact_ref: str
    variant: Literal["raw", "corrected"]
    bytes: int
    content_type: str


class Screenshot(GatewayModel):
    ref: str = DESKTOP_REF
    target: dict[str, Any]
    window_ref: str | None = None
    geometry: Geometry | None = None
    artifact: Artifact
    artifact_ref: str
    variants: list[ScreenshotVariant]
    receipt: dict[str, Any]
    capture: dict[str, Any]
    affordances: list[str] = Field(default_factory=list)


def _screenshot(runtime: Runtime, inp: ScreenshotInput) -> ActionResult:
    target = inp.target
    geometry: Geometry | None = None
    window_ref_value: str | None = None
    output: str | None = None
    if isinstance(target, (WindowTarget, ActiveWindowTarget)):
        locator = (
            target.window
            if isinstance(target, WindowTarget)
            else WindowLocator(active=True)
        )
        client, window_ref_value = _owner_call(lambda: locator.resolve(runtime))
        geometry = _window(client).geometry
        if geometry is None:
            raise ProtocolError("owner_failed", "window has no geometry")
    elif isinstance(target, RectTarget):
        geometry = Geometry(
            x=target.x, y=target.y, width=target.width, height=target.height
        )
    elif isinstance(target, MonitorTarget):
        output = target.name
    description = {**target.model_dump(), "window_ref": window_ref_value}
    result = _owner_call(
        lambda: runtime.desktop.capture(
            fix_hdr=inp.fix_hdr,
            geometry=f"{geometry.x},{geometry.y} {geometry.width}x{geometry.height}"
            if geometry
            else None,
            output=output,
            target=description,
        )
    )
    variants = [
        ScreenshotVariant(
            artifact_id=item["artifact_id"],
            artifact_ref=f"sinnix://artifacts/{item['artifact_id']}",
            variant=item["variant"],
            bytes=item["bytes"],
            content_type=item["content_type"],
        )
        for item in result["artifacts"]
    ]
    preferred = None
    for wanted in ("corrected", "raw") if inp.variant != "raw" else ("raw",):
        preferred = next(
            (item for item in result["artifacts"] if item["variant"] == wanted), None
        )
        if preferred:
            break
    if preferred is None:
        raise ProtocolError(
            "not_found", f"no {inp.variant} capture variant was produced"
        )
    artifact, blocks = attach(
        Path(preferred["path"]),
        ref=f"sinnix://artifacts/{preferred['artifact_id']}",
        media_type=preferred["content_type"],
    )
    return ActionResult(
        Screenshot(
            target=description,
            window_ref=window_ref_value,
            geometry=geometry,
            artifact=artifact,
            artifact_ref=artifact.ref,
            variants=variants,
            receipt=result["receipt"],
            capture=result["capture"],
            affordances=["desktop.snapshot", "desktop.operate", "artifacts.read"],
        ),
        blocks=blocks,
    )


# ----------------------------------------------------------------------- tree


class TreeInput(RequestControls):
    window: WindowLocator | None = Field(
        default=None, description="Defaults to the active window."
    )
    max_depth: int = Field(default=40, ge=1, le=200)
    max_nodes: int = Field(default=2_000, ge=1, le=50_000)


class TreeNode(GatewayModel):
    role: str
    name: str
    text: str | None = None
    children: list[TreeNode] = Field(default_factory=list)
    truncated: Literal["max_depth", "max_nodes"] | None = None


class AccessibleTree(GatewayModel):
    ref: str = DESKTOP_REF
    window_ref: str
    pid: int | None
    application: str | None
    nodes: int
    root: TreeNode | None
    affordances: list[str] = Field(default_factory=list)


def _walk(
    node: Any, *, max_depth: int, max_nodes: int
) -> tuple[dict[str, Any] | None, int]:
    counter = {"n": 0}

    def text_of(acc: Any) -> str | None:
        try:
            return acc.queryText().getText(0, -1) or None
        except Exception:
            return None

    def walk(acc: Any, depth: int) -> dict[str, Any] | None:
        if counter["n"] >= max_nodes:
            return None
        counter["n"] += 1
        entry: dict[str, Any] = {
            "role": acc.getRoleName() or "",
            "name": acc.name or "",
        }
        text = text_of(acc)
        if text:
            entry["text"] = text
        if depth >= max_depth:
            entry["truncated"] = "max_depth"
            return entry
        children = []
        for index in range(acc.getChildCount()):
            if counter["n"] >= max_nodes:
                entry["truncated"] = "max_nodes"
                break
            child = acc.getChildAtIndex(index)
            child_entry = walk(child, depth + 1) if child is not None else None
            if child_entry is None:
                if child is not None:
                    entry["truncated"] = "max_nodes"
                    break
                continue
            children.append(child_entry)
        if children:
            entry["children"] = children
        return entry

    return walk(node, 0), counter["n"]


def _tree(runtime: Runtime, inp: TreeInput) -> AccessibleTree:
    from ..capabilities import Capability

    runtime.principal.require(Capability.DESKTOP_READ)
    locator = inp.window or WindowLocator(active=True)
    client, ref = _owner_call(lambda: locator.resolve(runtime))
    pid = client.get("pid")
    try:
        import pyatspi  # type: ignore[import-not-found]
    except Exception as exc:  # ImportError or GI initialisation failure
        raise ProtocolError(
            "unavailable",
            "AT-SPI bindings (pyatspi) are not importable in the gateway environment",
            details={"window_ref": ref, "pid": pid, "reason": repr(exc)},
        ) from exc
    desktop = pyatspi.Registry.getDesktop(0)
    application = None
    for index in range(desktop.getChildCount()):
        app = desktop.getChildAtIndex(index)
        try:
            if app is not None and app.get_process_id() == pid:
                application = app
                break
        except Exception:
            continue
    if application is None:
        raise ProtocolError(
            "not_found",
            "no AT-SPI application exposes this window's pid",
            details={"window_ref": ref, "pid": pid},
        )
    root, nodes = _walk(application, max_depth=inp.max_depth, max_nodes=inp.max_nodes)
    return AccessibleTree(
        window_ref=ref,
        pid=pid,
        application=application.name or None,
        nodes=nodes,
        root=TreeNode.model_validate(root) if root else None,
        affordances=["desktop.operate", "desktop.screenshot"],
    )


# -------------------------------------------------------------------- operate


class FocusOp(GatewayModel):
    operation: Literal["focus"] = "focus"
    window: WindowLocator


class LaunchOp(GatewayModel):
    operation: Literal["launch"] = "launch"
    command: str = Field(
        min_length=1, max_length=8_192, description="Shell command line."
    )
    wait_for: WindowLocator | None = Field(
        default=None, description="Wait for this window to appear after launching."
    )
    timeout_seconds: int = Field(default=15, ge=1, le=120)


class CloseOp(GatewayModel):
    operation: Literal["close"] = "close"
    window: WindowLocator


class MoveOp(GatewayModel):
    operation: Literal["move"] = "move"
    window: WindowLocator
    x: int
    y: int


class ResizeOp(GatewayModel):
    operation: Literal["resize"] = "resize"
    window: WindowLocator
    width: int = Field(ge=1)
    height: int = Field(ge=1)


class ClickOp(GatewayModel):
    operation: Literal["click"] = "click"
    x: int
    y: int
    button: Literal["left", "right", "middle"] = "left"


class DoubleClickOp(GatewayModel):
    operation: Literal["double_click"] = "double_click"
    x: int
    y: int


class RightClickOp(GatewayModel):
    operation: Literal["right_click"] = "right_click"
    x: int
    y: int


class DragOp(GatewayModel):
    operation: Literal["drag"] = "drag"
    from_x: int
    from_y: int
    to_x: int
    to_y: int


class ScrollOp(GatewayModel):
    operation: Literal["scroll"] = "scroll"
    x: int | None = Field(default=None, description="Move the cursor here first.")
    y: int | None = None
    dx: int = 0
    dy: int = 0


class TypeOp(GatewayModel):
    operation: Literal["type"] = "type"
    window: WindowLocator
    text: str = Field(min_length=1, max_length=8_192)
    delay_ms: int = Field(default=0, ge=0, le=1_000)


class PasteOp(GatewayModel):
    operation: Literal["paste"] = "paste"
    window: WindowLocator
    text: str = Field(min_length=1, max_length=65_536)
    enter: bool = False


class KeyOp(GatewayModel):
    operation: Literal["key"] = "key"
    key: str = Field(
        min_length=1, max_length=128, description="XKB key name, e.g. Return."
    )
    mods: str = Field(default="", max_length=128, description="e.g. CTRL, SUPER SHIFT")
    window: WindowLocator | None = None


class KeyStateOp(GatewayModel):
    operation: Literal["key_state"] = "key_state"
    key: str = Field(min_length=1, max_length=128)
    mods: str = Field(default="", max_length=128)
    state: Literal["down", "repeat", "up"]
    window: WindowLocator


class WaitWindowOp(GatewayModel):
    operation: Literal["wait_window"] = "wait_window"
    window: WindowLocator
    until: Literal["present", "absent"] = "present"
    timeout_seconds: int = Field(default=15, ge=1, le=300)


class OpenOp(GatewayModel):
    operation: Literal["open"] = "open"
    uri: str = Field(
        min_length=1, max_length=8_192, description="URL or path for xdg-open."
    )


class DispatchOp(GatewayModel):
    operation: Literal["dispatch"] = "dispatch"
    expression: str = Field(
        min_length=1,
        max_length=8_192,
        description="Escape hatch: a Hyprland Lua dispatcher expression, e.g. hl.dsp.focus({ workspace = 3 }).",
    )


DesktopOp = (
    FocusOp
    | LaunchOp
    | CloseOp
    | MoveOp
    | ResizeOp
    | ClickOp
    | DoubleClickOp
    | RightClickOp
    | DragOp
    | ScrollOp
    | TypeOp
    | PasteOp
    | KeyOp
    | KeyStateOp
    | WaitWindowOp
    | OpenOp
    | DispatchOp
)


class OperateInput(MutationControls):
    action: DesktopOp = Field(discriminator="operation")


class OperateResult(GatewayModel):
    ref: str = DESKTOP_REF
    operation: str
    window_ref: str | None = Field(default=None, description="Resolved target window.")
    window: Window | None = None
    result: Any = None
    waited_seconds: float | None = None
    active_window: Window | None = Field(description="Observed after the operation.")
    affordances: list[str] = Field(default_factory=list)


def _selector(
    window: WindowLocator, runtime: Runtime
) -> tuple[str, str, dict[str, Any]]:
    client, ref = _owner_call(lambda: window.resolve(runtime))
    return f"address:{client['address']}", ref, client


def _active(runtime: Runtime) -> Window | None:
    raw = _owner_call(lambda: runtime.desktop.read("active_window"))["result"]
    return _window(raw) if isinstance(raw, dict) and raw.get("address") else None


def _pointer(runtime: Runtime, arguments: list[str]) -> Any:
    raw = _owner_call(
        lambda: runtime.desktop.invoke("hypr", ["pointer", *arguments], mutating=True)
    )
    if isinstance(raw, dict) and raw.get("available") is False:
        raise ProtocolError(
            "unavailable",
            str(raw.get("reason", "pointer control unavailable")),
            details=raw,
        )
    return raw


def _wait_window(
    runtime: Runtime, locator: WindowLocator, until: str, timeout: int
) -> tuple[dict[str, Any] | None, str | None, float]:
    started = time.monotonic()
    while True:
        try:
            client, ref = locator.resolve(runtime)
            present = True
        except ProtocolError as exc:
            if exc.code != "not_found":
                raise
            client, ref, present = None, None, False
        if present == (until == "present"):
            return client, ref, round(time.monotonic() - started, 3)
        if time.monotonic() - started >= timeout:
            raise ProtocolError(
                "deadline",
                f"window did not become {until} within {timeout}s",
                details={
                    "locator": locator.model_dump(by_alias=True, exclude_none=True)
                },
            )
        time.sleep(0.2)


def _operate(runtime: Runtime, inp: OperateInput) -> OperateResult:
    op = inp.action

    def hypr(args: list[str]) -> Any:
        return _owner_call(lambda: runtime.desktop.invoke("hypr", args, mutating=True))

    def legacy(name: str, args: Any) -> Any:
        return _owner_call(lambda: runtime.desktop.action(name, args))

    window_ref_value: str | None = None
    client: dict[str, Any] | None = None
    result: Any = None
    waited: float | None = None
    if isinstance(op, FocusOp):
        selector, window_ref_value, client = _selector(op.window, runtime)
        result = legacy("focus_window", {"window": selector})["result"]
    elif isinstance(op, LaunchOp):
        result = hypr(["exec", op.command])
        if op.wait_for is not None:
            client, window_ref_value, waited = _wait_window(
                runtime, op.wait_for, "present", op.timeout_seconds
            )
    elif isinstance(op, (CloseOp, MoveOp, ResizeOp)):
        selector, window_ref_value, client = _selector(op.window, runtime)
        extra = {
            "close": [],
            "move": [str(getattr(op, "x", 0)), str(getattr(op, "y", 0))],
            "resize": [str(getattr(op, "width", 0)), str(getattr(op, "height", 0))],
        }[op.operation]
        result = hypr(["window", selector, op.operation, *extra])
        if isinstance(op, CloseOp):
            _, _, waited = _wait_window(
                runtime, WindowLocator(address=client["address"]), "absent", 10
            )
            client = None
    elif isinstance(op, (ClickOp, DoubleClickOp, RightClickOp)):
        _pointer(runtime, ["move", str(op.x), str(op.y)])
        button = (
            "right" if isinstance(op, RightClickOp) else getattr(op, "button", "left")
        )
        result = _pointer(
            runtime,
            ["click", button, *(["--double"] if isinstance(op, DoubleClickOp) else [])],
        )
    elif isinstance(op, DragOp):
        result = _pointer(
            runtime,
            ["drag", str(op.from_x), str(op.from_y), str(op.to_x), str(op.to_y)],
        )
    elif isinstance(op, ScrollOp):
        if op.x is not None and op.y is not None:
            _pointer(runtime, ["move", str(op.x), str(op.y)])
        result = _pointer(runtime, ["scroll", str(op.dx), str(op.dy)])
    elif isinstance(op, TypeOp):
        selector, window_ref_value, client = _selector(op.window, runtime)
        result = hypr(
            ["type", selector, "--text", op.text, "--delay-ms", str(op.delay_ms)]
        )
    elif isinstance(op, PasteOp):
        selector, window_ref_value, client = _selector(op.window, runtime)
        result = legacy(
            "paste", {"window": selector, "text": op.text, "enter": op.enter}
        )["result"]
    elif isinstance(op, KeyOp):
        arguments: dict[str, Any] = {"mods": op.mods or " ", "key": op.key}
        if op.window is not None:
            arguments["window"], window_ref_value, client = _selector(
                op.window, runtime
            )
        result = legacy("send_shortcut", arguments)["result"]
    elif isinstance(op, KeyStateOp):
        selector, window_ref_value, client = _selector(op.window, runtime)
        result = legacy(
            "send_keystate",
            {
                "mods": op.mods or " ",
                "key": op.key,
                "state": op.state,
                "window": selector,
            },
        )["result"]
    elif isinstance(op, WaitWindowOp):
        client, window_ref_value, waited = _wait_window(
            runtime, op.window, op.until, op.timeout_seconds
        )
    elif isinstance(op, OpenOp):
        result = hypr(["open", op.uri])
    elif isinstance(op, DispatchOp):
        result = legacy("dispatch", {"dispatcher": op.expression, "args": []})["result"]
    return OperateResult(
        operation=op.operation,
        window_ref=window_ref_value,
        window=_window(client) if client else None,
        result=result,
        waited_seconds=waited,
        active_window=_active(runtime),
        affordances=["desktop.snapshot", "desktop.screenshot", "desktop.operate"],
    )


ACTIONS: tuple[Action, ...] = (
    Action(
        name="desktop.snapshot",
        family=VerbFamily.STATUS,
        owner="desktop",
        summary="One observation of the desktop: monitors, workspaces, focus, every window with geometry, and a generation stamp.",
        Input=SnapshotInput,
        Output=DesktopSnapshot,
        handler=_snapshot,
        principals=OBSERVER_OPERATOR,
        resource_kinds=("desktop",),
        affordances=("desktop.screenshot", "desktop.operate", "desktop.tree"),
        aliases=(
            "windows",
            "clients",
            "workspaces",
            "monitors",
            "active window",
            "what is on screen",
        ),
        examples=(Example(title="Observe the desktop", input={}),),
    ),
    Action(
        name="desktop.screenshot",
        family=VerbFamily.QUERY,
        owner="desktop",
        summary="Capture the focused output, one monitor, one window, or a rectangle; the PNG rides in an image block and is retained as an attested artifact.",
        Input=ScreenshotInput,
        Output=Screenshot,
        handler=_screenshot,
        principals=OBSERVER_OPERATOR,
        resource_kinds=("desktop", "artifact"),
        affordances=("desktop.snapshot", "desktop.operate", "artifacts.read"),
        aliases=(
            "screen capture",
            "grab screen",
            "picture of screen",
            "capture window",
        ),
        documentation="full captures the focused output through the HDR-aware screenshot owner; window/rect/monitor targets capture with grim. On HDR outputs a corrected SDR variant is produced and preferred for the image block.",
        examples=(
            Example(title="Focused output", input={}),
            Example(
                title="The active window", input={"target": {"kind": "active_window"}}
            ),
            Example(
                title="A window by class",
                input={"target": {"kind": "window", "window": {"class": "kitty"}}},
            ),
        ),
    ),
    Action(
        name="desktop.tree",
        family=VerbFamily.QUERY,
        owner="desktop",
        summary="AT-SPI accessible subtree of one window (bounded by depth and node count).",
        Input=TreeInput,
        Output=AccessibleTree,
        handler=_tree,
        principals=OBSERVER_OPERATOR,
        resource_kinds=("desktop",),
        affordances=("desktop.operate", "desktop.screenshot"),
        aliases=("accessibility tree", "a11y", "widgets", "ui elements"),
        documentation="Fails unavailable when the pyatspi bindings are absent from the gateway environment; Chromium apps expose a tree only when launched with accessibility forced on.",
        examples=(Example(title="Active window tree", input={"max_depth": 10}),),
        failure_codes=frozenset(
            {"unavailable", "not_found", "conflict", "invalid_request", "owner_failed"}
        ),
    ),
    Action(
        name="desktop.operate",
        family=VerbFamily.OPERATE,
        owner="desktop",
        summary="Focus, launch, close, move, resize, click, drag, scroll, type, paste, key chords, wait for a window, open a URI, or dispatch raw Hyprland; every call reports the active window afterwards.",
        Input=OperateInput,
        Output=OperateResult,
        handler=_operate,
        principals=OPERATOR_ONLY,
        resource_kinds=("desktop",),
        affordances=("desktop.snapshot", "desktop.screenshot", "desktop.tree"),
        aliases=(
            "focus window",
            "launch app",
            "close window",
            "click",
            "type text",
            "press key",
            "xdg-open",
            "hyprctl dispatch",
        ),
        documentation="Pointer clicks, drags and scrolls need a virtual pointer tool (ydotool) on the host and fail unavailable without one; cursor moves always work. Window targets are natural locators; ambiguity returns candidates.",
        examples=(
            Example(
                title="Focus a window by title",
                input={
                    "action": {
                        "operation": "focus",
                        "window": {"title_contains": "Codex"},
                    },
                    "idempotency_key": "focus-1",
                },
            ),
            Example(
                title="Launch and wait",
                input={
                    "action": {
                        "operation": "launch",
                        "command": "kitty --class scratch",
                        "wait_for": {"class": "scratch"},
                    },
                    "idempotency_key": "launch-1",
                },
            ),
            Example(
                title="Ctrl+L in the active window",
                input={
                    "action": {"operation": "key", "mods": "CTRL", "key": "L"},
                    "idempotency_key": "key-1",
                },
            ),
        ),
    ),
)
