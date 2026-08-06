from __future__ import annotations

import base64
import json
import mimetypes
import uuid
from pathlib import Path
from typing import Any

from .capabilities import Capability, Principal
from .config import GatewayConfig


class ArtifactError(ValueError):
    pass


class ArtifactService:
    def __init__(self, config: GatewayConfig, principal: Principal):
        self.config = config
        self.principal = principal
        config.initialize_state()
        self.root = config.state_dir / "artifacts"

    def register(self, source: Path, *, kind: str, owner_id: str) -> str:
        source = source.resolve(strict=True)
        jobs_root = (self.config.state_dir / "jobs").resolve()
        if source != jobs_root and jobs_root not in source.parents:
            raise ArtifactError("artifact source is outside attested job state")
        artifact_id = str(uuid.uuid4())
        directory = self.root / artifact_id
        directory.mkdir(mode=0o700)
        metadata = {
            "artifact_id": artifact_id,
            "kind": kind,
            "owner_id": owner_id,
            "source": str(source),
            "bytes": source.stat().st_size,
            "content_type": mimetypes.guess_type(source.name)[0] or "application/octet-stream",
        }
        metadata_path = directory / "metadata.json"
        metadata_path.write_text(json.dumps(metadata, sort_keys=True) + "\n")
        metadata_path.chmod(0o600)
        return artifact_id

    def _metadata(self, artifact_id: str) -> dict[str, Any]:
        try:
            parsed = uuid.UUID(artifact_id)
        except ValueError as exc:
            raise ArtifactError("invalid artifact ID") from exc
        path = self.root / str(parsed) / "metadata.json"
        try:
            metadata = json.loads(path.read_text())
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            raise ArtifactError("unknown or malformed artifact") from exc
        source = Path(metadata["source"]).resolve(strict=True)
        jobs_root = (self.config.state_dir / "jobs").resolve()
        if jobs_root not in source.parents or not source.is_file():
            raise ArtifactError("artifact source is no longer valid")
        metadata["_source"] = source
        return metadata

    def list(self, limit: int = 100) -> dict[str, Any]:
        self.principal.require(Capability.ARTIFACT_READ)
        rows = []
        for path in sorted(self.root.glob("*/metadata.json"), reverse=True):
            if len(rows) >= max(1, min(limit, 1000)):
                break
            try:
                row = json.loads(path.read_text())
            except json.JSONDecodeError:
                rows.append({"artifact_id": path.parent.name, "malformed": True})
                continue
            row.pop("source", None)
            rows.append(row)
        return {"artifacts": rows}

    def read(self, artifact_id: str, offset: int = 0, max_bytes: int = 64_000) -> dict[str, Any]:
        self.principal.require(Capability.ARTIFACT_READ)
        if offset < 0:
            raise ArtifactError("offset must be non-negative")
        max_bytes = max(1, min(max_bytes, self.config.max_result_bytes))
        metadata = self._metadata(artifact_id)
        source: Path = metadata.pop("_source")
        with source.open("rb") as handle:
            handle.seek(offset)
            data = handle.read(max_bytes + 1)
        truncated = len(data) > max_bytes
        data = data[:max_bytes]
        result = {key: value for key, value in metadata.items() if key != "source"}
        result.update(
            {
                "offset": offset,
                "returned_bytes": len(data),
                "next_offset": offset + len(data) if truncated else None,
                "base64": base64.b64encode(data).decode(),
            }
        )
        return result
