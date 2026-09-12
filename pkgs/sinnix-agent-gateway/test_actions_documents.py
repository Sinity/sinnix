"""Visual reads exercised through the MCP tool boundary with real images/PDFs."""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path

import anyio
import pymupdf
import pytest
from PIL import Image, ImageDraw
from sinnix_agent_gateway import visual
from sinnix_agent_gateway.actions import documents
from sinnix_agent_gateway.content import attach
from sinnix_agent_gateway.results import ProtocolError
from sinnix_agent_gateway.tooling import build_tool
from test_actions_artifacts import register, runtime


def invoke(rt, name, **arguments):
    action = next(action for action in documents.ACTIONS if action.name == name)

    async def run():
        return await build_tool(action, rt).fn(**arguments)

    return anyio.run(run)


def make_pdf(path: Path, *, encrypted: bool = False):
    with pymupdf.open() as document:
        for color, caption in [
            ((1, 0, 0), "RED PAGE ONE"),
            ((0, 0, 1), "BLUE PAGE TWO"),
        ]:
            page = document.new_page(width=400, height=300)
            page.draw_rect((30, 70, 370, 270), color=color, fill=color)
            page.insert_text((30, 40), caption, fontsize=20)
        options = (
            {
                "encryption": pymupdf.PDF_ENCRYPT_AES_256,
                "owner_pw": "owner",
                "user_pw": "synthetic",
            }
            if encrypted
            else {}
        )
        document.save(path, **options)


def make_image(path: Path):
    image = Image.new("RGB", (2400, 1600), "white")
    ImageDraw.Draw(image).rectangle((1200, 0, 2399, 1599), fill="blue")
    image.save(path)


def pixels(block):
    # Serialization aliases are the actual JSON-RPC fields clients receive.
    wire = block.model_dump(mode="json", by_alias=True)
    assert wire["type"] == "image"
    assert wire["mimeType"] in {"image/png", "image/jpeg"}
    return Image.open(io.BytesIO(base64.b64decode(wire["data"])))


def test_pdf_wire_images_have_selected_page_provenance_and_original(tmp_path):
    rt = runtime(tmp_path)
    path = tmp_path / "example.pdf"
    make_pdf(path)
    original_bytes = path.read_bytes()
    inspection = invoke(rt, "documents.inspect", target={"path": str(path)})
    assert inspection.structured_content["data"]["page_count"] == 2
    result = invoke(
        rt, "documents.render", target={"path": str(path)}, pages=[2, 1], max_edge=800
    )
    assert not result.is_error, result.structured_content
    data = result.structured_content["data"]
    assert [view["page"] for view in data["views"]] == [2, 1]
    for view, color in zip(data["views"], [(0, 0, 255), (255, 0, 0)], strict=True):
        image = pixels(result.content[view["content_index"]])
        assert image.size == (800, 600)
        assert image.getpixel((400, 350)) == color
    artifact_id = data["original"]["ref"].rsplit("/", 1)[1]
    stored = rt.artifacts._metadata(artifact_id)["_source"]
    assert stored.read_bytes() == original_bytes == path.read_bytes()
    assert stored.stat().st_mode & 0o777 == 0o600
    repeated = invoke(
        rt, "documents.render", target={"ref": data["original"]["ref"]}, pages=[1]
    )
    assert not repeated.is_error
    assert repeated.structured_content["data"]["source_sha256"] == data["source_sha256"]


def test_image_crop_and_original_resolution(tmp_path):
    rt = runtime(tmp_path)
    path = tmp_path / "photo.png"
    make_image(path)
    rendered = invoke(
        rt,
        "documents.render",
        target={"path": str(path)},
        mode="original",
        crop={"x": 1500, "y": 200, "width": 500, "height": 300},
    )
    assert not rendered.is_error, rendered.structured_content
    data = rendered.structured_content["data"]
    image = pixels(rendered.content[data["views"][0]["content_index"]])
    assert image.size == (500, 300)
    assert image.getpixel((200, 100)) == (0, 0, 255)
    assert data["width"] == 2400 and data["height"] == 1600
    thumbnail = invoke(
        rt, "documents.render", target={"path": str(path)}, mode="thumbnail"
    )
    assert thumbnail.structured_content["data"]["views"][0]["width"] == 512


@pytest.mark.parametrize(
    "options",
    [
        {},
        {"pages": [0]},
        {"pages": [3]},
        {"pages": [1, 1]},
        {"pages": [1], "crop": {"x": 0, "y": 0, "width": 10, "height": 10}},
    ],
)
def test_pdf_requires_valid_explicit_pages(tmp_path, options):
    rt = runtime(tmp_path)
    path = tmp_path / "example.pdf"
    make_pdf(path)
    result = invoke(rt, "documents.render", target={"path": str(path)}, **options)
    assert result.is_error
    assert result.structured_content["error"]["code"] == "invalid_request"
    assert not list((rt.config.state_dir / "captures").glob("visual-*"))


def test_corrupt_encrypted_and_missing_sources(tmp_path):
    rt = runtime(tmp_path)
    path = tmp_path / "bad.pdf"
    path.write_bytes(b"%PDF-1.7\ninvalid")
    assert invoke(rt, "documents.inspect", target={"path": str(path)}).is_error
    make_pdf(tmp_path / "locked.pdf", encrypted=True)
    locked = invoke(
        rt, "documents.render", target={"path": str(tmp_path / "locked.pdf")}, pages=[1]
    )
    assert locked.structured_content["error"]["code"] == "invalid_request"
    assert "encrypted" in locked.structured_content["error"]["message"]
    missing = invoke(rt, "documents.inspect", target={"path": str(tmp_path / "absent")})
    assert missing.structured_content["error"]["code"] == "not_found"


def test_principal_and_pixel_bounds(tmp_path):
    operator = runtime(tmp_path)
    path = tmp_path / "photo.png"
    make_image(path)
    identifier = register(operator, "image.png", path.read_bytes(), "image")
    from sinnix_agent_gateway.runtime import Runtime

    observer = Runtime.create(operator.config, "observer")
    denied = invoke(observer, "documents.render", target={"artifact_id": identifier})
    assert denied.structured_content["error"]["code"] == "policy_denied"
    pdf = tmp_path / "example.pdf"
    make_pdf(pdf)
    bounded = invoke(
        operator,
        "documents.render",
        target={"path": str(pdf)},
        pages=[1, 2],
        max_edge=8000,
    )
    assert bounded.structured_content["error"]["code"] == "response_bound"


def test_large_image_attach_is_visual_independent_of_text_budget(tmp_path):
    path = tmp_path / "noise.png"
    Image.effect_noise((2200, 2200), 100).convert("RGB").save(path, compress_level=0)
    assert path.stat().st_size > 4 * 1024**2
    artifact, blocks = attach(path, ref="sinnix://synthetic", max_inline_bytes=64_000)
    image = pixels(blocks[0])
    assert max(image.size) <= 1600
    assert artifact.preview and artifact.bytes == path.stat().st_size
    assert artifact.ref == "sinnix://synthetic"


def test_missing_decoder_dependency_is_typed(tmp_path, monkeypatch):
    import subprocess

    def unavailable(*args, **kwargs):
        kwargs["stdout"].write(
            json.dumps(
                {
                    "error": "unavailable",
                    "message": "visual decoding requires Pillow and PyMuPDF",
                }
            ).encode()
        )
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(visual.subprocess, "run", unavailable)
    with pytest.raises(ProtocolError) as exc:
        visual.decode(tmp_path / "file", tmp_path, render=True, pages=[])
    assert exc.value.code == "unavailable"


def test_decoder_timeout_is_typed(tmp_path, monkeypatch):
    import subprocess

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], 30)

    monkeypatch.setattr(visual.subprocess, "run", timeout)
    with pytest.raises(ProtocolError) as exc:
        visual.decode(tmp_path / "file", tmp_path, render=True, pages=[])
    assert exc.value.code == "response_bound"


def test_decoder_without_site_packages_reports_missing_dependency():
    import subprocess
    import sys

    from sinnix_agent_gateway import visual_decoder

    result = subprocess.run(
        [sys.executable, "-I", "-S", visual_decoder.__file__],
        input="{}",
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["error"] == "unavailable"


def test_orientation_coordinates_and_mime_survive_original_capture(tmp_path):
    rt = runtime(tmp_path)
    path = tmp_path / "unlabelled.bin"
    image = Image.new("RGB", (200, 100), "red")
    ImageDraw.Draw(image).rectangle((100, 0, 199, 99), fill="blue")
    exif = image.getexif()
    exif[274] = 6
    image.save(path, format="JPEG", quality=100, exif=exif)
    result = invoke(
        rt,
        "documents.render",
        target={"path": str(path)},
        mode="original",
        crop={"x": 0, "y": 100, "width": 100, "height": 100},
    )
    assert not result.is_error, result.structured_content
    data = result.structured_content["data"]
    assert (data["width"], data["height"]) == (100, 200)
    view = pixels(result.content[data["views"][0]["content_index"]])
    red, green, blue = view.getpixel((50, 50))
    assert blue > 250 and red < 5 and green < 5
    artifact_id = data["original"]["ref"].rsplit("/", 1)[1]
    metadata = rt.artifacts._metadata(artifact_id)
    assert metadata["content_type"] == "image/jpeg"
    assert metadata["_source"].read_bytes() == path.read_bytes()
