"""Binary and large content at the MCP boundary.

Text rides inline in the structured envelope. Images become ``ImageContent``
blocks so a vision-capable client sees the picture. Other binary content is a
``ResourceLink`` addressed by its canonical ref. Its bytes never become a
chat attachment, so reading a host file cannot trigger client-side attachment
approval.
"""

from __future__ import annotations

import base64
import hashlib
import mimetypes
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Literal

from mcp.types import (
    ContentBlock,
    ImageContent,
    ResourceLink,
)
from pydantic import Field

from .schemas import GatewayModel

INLINE_IMAGE_BYTES = 4 * 1024 * 1024
IMAGE_TYPES = frozenset({"image/png", "image/jpeg", "image/webp", "image/gif"})


class Artifact(GatewayModel):
    """One description of bytes the caller may fetch again by ref."""

    ref: str = Field(description="Canonical ref that reads these bytes again.")
    media_type: str
    bytes: int
    sha256: str | None = None
    name: str | None = None
    representation: Literal["image", "resource", "link", "text"]
    preview: bool = Field(
        default=False,
        description="The image block is a derived view; ref and hash still identify the original bytes.",
    )
    preview_width: int | None = None
    preview_height: int | None = None


def sniff_media_type(path: Path) -> str:
    """MIME from libmagic-backed file(1) when present, else the extension map."""
    try:
        completed = subprocess.run(
            ["file", "--brief", "--mime-type", "--", str(path)],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        guess = completed.stdout.strip()
        if completed.returncode == 0 and "/" in guess:
            return guess
    except (OSError, subprocess.SubprocessError):
        pass
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def is_text(media_type: str) -> bool:
    return media_type.startswith("text/") or media_type in {
        "application/json",
        "application/x-ndjson",
        "application/xml",
        "application/toml",
        "application/yaml",
        "application/x-yaml",
        "application/javascript",
        "application/x-sh",
        "application/x-shellscript",
        "inode/x-empty",
    }


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def attach(
    path: Path,
    *,
    ref: str,
    media_type: str | None = None,
) -> tuple[Artifact, list[ContentBlock]]:
    """Describe a file and produce visual blocks or a read-only binary handle."""
    media_type = media_type or sniff_media_type(path)
    size = path.stat().st_size
    digest = sha256_of(path)
    base: dict[str, Any] = {
        "ref": ref,
        "media_type": media_type,
        "bytes": size,
        "sha256": digest,
        "name": path.name,
    }
    if media_type in IMAGE_TYPES and size <= INLINE_IMAGE_BYTES:
        data = base64.b64encode(path.read_bytes()).decode()
        return (
            Artifact(representation="image", **base),
            [ImageContent(type="image", data=data, mime_type=media_type)],
        )
    if media_type.startswith("image/"):
        from . import visual

        with tempfile.TemporaryDirectory(prefix="gateway-image-") as directory:
            output = Path(directory)
            source = output / "source"
            visual.snapshot(path, source)
            decoded = visual.decode(source, output, render=True, pages=[])
            row = decoded["renders"][0]
            data = base64.b64encode((output / row["name"]).read_bytes()).decode()
            return (
                Artifact(
                    representation="image",
                    preview=True,
                    preview_width=row["width"],
                    preview_height=row["height"],
                    **base,
                ),
                [ImageContent(type="image", data=data, mime_type=row["media_type"])],
            )
    return (
        Artifact(representation="link", **base),
        [
            ResourceLink(
                type="resource_link",
                name=path.name,
                uri=ref,
                mime_type=media_type,
                size=size,
                description="Read-only binary resource handle; bytes are not attached to the chat.",
            )
        ],
    )
