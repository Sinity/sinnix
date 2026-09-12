"""Inspect images/PDFs and render selected views as actual MCP image blocks."""

from __future__ import annotations

import base64
import mimetypes
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal

from mcp.types import ImageContent, TextContent
from pydantic import Field, model_validator

from .. import visual
from ..action import ALL_PRINCIPALS, Action, ActionResult, Example, RequestControls
from ..artifacts import ArtifactError
from ..capabilities import Capability
from ..content import Artifact, sha256_of, sniff_media_type
from ..contracts import VerbFamily
from ..files import FileError
from ..locators import ArtifactLocator, FileLocator, encode_file_ref
from ..results import ProtocolError
from ..schemas import GatewayModel

if TYPE_CHECKING:
    from ..runtime import Runtime


class InspectInput(RequestControls):
    target: FileLocator | ArtifactLocator
    pages: list[Annotated[int, Field(ge=1)]] = Field(
        default_factory=list,
        description="1-based PDF pages to inspect; empty inspects page 1. Image inputs omit pages.",
    )

    @model_validator(mode="after")
    def distinct_pages(self):
        if len(self.pages) != len(set(self.pages)):
            raise ValueError("pages must be distinct")
        return self


class Crop(GatewayModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(ge=1)
    height: int = Field(ge=1)


class RenderInput(InspectInput):
    mode: Literal["thumbnail", "fit", "original"] = Field(
        default="fit",
        description="thumbnail fits within 512px; fit uses max_edge; original keeps image pixel resolution within safety bounds (re-encoded, not original file bytes).",
    )
    max_edge: int = Field(
        default=1600,
        ge=1,
        description="Longest rendered edge in pixels. Total output is bounded to 16 million pixels.",
    )
    crop: Crop | None = Field(
        default=None,
        description="Image crop in orientation-corrected source pixels; PDF pages do not accept image crops.",
    )


class Page(GatewayModel):
    page: int
    width: float
    height: float
    unit: Literal["pt"]
    rotation: int


class Inspection(GatewayModel):
    source_ref: str
    source_sha256: str
    source_bytes: int
    media_type: str
    kind: Literal["pdf", "image"]
    page_count: int | None = None
    width: int | None = None
    height: int | None = None
    frame_count: int | None = Field(
        default=None,
        description="Only the first frame is rendered for multi-frame images.",
    )
    pages: list[Page] = Field(default_factory=list)
    affordances: list[str] = Field(default_factory=lambda: ["documents.render"])


class RenderedView(GatewayModel):
    page: int | None = None
    width: int
    height: int
    artifact: Artifact
    content_index: int = Field(
        description="Zero-based index of the corresponding image in MCP content (including the leading envelope text block)."
    )


class RenderedDocument(Inspection):
    original: Artifact
    mode: Literal["thumbnail", "fit", "original"]
    crop: Crop | None = None
    views: list[RenderedView]


def _source(
    runtime: Runtime, target: FileLocator | ArtifactLocator
) -> tuple[Path, str]:
    if isinstance(target, FileLocator):
        runtime.principal.require(Capability.FILE_READ)
        raw, _ = target.resolve()
        try:
            path = runtime.files._resolve(raw, existing=True)
        except FileError as exc:
            raise ProtocolError(
                "not_found" if "not exist" in str(exc) else "policy_denied", str(exc)
            ) from exc
        return path, encode_file_ref(str(path))
    runtime.principal.require(Capability.ARTIFACT_READ)
    artifact_id, ref = target.resolve()
    try:
        return runtime.artifacts._metadata(artifact_id)["_source"], ref
    except FileNotFoundError as exc:
        raise ProtocolError("not_found", "artifact source is missing") from exc
    except ArtifactError as exc:
        raise ProtocolError(
            "policy_denied" if "principal" in str(exc) else "not_found", str(exc)
        ) from exc


def _description(path: Path, ref: str, decoded: dict) -> dict:
    return {
        "source_ref": ref,
        "source_sha256": sha256_of(path),
        "source_bytes": path.stat().st_size,
        "media_type": sniff_media_type(path),
        **{key: value for key, value in decoded.items() if key != "renders"},
    }


def _inspect(runtime: Runtime, inp: InspectInput) -> Inspection:
    source, ref = _source(runtime, inp.target)
    with tempfile.TemporaryDirectory(
        prefix="visual-inspect-", dir=runtime.config.state_dir
    ) as directory:
        path = Path(directory) / "source"
        visual.snapshot(source, path)
        decoded = visual.decode(path, Path(directory), render=False, pages=inp.pages)
        return Inspection(**_description(path, ref, decoded))


def _render(runtime: Runtime, inp: RenderInput) -> ActionResult:
    source, ref = _source(runtime, inp.target)
    root = runtime.config.state_dir / "captures"
    root.mkdir(mode=0o700, exist_ok=True)
    # A TemporaryDirectory owns failure cleanup. Successful captures are moved into
    # a separately allocated retained directory only after decoding succeeds.
    with tempfile.TemporaryDirectory(
        prefix="visual-", dir=runtime.config.state_dir
    ) as scratch:
        directory = Path(scratch)
        original = directory / ("original" + source.suffix)
        visual.snapshot(source, original)
        decoded = visual.decode(
            original,
            directory,
            render=True,
            pages=inp.pages,
            mode=inp.mode,
            max_edge=inp.max_edge,
            crop=inp.crop.model_dump() if inp.crop else None,
        )
        description = _description(original, ref, decoded)
        extension = mimetypes.guess_extension(description["media_type"]) or ".bin"
        original = original.rename(directory / ("original" + extension))
        retained = Path(tempfile.mkdtemp(prefix="visual-", dir=root))
        paths = [original, *(directory / row["name"] for row in decoded["renders"])]
        # Move within gateway state, so retaining an arbitrarily large original is O(1).
        paths = [path.rename(retained / path.name) for path in paths]
        runtime.artifacts.attest_capture(
            retained,
            source="documents.render",
            target={"source_ref": ref, "source_sha256": description["source_sha256"]},
            files=paths,
        )

        def register(path: Path, media: str, representation: str) -> Artifact:
            identifier = runtime.artifacts.register(
                path,
                kind="document-original" if path == paths[0] else "document-view",
                owner_id=ref,
            )
            return Artifact(
                ref=f"sinnix://artifacts/{identifier}",
                media_type=media,
                bytes=path.stat().st_size,
                sha256=description["source_sha256"]
                if path == paths[0]
                else sha256_of(path),
                name=path.name,
                representation=representation,
            )

        original_artifact = register(paths[0], description["media_type"], "link")
        blocks = []
        views = []
        for row, path in zip(decoded["renders"], paths[1:], strict=True):
            artifact = register(path, row["media_type"], "image")
            label = (
                f"PDF page {row['page']}"
                if "page" in row
                else "Image view (first frame)"
            )
            blocks.append(
                TextContent(
                    type="text",
                    text=f"{label}; source {ref}; sha256 {description['source_sha256']}; {row['width']} x {row['height']} pixels; view {artifact.ref}",
                )
            )
            views.append(
                RenderedView(
                    page=row.get("page"),
                    width=row["width"],
                    height=row["height"],
                    artifact=artifact,
                    content_index=len(blocks) + 1,
                )
            )
            blocks.append(
                ImageContent(
                    type="image",
                    data=base64.b64encode(path.read_bytes()).decode("ascii"),
                    mime_type=row["media_type"],
                )
            )
        return ActionResult(
            RenderedDocument(
                **description,
                original=original_artifact,
                mode=inp.mode,
                crop=inp.crop,
                views=views,
                affordances=["documents.render", "documents.inspect", "artifacts.read"],
            ),
            blocks=blocks,
        )


ACTIONS = (
    Action(
        name="documents.inspect",
        family=VerbFamily.QUERY,
        owner="documents",
        summary="Inspect an authorized image or PDF: dimensions, page count and selected page geometry.",
        Input=InspectInput,
        Output=Inspection,
        handler=_inspect,
        principals=ALL_PRINCIPALS,
        resource_kinds=("file", "artifact"),
        affordances=("documents.render",),
        aliases=("pdf pages", "image dimensions"),
        examples=(
            Example(
                title="Inspect a PDF",
                input={"target": {"path": "/realm/documents/example.pdf"}},
            ),
        ),
    ),
    Action(
        name="documents.render",
        family=VerbFamily.QUERY,
        owner="documents",
        summary="View an image or selected PDF pages as MCP image blocks; retains the original and rendered views as private artifacts.",
        Input=RenderInput,
        Output=RenderedDocument,
        handler=_render,
        principals=ALL_PRINCIPALS,
        resource_kinds=("file", "artifact"),
        affordances=("documents.inspect", "documents.render", "artifacts.read"),
        aliases=("view photo", "read PDF visually", "image crop", "thumbnail"),
        documentation="PDF pages are explicit and 1-based. Image crop coordinates follow EXIF orientation; only the first frame is rendered. Each view has page/source provenance and travels in ImageContent, independently of text read budgets. Original file bytes remain in a principal-scoped artifact. Decoder bounds: 80 million source image pixels, 16 million total output pixels, 2 GiB address space, 30 seconds and 3 MiB encoded images (4 MiB base64). Reduce pages or dimensions after response_bound. Client display depends on MCP image support.",
        examples=(
            Example(
                title="View PDF pages",
                input={
                    "target": {"path": "/realm/documents/example.pdf"},
                    "pages": [1, 2],
                },
            ),
            Example(
                title="View an image crop",
                input={
                    "target": {"path": "/realm/photos/example.jpg"},
                    "crop": {"x": 100, "y": 100, "width": 800, "height": 600},
                },
            ),
        ),
    ),
)
