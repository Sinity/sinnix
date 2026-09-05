"""Gateway artifacts: list, metadata, and typed reads (text inline, image block, resource block)."""

from __future__ import annotations

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
    limit: int = Field(default=100, ge=1, le=1_000)


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


def _list(runtime: Runtime, inp: ListInput) -> Listing:
    rows = [_row(raw) for raw in runtime.artifacts.list(inp.limit)["artifacts"]]
    if inp.kind is not None:
        rows = [row for row in rows if row.kind == inp.kind]
    if inp.owner_id is not None:
        rows = [row for row in rows if row.owner_id == inp.owner_id]
    return Listing(artifacts=rows, affordances=["artifacts.get", "artifacts.read"])


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
    max_bytes: int = Field(default=64_000, ge=1, le=4_194_304)
    representation: Literal["auto", "text", "binary"] = "auto"


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
        description="Set for binary artifacts; the bytes travel in a content block.",
    )
    affordances: list[str] = Field(default_factory=list)


def _read(runtime: Runtime, inp: ReadInput) -> ActionResult:
    raw, source, ref = _metadata(runtime, inp.target)
    media = raw.get("content_type") or "application/octet-stream"
    size = source.stat().st_size
    max_bytes = min(inp.max_bytes, runtime.config.max_result_bytes)
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
        return ActionResult(
            Content(
                **base,
                text=data.decode("utf-8", "replace"),
                offset=inp.offset,
                returned_bytes=len(data),
                next_offset=inp.offset + len(data) if truncated else None,
                truncated=truncated,
            )
        )
    artifact, blocks = attach(
        source, ref=ref, media_type=media, max_inline_bytes=max_bytes
    )
    return ActionResult(
        Content(**base, artifact=artifact, returned_bytes=min(size, max_bytes)),
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
        summary="Read an artifact: text inline with offsets, images as an image block, other binary as a resource block.",
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
