from __future__ import annotations

import base64
import json
import mimetypes
import os
import uuid
from pathlib import Path
from typing import Any

from .capabilities import Capability, Principal
from .config import GatewayConfig
from sinnix_mcp.execution import ExecutionResult
from .redaction import redact


class ArtifactError(ValueError):
    pass


class ArtifactService:
    def __init__(self, config: GatewayConfig, principal: Principal):
        self.config = config
        self.principal = principal
        config.initialize_state()
        self.root = config.state_dir / "artifacts"

    def _source_is_attested(self, source: Path) -> bool:
        for directory_name, schema, identifier in (
            ("captures", "sinnix.gateway-capture-receipt.v1", "capture_id"),
            ("diagnostics", "sinnix.gateway-diagnostic-receipt.v1", "diagnostic_id"),
        ):
            root = (self.config.state_dir / directory_name).resolve()
            if source == root or root not in source.parents:
                continue
            try:
                receipt = json.loads((source.parent / "receipt.json").read_text())
            except (OSError, json.JSONDecodeError):
                continue
            if (
                receipt.get("schema") == schema
                and isinstance(receipt.get(identifier), str)
                and isinstance(receipt.get("files"), list)
                and source.name in receipt["files"]
            ):
                return True
        return False

    def attest_capture(
        self,
        directory: Path,
        *,
        source: str,
        target: dict[str, Any],
        files: list[Path],
    ) -> dict[str, Any]:
        directory = directory.resolve(strict=True)
        captures_root = (self.config.state_dir / "captures").resolve()
        if directory == captures_root or captures_root not in directory.parents:
            raise ArtifactError("capture directory is outside attested gateway state")
        if not isinstance(source, str) or not source or not isinstance(target, dict):
            raise ArtifactError("capture receipt is malformed")
        names = []
        for file in files:
            file = file.resolve(strict=True)
            if file.parent != directory or not file.is_file():
                raise ArtifactError("capture file is outside its declared capture directory")
            names.append(file.name)
        if not names or len(names) != len(set(names)):
            raise ArtifactError("capture receipt must identify distinct files")
        receipt = {
            "schema": "sinnix.gateway-capture-receipt.v1",
            "capture_id": str(uuid.uuid4()),
            "source": source,
            "target": target,
            "files": names,
        }
        output = directory / "receipt.json"
        temporary = directory / f".{output.name}.{uuid.uuid4().hex}.tmp"
        try:
            temporary.write_text(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
            temporary.chmod(0o600)
            os.replace(temporary, output)
        finally:
            temporary.unlink(missing_ok=True)
        return receipt

    def record_owner_diagnostic(
        self, route: str, result: ExecutionResult
    ) -> dict[str, object]:
        """Persist a bounded direct-owner failure without storing request input."""
        if not route or result.failure_class is None:
            raise ArtifactError("owner diagnostic requires a failed route result")
        diagnostic_id = str(uuid.uuid4())
        directory = self.config.state_dir / "diagnostics" / diagnostic_id
        directory.mkdir(mode=0o700, parents=True)
        source = directory / "diagnostic.json"
        diagnostic = {
            "schema": "sinnix.gateway-owner-diagnostic.v1",
            "route": route,
            "failure_class": result.failure_class,
            "exit_status": result.exit_status,
            "timed_out": result.timed_out,
            "output_exceeded": result.output_exceeded,
            "stdout_bytes": len(result.stdout),
            "stderr_bytes": len(result.stderr),
            "stderr_excerpt": redact(result.stderr_excerpt()),
        }
        source.write_text(json.dumps(diagnostic, sort_keys=True, separators=(",", ":")))
        source.chmod(0o600)
        receipt = {
            "schema": "sinnix.gateway-diagnostic-receipt.v1",
            "diagnostic_id": diagnostic_id,
            "route": route,
            "files": [source.name],
        }
        receipt_path = directory / "receipt.json"
        receipt_path.write_text(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
        receipt_path.chmod(0o600)
        artifact_id = self.register(
            source,
            kind="owner-diagnostic",
            owner_id=route,
        )
        return {
            "available": False,
            "failure_class": result.failure_class,
            "route": route,
            "exit_status": result.exit_status,
            "timed_out": result.timed_out,
            "output_exceeded": result.output_exceeded,
            "diagnostic_artifact_id": artifact_id,
        }

    def register(self, source: Path, *, kind: str, owner_id: str) -> str:
        source = source.resolve(strict=True)
        if not source.is_file() or not self._source_is_attested(source):
            raise ArtifactError("artifact source is outside attested gateway state")
        artifact_id = str(uuid.uuid4())
        directory = self.root / artifact_id
        directory.mkdir(mode=0o700)
        metadata = {
            "artifact_id": artifact_id,
            "kind": kind,
            "owner_id": owner_id,
            "principal": self.principal.name,
            "source": str(source),
            "bytes": source.stat().st_size,
            "content_type": mimetypes.guess_type(source.name)[0]
            or "application/octet-stream",
        }
        metadata_path = directory / "metadata.json"
        metadata_path.write_text(json.dumps(metadata, sort_keys=True) + "\n")
        metadata_path.chmod(0o600)
        return artifact_id

    def register_json(
        self,
        payload: Any,
        *,
        kind: str,
        owner_id: str,
        source: str,
        target: dict[str, Any],
    ) -> dict[str, Any]:
        """Persist bounded metadata about an oversized JSON response as an artifact."""
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        directory = self.config.state_dir / "captures" / uuid.uuid4().hex
        directory.mkdir(mode=0o700, parents=True)
        source_path = directory / f"{kind}.json"
        source_path.write_bytes(encoded)
        receipt = self.attest_capture(
            directory, source=source, target=target, files=[source_path]
        )
        artifact_id = self.register(source_path, kind=kind, owner_id=owner_id)
        return {
            "artifact_id": artifact_id,
            "ref": f"sinnix://artifacts/{artifact_id}",
            "bytes": len(encoded),
            "content_type": "application/json",
            "receipt": {
                "capture_id": receipt["capture_id"],
                "source": receipt["source"],
                "target": receipt["target"],
            },
        }

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
        if self.principal.name != "operator" and metadata.get("principal") != self.principal.name:
            raise ArtifactError("artifact is unavailable to this principal")
        source = Path(metadata["source"]).resolve(strict=True)
        if not source.is_file() or not self._source_is_attested(source):
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
                if self.principal.name == "operator":
                    rows.append({"artifact_id": path.parent.name, "malformed": True})
                continue
            if self.principal.name != "operator" and row.get("principal") != self.principal.name:
                continue
            row.pop("source", None)
            rows.append(row)
        return {"artifacts": rows}

    def read(
        self, artifact_id: str, offset: int = 0, max_bytes: int = 64_000
    ) -> dict[str, Any]:
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
