"""Gateway artifacts: list, metadata, and typed reads (text inline, image block, resource block)."""

from __future__ import annotations

import codecs
import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field

from ..action import ALL_PRINCIPALS, Action, ActionResult, Example, RequestControls
from ..artifacts import ArtifactError
from ..capabilities import Capability
from ..content import IMAGE_TYPES, Artifact, attach, is_text
from ..contracts import VerbFamily
from ..locators import ARTIFACT_REF_PREFIX, ArtifactLocator
from ..results import ProtocolError
from ..schemas import GatewayModel

if TYPE_CHECKING:
    from ..runtime import Runtime


class ArtifactRow(GatewayModel):
    ref: str
    artifact_id: str
    kind: str | None = None
    owner_id: str | None = None
    principal: str | None = None
    bytes: int | None = None
    content_type: str | None = None
    malformed: bool = False


class ListInput(RequestControls):
    kind: str | None = Field(
        default=None,
        max_length=128,
        description="Exact artifact kind, e.g. mcp-stderr, machine-query.",
    )
    owner_id: str | None = Field(default=None, max_length=256)
    limit: int = Field(default=100, ge=1)
    cursor: str | None = Field(default=None, max_length=8192)


class Listing(GatewayModel):
    artifacts: list[ArtifactRow]
    affordances: list[str] = Field(default_factory=list)


def _row(raw: dict[str, Any]) -> ArtifactRow:
    return ArtifactRow(
        ref=f"{ARTIFACT_REF_PREFIX}{raw['artifact_id']}",
        **{
            k: raw.get(k)
            for k in (
                "artifact_id",
                "kind",
                "owner_id",
                "principal",
                "bytes",
                "content_type",
            )
        },
        malformed=bool(raw.get("malformed")),
    )


def _list(runtime: Runtime, inp: ListInput) -> ActionResult:
    runtime.principal.require(Capability.ARTIFACT_READ)
    query = {
        "action": "artifacts.list",
        "kind": inp.kind,
        "owner_id": inp.owner_id,
        "limit": inp.limit,
    }
    query_hash = hashlib.sha256(json.dumps(query, sort_keys=True).encode()).hexdigest()
    if inp.cursor:
        snapshot = runtime.results.continue_snapshot(
            inp.cursor, query_sha256=query_hash
        )
    else:
        rows = [
            _row(raw).model_dump()
            for raw in runtime.artifacts.list(
                None, kind=inp.kind, owner_id=inp.owner_id
            )["artifacts"]
        ]
        revision = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
        writer = runtime.results.start_snapshot(
            query_sha256=query_hash, source_revision=revision, page_size=inp.limit
        )
        try:
            for row in rows:
                writer.append(row)
            snapshot = runtime.results.finish_snapshot(writer)
        except Exception:
            writer.abort()
            raise
    return ActionResult(
        Listing(
            artifacts=snapshot["rows"], affordances=["artifacts.get", "artifacts.read"]
        ),
        page={
            "kind": "snapshot",
            "cursor": snapshot["cursor"],
            "next_cursor": snapshot["next_cursor"],
            "total": snapshot["row_count"],
            "expires_at": snapshot["expires_at"],
            "snapshot_ref": snapshot["snapshot_ref"],
        },
    )


class GetInput(RequestControls):
    target: ArtifactLocator


class Metadata(ArtifactRow):
    source_name: str | None = None
    affordances: list[str] = Field(default_factory=list)


def _metadata(
    runtime: Runtime, locator: ArtifactLocator
) -> tuple[dict[str, Any], Path, str]:
    runtime.principal.require(Capability.ARTIFACT_READ)
    artifact_id, ref = locator.resolve()
    try:
        raw = runtime.artifacts._metadata(artifact_id)
    except ArtifactError as exc:
        message = str(exc)
        code = (
            "not_found"
            if "unknown" in message or "invalid" in message or "no longer" in message
            else "policy_denied"
        )
        raise ProtocolError(code, message) from exc
    except FileNotFoundError as exc:
        raise ProtocolError("not_found", "artifact source is missing") from exc
    return raw, raw.pop("_source"), ref


def _get(runtime: Runtime, inp: GetInput) -> Metadata:
    raw, source, ref = _metadata(runtime, inp.target)
    return Metadata(
        **_row(raw).model_dump(),
        source_name=source.name,
        affordances=["artifacts.read"],
    )


class ReadInput(RequestControls):
    target: ArtifactLocator
    offset: int = Field(default=0, ge=0, description="Byte offset for text reads.")
    max_bytes: int = Field(
        default=64_000, ge=1, description="Maximum inline text bytes."
    )
    representation: Literal["auto", "text"] = "auto"


class Content(GatewayModel):
    ref: str
    artifact_id: str
    kind: str | None = None
    owner_id: str | None = None
    content_type: str
    bytes: int
    text: str | None = None
    offset: int = 0
    returned_bytes: int = 0
    next_offset: int | None = None
    truncated: bool = False
    artifact: Artifact | None = Field(
        default=None,
        description="Set for binary artifacts; bytes are represented by a canonical read-only link.",
    )
    affordances: list[str] = Field(default_factory=list)


def _read(runtime: Runtime, inp: ReadInput) -> ActionResult:
    raw, source, ref = _metadata(runtime, inp.target)
    media = raw.get("content_type") or "application/octet-stream"
    size = source.stat().st_size
    max_bytes = inp.max_bytes
    base = {
        "ref": ref,
        "artifact_id": raw["artifact_id"],
        "kind": raw.get("kind"),
        "owner_id": raw.get("owner_id"),
        "content_type": media,
        "bytes": size,
        "affordances": ["artifacts.get", "artifacts.list"],
    }
    textual = inp.representation == "text" or (
        inp.representation == "auto" and is_text(media) and media not in IMAGE_TYPES
    )
    if textual:
        with source.open("rb") as handle:
            handle.seek(inp.offset)
            data = handle.read(max_bytes + 1)
        truncated = len(data) > max_bytes
        data = data[:max_bytes]
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        text = decoder.decode(data, final=not truncated)
        consumed = len(data) - len(decoder.getstate()[0])
        if truncated and consumed == 0:
            raise ProtocolError(
                "invalid_request",
                "max_bytes cannot fit the next UTF-8 character; retry with at least 4",
            )
        return ActionResult(
            Content(
                **base,
                text=text,
                offset=inp.offset,
                returned_bytes=consumed,
                next_offset=inp.offset + consumed if truncated else None,
                truncated=truncated,
            )
        )
    artifact, blocks = attach(source, ref=ref, media_type=media)
    return ActionResult(
        Content(**base, artifact=artifact, returned_bytes=0),
        blocks=blocks,
    )


ACTIONS: tuple[Action, ...] = (
    Action(
        name="artifacts.list",
        family=VerbFamily.CATALOG,
        owner="artifacts",
        summary="List principal-visible artifacts with kind, owner, size and canonical ref.",
        Input=ListInput,
        Output=Listing,
        handler=_list,
        principals=ALL_PRINCIPALS,
        resource_kinds=("artifact",),
        affordances=("artifacts.get", "artifacts.read"),
        aliases=("captures", "diagnostics", "stored responses", "large results"),
        examples=(
            Example(
                title="Recent MCP stderr captures",
                input={"kind": "mcp-stderr", "limit": 20},
            ),
        ),
    ),
    Action(
        name="artifacts.get",
        family=VerbFamily.GET,
        owner="artifacts",
        summary="Metadata of one artifact without its bytes.",
        Input=GetInput,
        Output=Metadata,
        handler=_get,
        principals=ALL_PRINCIPALS,
        resource_kinds=("artifact",),
        affordances=("artifacts.read", "artifacts.list"),
        aliases=("artifact info", "artifact metadata"),
        examples=(
            Example(
                title="By ref",
                input={
                    "target": {
                        "ref": "sinnix://artifacts/00000000-0000-0000-0000-000000000000"
                    }
                },
            ),
        ),
    ),
    Action(
        name="artifacts.read",
        family=VerbFamily.QUERY,
        owner="artifacts",
        summary="Read an artifact: text inline with offsets, images as image blocks, other binary as read-only links.",
        Input=ReadInput,
        Output=Content,
        handler=_read,
        principals=ALL_PRINCIPALS,
        resource_kinds=("artifact",),
        affordances=("artifacts.get", "artifacts.list"),
        aliases=(
            "open artifact",
            "diagnostic log",
            "truncated response",
            "view capture",
        ),
        examples=(
            Example(
                title="First 64 KB of a stored response",
                input={
                    "target": {"artifact_id": "00000000-0000-0000-0000-000000000000"}
                },
            ),
        ),
    ),
)
