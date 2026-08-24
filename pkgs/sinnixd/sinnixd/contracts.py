from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import UUID, uuid4

from .jobs import GenericJobSpec, GenericJobs
from .limits import maximum_timeout_seconds, valid_timeout_seconds
from .projects import ProjectCatalog, RegisteredCheckout


MAX_PROMPT_BYTES = 200_000
AGENT_BACKENDS = frozenset({"claude", "codex", "gemini", "grok", "antigravity"})
CREDENTIAL_PROFILES = frozenset({"subscription", "api"})


class ContractError(ValueError):
    """A typed job request would widen the shared systemd authority."""


def contract_runner_executable() -> Path:
    configured = os.environ.get("SINNIXD_CONTRACT_RUNNER")
    if configured:
        return Path(configured)
    module_path = Path(__file__).resolve()
    if len(module_path.parents) > 4 and module_path.parents[3].name == "lib":
        return module_path.parents[4] / "bin" / "sinnixd-contract-runner"
    return Path(os.sys.executable).with_name("sinnixd-contract-runner")


@dataclass(frozen=True)
class TypedJobContracts:
    """Construct redacted durable specs and private launch inputs for typed jobs."""

    projects: ProjectCatalog
    jobs: GenericJobs
    native_runner: Path

    @property
    def inputs_root(self) -> Path:
        return self.jobs.store.root / "inputs"

    def start_shell(
        self,
        *,
        principal: str,
        project_id: str,
        checkout_id: str,
        argv: Sequence[str],
        cwd: str,
        timeout_seconds: int,
        result: str,
    ) -> dict[str, Any]:
        if principal != "operator":
            raise ContractError("operator shell jobs require the operator principal")
        if result != "exit-status":
            raise ContractError("operator shell jobs require an exit-status result")
        if not argv or len(argv) > 128 or any(not isinstance(item, str) or not item for item in argv):
            raise ContractError("shell argv must contain 1-128 non-empty strings")
        if sum(len(item) for item in argv) > 32_768:
            raise ContractError("shell argv exceeds the configured bound")
        checkout = self.projects.checkout(project_id, checkout_id)
        workdir = self._working_directory(checkout, cwd)
        job_id = str(uuid4())
        public_contract = {
            "identity": "user",
            "argv": {
                "count": len(argv),
                "executable": argv[0],
                "sha256": self._digest(argv),
            },
            "cwd": str(workdir),
            "result": result,
        }
        private = {
            "schema_version": 1,
            "job_id": job_id,
            "kind": "operator-shell",
            "principal": principal,
            "checkout": checkout.to_dict(),
            "cwd": str(workdir),
            "argv": list(argv),
        }
        return self._start(
            job_id=job_id,
            kind="operator-shell",
            principal=principal,
            checkout=checkout,
            public_contract=public_contract,
            private=private,
            timeout_seconds=timeout_seconds,
            result_kind=result,
        )

    def start_agent(
        self,
        *,
        principal: str,
        project_id: str,
        checkout_id: str,
        prompt: str,
        backend: str,
        model: str,
        effort: str,
        credential_profile: str,
        timeout_seconds: int,
        result: str,
        bead_binding: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if principal not in {"agent-control", "operator"}:
            raise ContractError(
                "attested agent jobs require the agent-control or operator principal"
            )
        if backend not in AGENT_BACKENDS:
            raise ContractError("agent backend is invalid")
        if not isinstance(model, str) or not model or len(model) > 256:
            raise ContractError("agent model must be a non-empty string up to 256 characters")
        if not isinstance(effort, str) or not effort or len(effort) > 32:
            raise ContractError("agent effort must be a non-empty string up to 32 characters")
        if credential_profile not in CREDENTIAL_PROFILES:
            raise ContractError("agent credential profile is invalid")
        if result != "last-message":
            raise ContractError("attested agent jobs require a last-message result")
        if not isinstance(prompt, str) or not prompt or len(prompt.encode()) > MAX_PROMPT_BYTES:
            raise ContractError(f"agent prompt must be non-empty and at most {MAX_PROMPT_BYTES} bytes")
        if not self.native_runner.is_file() or not os.access(self.native_runner, os.X_OK):
            raise ContractError("native agent runner is unavailable")
        checkout = self.projects.checkout(project_id, checkout_id)
        binding = self._bead_binding(bead_binding, checkout)
        job_id = str(uuid4())
        prompt_path = self.inputs_root / f"{job_id}.prompt"
        public_contract = {
            "backend": backend,
            "model": model,
            "effort": effort,
            "credential_profile": credential_profile,
            "prompt": {"sha256": hashlib.sha256(prompt.encode()).hexdigest(), "bytes": len(prompt.encode())},
            "result": result,
            **({"bead_binding": binding} if binding is not None else {}),
        }
        private = {
            "schema_version": 1,
            "job_id": job_id,
            "kind": "attested-agent",
            "principal": principal,
            "checkout": checkout.to_dict(),
            "backend": backend,
            "model": model,
            "effort": effort,
            "credential_profile": credential_profile,
            "prompt_path": str(prompt_path),
            **({"bead_binding": binding} if binding is not None else {}),
        }
        self._write_private(prompt_path, prompt.encode())
        try:
            return self._start(
                job_id=job_id,
                kind="attested-agent",
                principal=principal,
                checkout=checkout,
                public_contract=public_contract,
                private=private,
                timeout_seconds=timeout_seconds,
                result_kind=result,
            )
        except BaseException:
            prompt_path.unlink(missing_ok=True)
            raise

    def _start(
        self,
        *,
        job_id: str,
        kind: str,
        principal: str,
        checkout: RegisteredCheckout,
        public_contract: Mapping[str, Any],
        private: Mapping[str, Any],
        timeout_seconds: int,
        result_kind: str,
    ) -> dict[str, Any]:
        maximum_timeout = maximum_timeout_seconds(kind)
        if not valid_timeout_seconds(timeout_seconds, kind=kind):
            raise ContractError(f"job timeout_seconds must be between 1 and {maximum_timeout}")
        input_path = self.inputs_root / f"{job_id}.json"
        self._write_private(input_path, json.dumps(private, sort_keys=True, separators=(",", ":")).encode())
        environment = self._environment(checkout, job_id, principal, timeout_seconds)
        command = (
            str(contract_runner_executable()),
            "--input",
            str(input_path),
            "--job-id",
            job_id,
            "--unit",
            f"sinnixd-job-{job_id}.service",
            "--native-runner",
            str(self.native_runner),
            "--state-root",
            str(self.jobs.store.root),
        )
        result_path = self.jobs.store.results_root / f"{job_id}.result"
        if result_kind == "last-message":
            private = {**private, "result_path": str(result_path)}
            self._write_private(input_path, json.dumps(private, sort_keys=True, separators=(",", ":")).encode())
        try:
            response = self.jobs.start(
                GenericJobSpec(
                    kind=kind,
                    command=command,
                    working_directory=str(checkout.path),
                    environment=environment,
                    timeout_seconds=timeout_seconds,
                    project_id=checkout.project_id,
                    principal=principal,
                    checkout=checkout.to_dict(),
                    contract=public_contract,
                    result_kind=result_kind,
                ),
                job_id,
            )
        except BaseException:
            input_path.unlink(missing_ok=True)
            prompt_path = private.get("prompt_path")
            if isinstance(prompt_path, str):
                Path(prompt_path).unlink(missing_ok=True)
            raise
        if response["state"]["phase"] == "launch-failed":
            input_path.unlink(missing_ok=True)
            prompt_path = private.get("prompt_path")
            if isinstance(prompt_path, str):
                Path(prompt_path).unlink(missing_ok=True)
        return response

    @staticmethod
    def _bead_binding(
        value: Mapping[str, Any] | None, checkout: RegisteredCheckout
    ) -> dict[str, Any] | None:
        """Validate public Beads provenance carried by an attested agent job."""
        if value is None:
            return None
        expected = {
            "bead_ref", "project_ref", "checkout_ref", "task_revision",
            "task_etag", "claim_ref", "claim_receipt", "request_id", "work_item",
        }
        if not isinstance(value, Mapping) or set(value) != expected:
            raise ContractError("agent bead binding is malformed")
        binding = dict(value)
        project_ref = f"sinnix://projects/{checkout.project_id}"
        checkout_ref = f"{project_ref}/checkouts/{checkout.checkout_id}"
        bead_prefix = f"{project_ref}/beads/"
        bead_ref = binding["bead_ref"]
        if (
            not isinstance(bead_ref, str)
            or not bead_ref.startswith(bead_prefix)
            or not bead_ref.removeprefix(bead_prefix)
            or "/" in bead_ref.removeprefix(bead_prefix)
            or binding["project_ref"] != project_ref
            or binding["checkout_ref"] != checkout_ref
            or not isinstance(binding["task_revision"], str)
            or len(binding["task_revision"]) != 64
            or not isinstance(binding["task_etag"], str)
            or len(binding["task_etag"]) != 64
            or binding["work_item"] is not None and (not isinstance(binding["work_item"], str) or len(binding["work_item"]) > 2_000)
        ):
            raise ContractError("agent bead binding is malformed")
        claim_ref = binding["claim_ref"]
        claim_receipt = binding["claim_receipt"]
        if (claim_ref is None) != (claim_receipt is None):
            raise ContractError("agent bead binding claim is malformed")
        if claim_ref is not None and (
            not isinstance(claim_ref, str)
            or not claim_ref.startswith(f"{bead_ref}/claims/")
            or not claim_ref.removeprefix(f"{bead_ref}/claims/")
            or "/" in claim_ref.removeprefix(f"{bead_ref}/claims/")
            or not isinstance(claim_receipt, Mapping)
            or claim_receipt.get("ref") != claim_ref
        ):
            raise ContractError("agent bead binding claim is malformed")
        if any(character not in "0123456789abcdef" for character in binding["task_revision"] + binding["task_etag"]):
            raise ContractError("agent bead binding is malformed")
        try:
            UUID(str(binding["request_id"]))
        except (TypeError, ValueError, AttributeError) as error:
            raise ContractError("agent bead binding request_id is malformed") from error
        return binding

    def _environment(
        self, checkout: RegisteredCheckout, job_id: str, principal: str, timeout_seconds: int
    ) -> dict[str, str]:
        project = self.projects.get(checkout.project_id)
        environment = project.environment.values()
        forbidden = sorted(name for name in environment if name.startswith("SINNIX"))
        if forbidden:
            raise ContractError("project environment cannot supply SINNIX identity variables")
        environment.update(
            {
                "SINNIXD_JOB_ID": job_id,
                "SINNIXD_PROJECT_ID": checkout.project_id,
                "SINNIXD_CHECKOUT_ID": checkout.checkout_id,
                "SINNIXD_PRINCIPAL": principal,
                "SINNIXD_TIMEOUT_SECONDS": str(timeout_seconds),
            }
        )
        return environment

    @staticmethod
    def _working_directory(checkout: RegisteredCheckout, cwd: str) -> Path:
        candidate = Path(cwd)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ContractError("shell cwd must be a relative path inside the registered checkout")
        try:
            resolved = (checkout.path / candidate).resolve(strict=True)
        except FileNotFoundError as error:
            raise ContractError("shell cwd does not exist") from error
        if not resolved.is_dir() or (resolved != checkout.path and checkout.path not in resolved.parents):
            raise ContractError("shell cwd must be a directory inside the registered checkout")
        return resolved

    def _write_private(self, path: Path, content: bytes) -> None:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def cleanup_terminal(self, response: Mapping[str, Any]) -> dict[str, Any]:
        """Remove private typed-job inputs once systemd records a terminal outcome."""
        state = response.get("state")
        job_id = response.get("job_id")
        if (
            response.get("kind") not in {"operator-shell", "attested-agent"}
            or not isinstance(state, Mapping)
            or not state.get("terminal")
            or not isinstance(job_id, str)
        ):
            return dict(response)
        (self.inputs_root / f"{job_id}.json").unlink(missing_ok=True)
        (self.inputs_root / f"{job_id}.prompt").unlink(missing_ok=True)
        return dict(response)

    @staticmethod
    def _digest(argv: Sequence[str]) -> str:
        return hashlib.sha256("\0".join(argv).encode()).hexdigest()
