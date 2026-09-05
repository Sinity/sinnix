"""Audit chain verification, receipts, result snapshots, and the capability index."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field, model_validator

from ..action import ALL_PRINCIPALS, Action, Example, RequestControls
from ..capability_index import CapabilityIndexError
from ..catalog import search_rows
from ..contracts import VerbFamily
from ..results import ProtocolError, ResultError
from ..schemas import GatewayModel

if TYPE_CHECKING:
    from ..runtime import Runtime


class VerifyInput(RequestControls):
    pass


class Verification(GatewayModel):
    valid: bool
    checked: int
    head_hash: str | None = None
    broken_at: int | None = None
    affordances: list[str] = Field(default_factory=list)


def _verify(runtime: Runtime, _inp: VerifyInput) -> Verification:
    return Verification(
        **runtime.audit.verify(), affordances=["audit.receipt", "events.tail"]
    )


class ReceiptInput(RequestControls):
    ref: str | None = Field(
        default=None, pattern=r"^sinnix://receipts/[0-9a-fA-F-]{36}$"
    )
    receipt_id: str | None = Field(default=None, min_length=36, max_length=36)

    @model_validator(mode="after")
    def exactly_one(self) -> ReceiptInput:
        if (self.ref is None) == (self.receipt_id is None):
            raise ValueError("give exactly one of ref or receipt_id")
        return self


class Receipt(GatewayModel):
    ref: str
    receipt_id: str
    sequence: int
    occurred_at: float
    principal: str
    operation: str
    outcome: str
    payload: dict[str, Any]
    previous_hash: str
    entry_hash: str
    schema_name: str


def _receipt(runtime: Runtime, inp: ReceiptInput) -> Receipt:
    receipt_id = inp.receipt_id or (inp.ref or "").rsplit("/", 1)[1]
    try:
        raw = runtime.audit.receipt(receipt_id)
    except ValueError as exc:
        message = str(exc)
        raise ProtocolError(
            "policy_denied" if "principal" in message else "not_found", message
        ) from exc
    raw["schema_name"] = raw.pop("schema")
    return Receipt(ref=f"sinnix://receipts/{raw['receipt_id']}", **raw)


class ResultInput(RequestControls):
    ref: str | None = Field(default=None, pattern=r"^sinnix://results/[^/]{1,128}$")
    result_id: str | None = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode="after")
    def exactly_one(self) -> ResultInput:
        if (self.ref is None) == (self.result_id is None):
            raise ValueError("give exactly one of ref or result_id")
        return self


class ResultSnapshot(GatewayModel):
    ref: str
    envelope: dict[str, Any] = Field(
        description="The immutable stored V2 response envelope."
    )


def _result(runtime: Runtime, inp: ResultInput) -> ResultSnapshot:
    result_id = inp.result_id or (inp.ref or "").rsplit("/", 1)[1]
    try:
        envelope = runtime.results.read(result_id)
    except ResultError as exc:
        raise ProtocolError("not_found", str(exc)) from exc
    return ResultSnapshot(ref=envelope["result"]["ref"], envelope=envelope)


# ------------------------------------------------------------ capabilities


class SearchOp(GatewayModel):
    operation: Literal["search"] = "search"
    query: str = Field(
        default="",
        max_length=1_024,
        description="Terms matched against kind, name, description, invoke, owner and docs.",
    )
    kind: str | None = Field(default=None, min_length=1, max_length=64)
    enabled: bool | None = None
    cursor: int = Field(default=0, ge=0)
    limit: int = Field(default=100, ge=1, le=500)


class DescribeOp(GatewayModel):
    operation: Literal["describe"] = "describe"
    name: str = Field(min_length=1, max_length=1_024)
    kind: str | None = Field(default=None, min_length=1, max_length=64)


class CapabilitiesInput(RequestControls):
    request: SearchOp | DescribeOp = Field(
        default_factory=SearchOp, discriminator="operation"
    )


class Capabilities(GatewayModel):
    operation: Literal["search", "describe"]
    available: bool
    reason: str | None = None
    source: dict[str, Any] | None = None
    query: str | None = None
    name: str | None = None
    kind: str | None = None
    enabled: bool | None = None
    ambiguous: bool | None = None
    total: int | None = None
    cursor: int | None = None
    next_cursor: int | None = None
    rows: list[dict[str, Any]] = Field(default_factory=list)
    affordances: list[str] = Field(default_factory=list)


_SEARCH_FIELDS = ("kind", "name", "description", "invoke", "owner", "docs")


def _capabilities(runtime: Runtime, inp: CapabilitiesInput) -> Capabilities:
    op = inp.request
    try:
        if isinstance(op, DescribeOp):
            payload = runtime.capability_index.describe(op.name, op.kind)
        else:
            payload = runtime.capability_index.search("", op.kind, op.enabled, 0, 500)
            if payload.get("available"):
                index = runtime.capability_index._load() or {"rows": []}
                rows = [
                    row
                    for row in index["rows"]
                    if (op.kind is None or row.get("kind") == op.kind)
                    and (op.enabled is None or row.get("enabled") is op.enabled)
                ]
                rows = search_rows(rows, op.query, _SEARCH_FIELDS)
                if op.cursor >= len(rows) and op.cursor != 0:
                    raise ProtocolError(
                        "stale_cursor", "cursor is beyond matching capability rows"
                    )
                page = rows[op.cursor : op.cursor + op.limit]
                payload = {
                    **payload,
                    "query": op.query,
                    "total": len(rows),
                    "cursor": op.cursor,
                    "next_cursor": op.cursor + len(page)
                    if op.cursor + len(page) < len(rows)
                    else None,
                    "rows": page,
                }
    except CapabilityIndexError as exc:
        raise ProtocolError("invalid_request", str(exc)) from exc
    for row in payload.get("rows", []):
        if isinstance(row.get("name"), str) and "ref" not in row:
            row["ref"] = f"sinnix://capabilities/{row['name']}"
    return Capabilities(
        operation=op.operation,
        **{k: v for k, v in payload.items() if k in Capabilities.model_fields},
        affordances=["capabilities.query"],
    )


ACTIONS: tuple[Action, ...] = (
    Action(
        name="audit.verify",
        family=VerbFamily.STATUS,
        owner="audit",
        summary="Verify the tamper-evident audit hash chain end to end.",
        Input=VerifyInput,
        Output=Verification,
        handler=_verify,
        principals=ALL_PRINCIPALS,
        resource_kinds=("receipt",),
        affordances=("audit.receipt", "events.tail"),
        aliases=("audit chain", "integrity", "tamper check"),
        examples=(Example(title="Verify", input={}),),
    ),
    Action(
        name="audit.receipt",
        family=VerbFamily.GET,
        owner="audit",
        summary="Read one principal-scoped audit receipt by ref or id.",
        Input=ReceiptInput,
        Output=Receipt,
        handler=_receipt,
        principals=ALL_PRINCIPALS,
        resource_kinds=("receipt",),
        affordances=("audit.verify", "events.tail"),
        aliases=("receipt", "what happened in that call"),
        examples=(
            Example(
                title="By ref",
                input={"ref": "sinnix://receipts/00000000-0000-0000-0000-000000000000"},
            ),
        ),
    ),
    Action(
        name="results.get",
        family=VerbFamily.GET,
        owner="results",
        summary="Read one immutable stored response snapshot by ref or id.",
        Input=ResultInput,
        Output=ResultSnapshot,
        handler=_result,
        principals=ALL_PRINCIPALS,
        resource_kinds=("result",),
        affordances=("audit.receipt",),
        aliases=("result snapshot", "replay response"),
        examples=(Example(title="By id", input={"result_id": "example-result"}),),
    ),
    Action(
        name="capabilities.query",
        family=VerbFamily.CATALOG,
        owner="capability-index",
        summary="Search the generated machine capability index or describe one capability exactly.",
        Input=CapabilitiesInput,
        Output=Capabilities,
        handler=_capabilities,
        principals=ALL_PRINCIPALS,
        resource_kinds=("capability",),
        affordances=("capabilities.query",),
        aliases=(
            "what can this machine do",
            "scripts",
            "services",
            "which command",
            "capability index",
        ),
        examples=(
            Example(
                title="Search",
                input={"request": {"operation": "search", "query": "screenshot"}},
            ),
            Example(
                title="Describe",
                input={"request": {"operation": "describe", "name": "sinnix-observe"}},
            ),
        ),
    ),
)
