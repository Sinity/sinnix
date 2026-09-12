"""Bounded image/PDF decoder, invoked in its own process by visual.py."""

from __future__ import annotations

import io
import json
import resource
import sys
import warnings
from pathlib import Path

SOURCE_PIXELS = 80_000_000
OUTPUT_PIXELS = 16_000_000


class DecodeError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _encode(image, destination: Path, budget: int, *, original: bool) -> dict:
    from PIL import Image

    # Re-encode to strip EXIF/location and prevent active/animated payloads.
    image = image.convert("RGB")
    for _attempt in range(8):
        output = io.BytesIO()
        image.save(output, format="PNG")
        data, media, suffix = output.getvalue(), "image/png", ".png"
        if len(data) > budget:
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=85)
            data, media, suffix = output.getvalue(), "image/jpeg", ".jpg"
        if len(data) <= budget:
            path = destination.with_suffix(suffix)
            path.write_bytes(data)
            path.chmod(0o600)
            return {
                "name": path.name,
                "width": image.width,
                "height": image.height,
                "media_type": media,
                "bytes": len(data),
            }
        if original:
            break
        image.thumbnail(
            (max(1, int(image.width * 0.7)), max(1, int(image.height * 0.7))),
            Image.Resampling.LANCZOS,
        )
    raise DecodeError(
        "response_bound", "image exceeds the inline byte budget; request a smaller view"
    )


def decode(request: dict) -> dict:
    from PIL import Image, ImageOps

    Image.MAX_IMAGE_PIXELS = SOURCE_PIXELS
    warnings.simplefilter("error", Image.DecompressionBombWarning)
    path = Path(request["path"])
    render = request["render"]
    pages = request["pages"]
    if pages:
        raise DecodeError(
            "invalid_request",
            "pages applies only to PDFs, which travel as binary resources",
        )
    with Image.open(path) as image:
        if image.width * image.height > SOURCE_PIXELS:
            raise DecodeError(
                "response_bound", "image exceeds 80 million source pixels"
            )
        if pages:
            raise DecodeError("invalid_request", "pages applies only to PDFs")
        orientation = image.getexif().get(274, 1)
        width, height = image.size
        if orientation in (5, 6, 7, 8):
            width, height = height, width
        result = {
            "width": width,
            "height": height,
            "frame_count": getattr(image, "n_frames", 1),
            "pages": [],
            "renders": [],
        }
        if not render:
            return result
        crop = request["crop"]
        output_pixels = crop["width"] * crop["height"] if crop else width * height
        if request["mode"] == "original" and output_pixels > OUTPUT_PIXELS:
            raise DecodeError(
                "response_bound",
                "original view exceeds 16 million pixels; request a crop or fit",
            )
        if crop and (
            crop["x"] + crop["width"] > width or crop["y"] + crop["height"] > height
        ):
            raise DecodeError(
                "invalid_request", "crop is outside the orientation-corrected image"
            )
        # JPEG draft reduces decode work before resizing, without affecting crop coordinates.
        edge = (
            min(request["max_edge"], 512)
            if request["mode"] == "thumbnail"
            else request["max_edge"]
        )
        if not crop and request["mode"] != "original":
            image.draft("RGB", (edge, edge))
        image = ImageOps.exif_transpose(image)
        if crop:
            image = image.crop(
                (
                    crop["x"],
                    crop["y"],
                    crop["x"] + crop["width"],
                    crop["y"] + crop["height"],
                )
            )
        if request["mode"] != "original":
            image.thumbnail((edge, edge), Image.Resampling.LANCZOS)
        if image.width * image.height > OUTPUT_PIXELS:
            raise DecodeError("response_bound", "view exceeds 16 million output pixels")
        result["renders"] = [
            _encode(
                image,
                Path(request["directory"]) / "image",
                request["budget"],
                original=request["mode"] == "original",
            )
        ]
        return result


def main() -> None:
    # Native parsers handle untrusted compressed data. Limit this disposable decoder,
    # never the gateway process, including expansion inside embedded PDF images.
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (25, 25))
    resource.setrlimit(resource.RLIMIT_FSIZE, (8 * 1024**2, 8 * 1024**2))
    try:
        request = json.loads(sys.stdin.read(32_768))
        result = decode(request)
        print(json.dumps(result))
    except ImportError:
        print(
            json.dumps(
                {
                    "error": "unavailable",
                    "message": "visual image decoding requires Pillow",
                }
            )
        )
    except DecodeError as exc:
        print(json.dumps({"error": exc.code, "message": str(exc)}))
    except (MemoryError, OverflowError):
        print(
            json.dumps(
                {
                    "error": "response_bound",
                    "message": "document exceeds decoder memory bounds",
                }
            )
        )
    except Exception:
        # Parser errors may embed document content; keep the response private by construction.
        print(
            json.dumps(
                {
                    "error": "invalid_request",
                    "message": "image or PDF is corrupt, unsupported, or exceeds safe decode limits",
                }
            )
        )


if __name__ == "__main__":
    main()
