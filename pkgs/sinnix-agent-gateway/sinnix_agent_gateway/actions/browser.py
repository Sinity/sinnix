"""Browser actions over the operator's Chrome. Every page is listable; only
pages the gateway opened on the hidden agent workspace are readable in depth,
capturable, or mutable."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field, model_validator

from ..action import (
    OBSERVER_OPERATOR,
    OPERATOR_ONLY,
    Action,
    ActionResult,
    Example,
    MutationControls,
    RequestControls,
)
from ..browser import BrowserDiagnosticError, BrowserError
from ..content import Artifact, attach
from ..contracts import VerbFamily
from ..locators import FileLocator, PageLocator, page_ref
from ..results import ProtocolError
from ..schemas import GatewayModel
from .files import _authorized

if TYPE_CHECKING:
    from ..runtime import Runtime

WORKSPACE_REF = "sinnix://browser/agent-workspace"


def _owner_call(callback):
    try:
        return callback()
    except BrowserDiagnosticError as exc:
        raise ProtocolError(
            "unavailable",
            "browser owner failed",
            details=dict(exc.response),
            diagnostic_refs=[
                f"sinnix://artifacts/{exc.response['diagnostic_artifact_id']}"
            ],
        ) from exc
    except BrowserError as exc:
        raise ProtocolError(
            "policy_denied" if "gateway-created" in str(exc) else "owner_failed",
            str(exc),
        ) from exc


class Page(GatewayModel):
    ref: str
    page_id: str
    title: str = ""
    url: str = ""
    type: str = "page"
    owned: bool = Field(
        description="Opened by the gateway; the only kind that can be read, captured or operated."
    )
    affordances: list[str] = Field(default_factory=list)


def _listing(runtime: Runtime, *, pages_only: bool = True) -> list[dict[str, Any]]:
    verb = "list-tabs" if pages_only else "list"
    raw = _owner_call(lambda: runtime.browser.invoke([verb, "--json"], mutating=False))
    if not isinstance(raw, list):
        raise ProtocolError("owner_failed", "chrome control did not return a page list")
    owned = runtime.browser.owned_page_ids()
    return [
        {**item, "owned": item.get("id") in owned}
        for item in raw
        if isinstance(item, dict)
    ]


def _page(item: dict[str, Any]) -> Page:
    owned = bool(item.get("owned"))
    return Page(
        ref=page_ref(str(item.get("id"))),
        page_id=str(item.get("id")),
        title=str(item.get("title", "") or ""),
        url=str(item.get("url", "") or ""),
        type=str(item.get("type", "page") or "page"),
        owned=owned,
        affordances=["browser.page", "browser.screenshot", "browser.operate"]
        if owned
        else [],
    )


def _resolve_owned(
    runtime: Runtime, locator: PageLocator
) -> tuple[dict[str, Any], str]:
    """Resolve among gateway-owned pages only; an operator tab is never a target."""
    pages = _listing(runtime)
    owned = [p for p in pages if p["owned"]]
    try:
        page, ref = locator.resolve(owned)
    except ProtocolError as exc:
        if exc.code == "not_found":
            try:
                locator.resolve(pages)
            except ProtocolError:
                raise exc from None
            raise ProtocolError(
                "policy_denied",
                "page exists but is an operator tab; only gateway-opened pages can be read in depth or operated",
                details=exc.details,
            ) from None
        raise
    return page, ref


class PagesInput(RequestControls):
    include: Literal["pages", "all_targets"] = Field(
        default="pages",
        description="all_targets also lists workers, extensions and service workers.",
    )


class PageListing(GatewayModel):
    workspace_ref: str = WORKSPACE_REF
    pages: list[Page]
    owned_refs: list[str]
    affordances: list[str] = Field(default_factory=list)


def _pages(runtime: Runtime, inp: PagesInput) -> PageListing:
    pages = [
        _page(item) for item in _listing(runtime, pages_only=inp.include == "pages")
    ]
    return PageListing(
        pages=pages,
        owned_refs=[p.ref for p in pages if p.owned],
        affordances=["browser.page", "browser.operate", "browser.screenshot"],
    )


# ----------------------------------------------------------------------- page


class Rect(GatewayModel):
    x: int
    y: int
    w: int
    h: int


class Element(GatewayModel):
    ref: str = Field(
        description="Element ref valid for this page generation; use it in browser.operate."
    )
    tag: str
    type: str | None = None
    role: str | None = None
    name: str = ""
    text: str = ""
    href: str | None = None
    value: str | None = None
    disabled: bool = False
    rect: Rect | None = None


class Link(GatewayModel):
    text: str = ""
    href: str
    ref: str | None = None


class FormField(GatewayModel):
    ref: str | None = None
    tag: str
    type: str | None = None
    name: str | None = None
    value: str = ""


class Form(GatewayModel):
    index: int
    id: str | None = None
    name: str | None = None
    action: str | None = None
    method: str | None = None
    ref: str | None = None
    fields: list[FormField] = Field(default_factory=list)


class PageSnapshot(GatewayModel):
    ref: str
    page_id: str
    generation: int = Field(description="Element refs are scoped to this generation.")
    url: str
    title: str
    ready_state: str
    text: str
    text_truncated: bool
    elements: list[Element]
    links: list[Link]
    forms: list[Form]
    affordances: list[str] = Field(default_factory=list)


class PageInput(RequestControls):
    target: PageLocator
    max_text: int = Field(default=20_000, ge=0, le=1_000_000)
    max_elements: int = Field(default=300, ge=1, le=5_000)


def _snapshot(
    runtime: Runtime, page_id: str, max_text: int, max_elements: int
) -> dict[str, Any]:
    raw = _owner_call(
        lambda: runtime.browser.invoke(
            [
                "page-snapshot",
                page_id,
                "--max-text",
                str(max_text),
                "--max-elements",
                str(max_elements),
            ],
            mutating=False,
        )
    )
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError as exc:
            raise ProtocolError("owner_failed", "page snapshot is not JSON") from exc
    if not isinstance(raw, dict):
        raise ProtocolError("owner_failed", "page snapshot is malformed")
    return raw


def _page_snapshot(runtime: Runtime, inp: PageInput) -> PageSnapshot:
    page, ref = _resolve_owned(runtime, inp.target)
    raw = _snapshot(runtime, page["id"], inp.max_text, inp.max_elements)
    return PageSnapshot(
        ref=ref,
        page_id=page["id"],
        generation=int(raw.get("generation", 0)),
        url=str(raw.get("url", "")),
        title=str(raw.get("title", "")),
        ready_state=str(raw.get("ready_state", "")),
        text=str(raw.get("text", "")),
        text_truncated=bool(raw.get("text_truncated", False)),
        elements=[
            Element.model_validate(
                {**e, "name": e.get("name") or "", "text": e.get("text") or ""}
            )
            for e in raw.get("elements", [])
        ],
        links=[
            Link.model_validate({**link, "text": link.get("text") or ""})
            for link in raw.get("links", [])
        ],
        forms=[
            Form.model_validate(
                {
                    **f,
                    "fields": [
                        {**x, "value": x.get("value") or ""}
                        for x in f.get("fields", [])
                    ],
                }
            )
            for f in raw.get("forms", [])
        ],
        affordances=["browser.operate", "browser.screenshot"],
    )


# ----------------------------------------------------------------- screenshot


class BrowserScreenshotInput(RequestControls):
    target: PageLocator
    image_format: Literal["png", "jpeg"] = "png"
    full_page: bool = False
    quality: int | None = Field(default=None, ge=1, le=100)


class BrowserScreenshot(GatewayModel):
    ref: str
    page_id: str
    artifact: Artifact
    artifact_ref: str
    receipt: dict[str, Any]
    capture: dict[str, Any]
    affordances: list[str] = Field(default_factory=list)


def _screenshot(runtime: Runtime, inp: BrowserScreenshotInput) -> ActionResult:
    page, ref = _resolve_owned(runtime, inp.target)
    result = _owner_call(
        lambda: runtime.browser.capture(
            page["id"], inp.image_format, inp.full_page, inp.quality
        )
    )
    artifact_id = result["artifact_id"]
    metadata = runtime.artifacts._metadata(artifact_id)
    artifact, blocks = attach(
        Path(metadata["source"]),
        ref=f"sinnix://artifacts/{artifact_id}",
        media_type=result["artifact"]["content_type"],
    )
    return ActionResult(
        BrowserScreenshot(
            ref=ref,
            page_id=page["id"],
            artifact=artifact,
            artifact_ref=artifact.ref,
            receipt=result["receipt"],
            capture=result["capture"],
            affordances=["browser.page", "browser.operate", "artifacts.read"],
        ),
        blocks=blocks,
    )


# -------------------------------------------------------------------- operate


class ElementTarget(GatewayModel):
    """An element by snapshot ref or CSS selector."""

    ref: str | None = Field(default=None, pattern=r"^g\d+e\d+$")
    selector: str | None = Field(default=None, min_length=1, max_length=8_192)

    @model_validator(mode="after")
    def exactly_one(self) -> ElementTarget:
        if (self.ref is None) == (self.selector is None):
            raise ValueError("give exactly one of ref or selector")
        return self

    def css(self) -> str:
        return (
            self.selector
            if self.selector is not None
            else f'[data-sinnix-ref="{self.ref}"]'
        )


class NavigateOp(GatewayModel):
    operation: Literal["navigate"] = "navigate"
    url: str = Field(min_length=1, max_length=8_192)


class BackOp(GatewayModel):
    operation: Literal["back"] = "back"


class ForwardOp(GatewayModel):
    operation: Literal["forward"] = "forward"


class ReloadOp(GatewayModel):
    operation: Literal["reload"] = "reload"


class NewOp(GatewayModel):
    operation: Literal["new"] = "new"
    url: str | None = Field(default=None, max_length=8_192)


class CloseOp(GatewayModel):
    operation: Literal["close"] = "close"


class FocusOp(GatewayModel):
    operation: Literal["focus"] = "focus"


class ClickOp(GatewayModel):
    operation: Literal["click"] = "click"
    element: ElementTarget


class FillOp(GatewayModel):
    operation: Literal["fill"] = "fill"
    element: ElementTarget
    value: str = Field(max_length=64_000)


class SubmitOp(GatewayModel):
    operation: Literal["submit"] = "submit"
    element: ElementTarget | None = Field(
        default=None,
        description="A form or a field inside it; default: the first form.",
    )


class ScrollOp(GatewayModel):
    operation: Literal["scroll"] = "scroll"
    element: ElementTarget | None = Field(
        default=None, description="Scroll this element into view instead of by offset."
    )
    dx: int = 0
    dy: int = 0


class KeyOp(GatewayModel):
    operation: Literal["key"] = "key"
    key: str = Field(
        min_length=1,
        max_length=32,
        description="Enter, Tab, Escape, ArrowDown, ... or one character.",
    )
    mods: list[Literal["ctrl", "shift", "alt", "meta"]] = Field(default_factory=list)


class WaitOp(GatewayModel):
    operation: Literal["wait"] = "wait"
    for_: Literal["selector", "text", "navigation"] = Field(alias="for")
    value: str | None = Field(
        default=None,
        max_length=8_192,
        description="Selector or text; for navigation, the URL fragment to reach (optional).",
    )
    timeout_seconds: int = Field(default=30, ge=1, le=300)

    model_config = {"extra": "forbid", "populate_by_name": True}


class DownloadOp(GatewayModel):
    operation: Literal["download"] = "download"
    url: str = Field(min_length=1, max_length=8_192)
    destination: FileLocator | None = Field(
        default=None, description="Host file; default: a gateway capture artifact."
    )


class UploadOp(GatewayModel):
    operation: Literal["upload"] = "upload"
    element: ElementTarget
    files: list[FileLocator] = Field(min_length=1, max_length=32)


class EvaluateOp(GatewayModel):
    operation: Literal["evaluate"] = "evaluate"
    javascript: str = Field(min_length=1, max_length=64_000)
    until_truthy: bool = Field(
        default=False, description="Poll the expression until truthy."
    )
    timeout_seconds: int = Field(default=30, ge=1, le=300)


BrowserOp = (
    NavigateOp
    | BackOp
    | ForwardOp
    | ReloadOp
    | NewOp
    | CloseOp
    | FocusOp
    | ClickOp
    | FillOp
    | SubmitOp
    | ScrollOp
    | KeyOp
    | WaitOp
    | DownloadOp
    | UploadOp
    | EvaluateOp
)


class BrowserOperateInput(MutationControls):
    target: PageLocator | None = Field(
        default=None, description="Required for every operation except new."
    )
    action: BrowserOp = Field(discriminator="operation")

    @model_validator(mode="after")
    def target_rule(self) -> BrowserOperateInput:
        if (self.action.operation == "new") != (self.target is None):
            raise ValueError("new takes no target; every other operation requires one")
        return self


class BrowserOperateResult(GatewayModel):
    ref: str
    page_id: str | None
    operation: str
    result: Any = None
    page: Page | None = Field(default=None, description="Observed after the operation.")
    artifact: Artifact | None = None
    artifact_ref: str | None = None
    affordances: list[str] = Field(default_factory=list)


def _text(value: Any) -> Any:
    """Wrapper verbs print one line; strip the newline so results compare cleanly."""
    return value.rstrip("\n") if isinstance(value, str) else value


def _js(runtime: Runtime, page_id: str, expression: str) -> Any:
    return _text(
        _owner_call(
            lambda: runtime.browser.action(
                "evaluate", {"page_id": page_id, "javascript": expression}
            )
        )["result"]
    )


def _await(runtime: Runtime, page_id: str, expression: str, timeout: int) -> Any:
    try:
        return _text(
            _owner_call(
                lambda: runtime.browser.action(
                    "await",
                    {
                        "page_id": page_id,
                        "javascript": expression,
                        "timeout_seconds": timeout,
                    },
                )
            )["result"]
        )
    except ProtocolError as exc:
        if exc.code == "unavailable" and exc.details.get("exit_status") == 124:
            raise ProtocolError(
                "deadline", f"condition not met within {timeout}s"
            ) from exc
        raise


def _element_js(target: ElementTarget) -> str:
    return f"document.querySelector({json.dumps(target.css())})"


def _observe(runtime: Runtime, page_id: str) -> Page | None:
    return next(
        (
            _page(p)
            for p in _listing(runtime, pages_only=False)
            if p.get("id") == page_id
        ),
        None,
    )


def _operate(runtime: Runtime, inp: BrowserOperateInput) -> ActionResult:
    op = inp.action
    result: Any = None
    artifact: Artifact | None = None
    blocks: list[Any] = []
    if isinstance(op, NewOp):
        arguments = {"url": op.url} if op.url else {}
        created = _owner_call(
            lambda: runtime.browser.action("agent_window", arguments)
        )["target"]
        page_id = str(created["id"])
        return ActionResult(
            BrowserOperateResult(
                ref=page_ref(page_id),
                page_id=page_id,
                operation="new",
                result=created,
                page=_observe(runtime, page_id),
                affordances=["browser.page", "browser.operate", "browser.screenshot"],
            )
        )
    page, ref = _resolve_owned(runtime, inp.target)
    page_id = str(page["id"])

    def act(name: str, **arguments: Any) -> str:
        return _text(
            _owner_call(
                lambda: runtime.browser.action(name, {"page_id": page_id, **arguments})
            )["result"]
        )

    if isinstance(op, NavigateOp):
        result = act("navigate", url=op.url)
    elif isinstance(op, BackOp):
        result = _js(runtime, page_id, "history.back(); 'ok'")
    elif isinstance(op, ForwardOp):
        result = _js(runtime, page_id, "history.forward(); 'ok'")
    elif isinstance(op, ReloadOp):
        result = act("reload")
    elif isinstance(op, CloseOp):
        result = act("close")
    elif isinstance(op, FocusOp):
        result = _text(
            _owner_call(
                lambda: runtime.browser.invoke(["activate", page_id], mutating=True)
            )
        )
    elif isinstance(op, ClickOp):
        result = act("click", selector=op.element.css())
    elif isinstance(op, FillOp):
        result = act("fill_form", selector=op.element.css(), value=op.value)
        if result == "NOT_FOUND":
            raise ProtocolError(
                "not_found",
                "no element matches the target",
                details={"selector": op.element.css()},
            )
    elif isinstance(op, SubmitOp):
        node = _element_js(op.element) if op.element else "document.forms[0]"
        result = _js(
            runtime,
            page_id,
            f"(() => {{ const n = {node}; if (!n) return 'NOT_FOUND'; const f = n.tagName === 'FORM' ? n : n.form || n.closest('form'); if (!f) return 'NO_FORM'; f.requestSubmit ? f.requestSubmit() : f.submit(); return 'OK'; }})()",
        )
        if result in {"NOT_FOUND", "NO_FORM"}:
            raise ProtocolError(
                "not_found", "no form matches the target", details={"result": result}
            )
    elif isinstance(op, ScrollOp):
        if op.element:
            result = _js(
                runtime,
                page_id,
                f"(() => {{ const n = {_element_js(op.element)}; if (!n) return 'NOT_FOUND'; n.scrollIntoView({{block: 'center'}}); return 'OK'; }})()",
            )
            if result == "NOT_FOUND":
                raise ProtocolError(
                    "not_found",
                    "no element matches the target",
                    details={"selector": op.element.css()},
                )
        else:
            result = _js(
                runtime,
                page_id,
                f"window.scrollBy({op.dx}, {op.dy}); [window.scrollX, window.scrollY]",
            )
    elif isinstance(op, KeyOp):
        arguments = ["key", page_id, "--key", op.key]
        for mod in op.mods:
            arguments.extend(["--mod", mod])
        result = _owner_call(lambda: runtime.browser.invoke(arguments, mutating=True))
    elif isinstance(op, WaitOp):
        if op.for_ == "selector":
            if not op.value:
                raise ProtocolError("invalid_request", "wait for selector needs value")
            result = act(
                "wait_selector", selector=op.value, timeout_seconds=op.timeout_seconds
            )
        elif op.for_ == "text":
            if not op.value:
                raise ProtocolError("invalid_request", "wait for text needs value")
            result = _await(
                runtime,
                page_id,
                f"(document.body && document.body.innerText.includes({json.dumps(op.value)}))",
                op.timeout_seconds,
            )
        else:
            condition = "document.readyState === 'complete'"
            if op.value:
                condition += f" && location.href.includes({json.dumps(op.value)})"
            result = _await(
                runtime, page_id, f"({condition}) && location.href", op.timeout_seconds
            )
    elif isinstance(op, DownloadOp):
        if op.destination is not None:
            destination = _authorized(runtime, op.destination, existing=False)
            destination.parent.mkdir(parents=True, exist_ok=True)
            capture_dir = None
        else:
            capture_dir = runtime.config.state_dir / "captures" / uuid.uuid4().hex
            capture_dir.mkdir(mode=0o700, parents=True)
            destination = capture_dir / "download.bin"
        result = _owner_call(
            lambda: runtime.browser.invoke(
                ["download", page_id, "--url", op.url, "--out", str(destination)],
                mutating=True,
                timeout=120,
            )
        )
        if capture_dir is not None:
            runtime.artifacts.attest_capture(
                capture_dir,
                source="chrome-cdp",
                target={"kind": "browser-download", "page_id": page_id, "url": op.url},
                files=[destination],
            )
            artifact_id = runtime.artifacts.register(
                destination, kind="browser-download", owner_id="browser-download"
            )
            media = (
                str(result.get("type") or "").split(";")[0]
                if isinstance(result, dict)
                else ""
            )
            artifact, blocks = attach(
                destination,
                ref=f"sinnix://artifacts/{artifact_id}",
                media_type=media or None,
            )
        else:
            artifact, _ = attach(
                destination, ref=op.destination.resolve()[1], max_inline_bytes=1
            )
    elif isinstance(op, UploadOp):
        arguments = ["upload-files", page_id, "--selector", op.element.css()]
        for locator in op.files:
            arguments.extend(
                ["--file", str(_authorized(runtime, locator, existing=True))]
            )
        result = _owner_call(lambda: runtime.browser.invoke(arguments, mutating=True))
    elif isinstance(op, EvaluateOp):
        result = (
            _await(runtime, page_id, op.javascript, op.timeout_seconds)
            if op.until_truthy
            else _js(runtime, page_id, op.javascript)
        )
    return ActionResult(
        BrowserOperateResult(
            ref=ref,
            page_id=page_id,
            operation=op.operation,
            result=result,
            page=None if isinstance(op, CloseOp) else _observe(runtime, page_id),
            artifact=artifact,
            artifact_ref=artifact.ref if artifact else None,
            affordances=["browser.page", "browser.screenshot", "browser.operate"],
        ),
        blocks=blocks,
    )


_READ = {"owner": "browser", "principals": OBSERVER_OPERATOR}
_TARGET = {"target": {"url_contains": "example.test"}}

ACTIONS: tuple[Action, ...] = (
    Action(
        name="browser.pages",
        family=VerbFamily.CATALOG,
        summary="List every open Chrome page with its ref; flags the gateway-owned pages that can be read, captured or operated.",
        Input=PagesInput,
        Output=PageListing,
        handler=_pages,
        resource_kinds=("browser_page", "browser_workspace"),
        affordances=("browser.page", "browser.operate", "browser.screenshot"),
        aliases=("tabs", "open pages", "list tabs", "what is open in chrome"),
        examples=(Example(title="List pages", input={}),),
        **_READ,
    ),
    Action(
        name="browser.page",
        family=VerbFamily.GET,
        summary="Read one gateway-owned page: url, title, text, links, forms and interactive elements with refs scoped to a page generation.",
        Input=PageInput,
        Output=PageSnapshot,
        handler=_page_snapshot,
        resource_kinds=("browser_page",),
        affordances=("browser.operate", "browser.screenshot"),
        aliases=(
            "page text",
            "read page",
            "page content",
            "elements",
            "links",
            "forms",
        ),
        documentation="Element refs (g<generation>e<n>) are attached to the DOM for this snapshot; a later snapshot or reload replaces them, and a stale ref fails not_found.",
        examples=(Example(title="Read a page", input=_TARGET),),
        **_READ,
    ),
    Action(
        name="browser.screenshot",
        family=VerbFamily.QUERY,
        summary="Screenshot a gateway-owned page through CDP; the image rides in an image block and is retained as an artifact.",
        Input=BrowserScreenshotInput,
        Output=BrowserScreenshot,
        handler=_screenshot,
        resource_kinds=("browser_page", "artifact"),
        affordances=("browser.page", "browser.operate", "artifacts.read"),
        aliases=("page screenshot", "capture page", "picture of the page"),
        examples=(
            Example(title="Full-page PNG", input={**_TARGET, "full_page": True}),
        ),
        **_READ,
    ),
    Action(
        name="browser.operate",
        family=VerbFamily.OPERATE,
        owner="browser",
        principals=OPERATOR_ONLY,
        summary="Open a gateway page on the hidden agent workspace, or navigate, click, fill, submit, scroll, press keys, wait, download, upload, or evaluate JavaScript in one gateway-owned page.",
        Input=BrowserOperateInput,
        Output=BrowserOperateResult,
        handler=_operate,
        resource_kinds=("browser_page", "browser_workspace"),
        affordances=("browser.page", "browser.screenshot", "browser.pages"),
        aliases=(
            "open url",
            "click link",
            "fill form",
            "type in browser",
            "press enter",
            "download file",
            "upload file",
            "run javascript",
        ),
        documentation="Operator tabs are never accepted as targets, even when a locator matches one. Element targets take a snapshot ref or a CSS selector.",
        examples=(
            Example(
                title="Open an agent page",
                input={
                    "action": {"operation": "new", "url": "https://example.test"},
                    "idempotency_key": "new-1",
                },
            ),
            Example(
                title="Click by snapshot ref",
                input={
                    **_TARGET,
                    "action": {"operation": "click", "element": {"ref": "g1e4"}},
                    "idempotency_key": "click-1",
                },
            ),
            Example(
                title="Fill and submit",
                input={
                    **_TARGET,
                    "action": {
                        "operation": "fill",
                        "element": {"selector": "#q"},
                        "value": "sinnix",
                    },
                    "idempotency_key": "fill-1",
                },
            ),
            Example(
                title="Wait for text",
                input={
                    **_TARGET,
                    "action": {"operation": "wait", "for": "text", "value": "Results"},
                    "idempotency_key": "wait-1",
                },
            ),
        ),
    ),
)
