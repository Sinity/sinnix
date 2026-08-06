from __future__ import annotations

import json
import os
import re
import uuid
import subprocess
import time
from pathlib import Path
from typing import Any

from .artifacts import ArtifactService
from .capabilities import Capability, Principal
from .config import GatewayConfig
from .schemas import AgentLaunchRequest


JOB_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


class JobError(ValueError):
    pass


class JobService:
    def __init__(
        self,
        config: GatewayConfig,
        principal: Principal,
        artifacts: ArtifactService,
    ):
        self.config = config
        self.principal = principal
        self.artifacts = artifacts
        config.initialize_state()
        self.root = config.state_dir / "jobs"

    def _environment(self) -> dict[str, str]:
        allowed_names = {
            "DBUS_SESSION_BUS_ADDRESS",
            "DISPLAY",
            "HOME",
            "LANG",
            "LC_ALL",
            "PATH",
            "SHELL",
            "SSH_AUTH_SOCK",
            "TERM",
            "USER",
            "WAYLAND_DISPLAY",
            "XDG_CONFIG_HOME",
            "XDG_DATA_HOME",
            "XDG_RUNTIME_DIR",
            "XDG_STATE_HOME",
        }
        environment = {
            name: value for name, value in os.environ.items() if name in allowed_names
        }
        environment["SINNIX_AGENT_JOB_STATE_DIR"] = str(self.root)
        return environment

    def _manifest_path(self, job_id: str) -> Path:
        if not JOB_ID_RE.fullmatch(job_id):
            raise JobError("invalid job ID")
        return self.root / f"{job_id}.json"

    def _load(self, job_id: str) -> dict[str, Any]:
        path = self._manifest_path(job_id)
        try:
            value = json.loads(path.read_text())
        except FileNotFoundError as exc:
            raise JobError("unknown job ID") from exc
        except json.JSONDecodeError as exc:
            raise JobError("malformed job manifest") from exc
        if value.get("schema_version") != 2 or value.get("job_id") != job_id:
            raise JobError("unattested job manifest")
        return value

    def launch_agent(self, request: AgentLaunchRequest) -> dict[str, Any]:
        self.principal.require(Capability.JOB_START)
        try:
            project = self.config.projects[request.project_id]
        except KeyError as exc:
            raise JobError(f"unknown project: {request.project_id}") from exc
        if not project.path.is_dir():
            raise JobError("project checkout is unavailable")
        if not self.config.agent_runner.is_file():
            raise JobError("agent runner is unavailable")

        job_id = str(uuid.uuid4())
        prompt_path = self.root / f"{job_id}.prompt.md"
        log_path = self.root / f"{job_id}.log"
        final_path = self.root / f"{job_id}.final.md"
        prompt_path.write_text(request.prompt)
        prompt_path.chmod(0o600)
        command = [
            str(self.config.agent_runner),
            "--agent",
            request.backend,
            "--workdir",
            str(project.path),
            "--prompt-file",
            str(prompt_path),
            "--log-file",
            str(log_path),
            "--last-file",
            str(final_path),
            "--job-id",
            job_id,
            "--job-state-dir",
            str(self.root),
            "--timeout-seconds",
            str(request.timeout_seconds),
            "--credential-profile",
            request.credential_profile,
        ]
        model = request.model
        effort = request.reasoning_effort
        if request.backend == "codex" and model is None:
            model = "gpt-5.6-terra"
        if request.backend == "grok" and model is None:
            model = "grok-4.5"
        if request.backend == "antigravity" and model is None:
            model = "gemini-3.1-pro-high"
        if request.backend in {"grok", "antigravity"} and effort is None:
            effort = "high"
        if model:
            command.extend(["--model", model])
        if effort:
            command.extend(["--reasoning-effort", effort])
        if request.job_role:
            command.extend(["--job-role", request.job_role])
        if request.work_item:
            command.extend(["--work-item", request.work_item])

        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                env={
                    **self._environment(),
                    "SINNIX_CORRELATION_ID": job_id,
                    "SINNIX_PROJECT": request.project_id,
                    **({"SINNIX_WORK_ITEM": request.work_item} if request.work_item else {}),
                },
            )
        except OSError as exc:
            raise JobError("failed to launch attested agent job") from exc
        manifest = self._manifest_path(job_id)
        for _ in range(40):
            if manifest.exists() or process.poll() is not None:
                break
            time.sleep(0.05)
        return {
            "job_id": job_id,
            "accepted": True,
            "backend": request.backend,
            "project_id": request.project_id,
        }

    def _live(self, manifest: dict[str, Any]) -> dict[str, Any]:
        unit = manifest.get("launcher", {}).get("scope_unit")
        if not isinstance(unit, str) or not unit:
            return {"available": False, "reason": "missing attested unit"}
        result = subprocess.run(
            [
                "systemctl",
                "--user",
                "show",
                unit,
                "--property=ActiveState",
                "--property=SubState",
                "--property=MainPID",
                "--property=ControlGroup",
                "--property=InvocationID",
                "--property=MemoryCurrent",
                "--property=MemoryPeak",
                "--property=CPUUsageNSec",
                "--property=Result",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            text=True,
            env=self._environment(),
        )
        if result.returncode != 0:
            return {"available": False, "reason": "unit unavailable"}
        return {
            "available": True,
            **dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line),
        }

    def status(self, job_id: str) -> dict[str, Any]:
        self.principal.require(Capability.JOB_READ)
        manifest = self._load(job_id)
        sanitized = json.loads(json.dumps(manifest))
        for section in ("prompt", "artifacts"):
            if isinstance(sanitized.get(section), dict):
                for key in list(sanitized[section]):
                    if key == "sha256":
                        continue
                    sanitized[section][key] = bool(sanitized[section][key])
        sanitized.pop("repo", None)
        sanitized.pop("worktree", None)
        sanitized["live"] = self._live(manifest)
        return sanitized

    def list(self, limit: int = 100) -> dict[str, Any]:
        self.principal.require(Capability.JOB_READ)
        jobs: list[dict[str, Any]] = []
        malformed: list[dict[str, str]] = []
        paths = sorted(self.root.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
        for path in paths[: max(1, min(limit, 1000))]:
            try:
                value = json.loads(path.read_text())
                job_id = value.get("job_id")
                if value.get("schema_version") != 2 or not isinstance(job_id, str):
                    raise ValueError("invalid manifest contract")
                jobs.append(self.status(job_id))
            except (ValueError, json.JSONDecodeError, JobError) as exc:
                malformed.append({"record": path.name, "error": str(exc)})
        return {"jobs": jobs, "malformed_records": malformed}

    def cancel(self, job_id: str) -> dict[str, Any]:
        self.principal.require(Capability.JOB_CANCEL)
        self._load(job_id)
        if not self.config.agent_controller.is_file():
            raise JobError("agent controller is unavailable")
        result = subprocess.run(
            [
                str(self.config.agent_controller),
                "--state-dir",
                str(self.root),
                "interrupt",
                "--job",
                job_id,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            text=True,
            env=self._environment(),
        )
        if result.returncode != 0:
            raise JobError(result.stderr.strip() or "job cancellation was refused")
        return {"job_id": job_id, "cancelled": True, "lifecycle": "cancelled"}

    def read_output(
        self, job_id: str, artifact: str = "log", offset: int = 0, max_bytes: int = 64_000
    ) -> dict[str, Any]:
        self.principal.require(Capability.JOB_READ)
        if artifact not in {"log", "final", "json"}:
            raise JobError("artifact must be log, final, or json")
        manifest = self._load(job_id)
        raw = manifest.get("artifacts", {}).get(artifact)
        if not raw:
            raise JobError("job artifact is unavailable")
        source = Path(raw).resolve(strict=True)
        root = self.root.resolve()
        if root not in source.parents or not source.is_file():
            raise JobError("job artifact failed path attestation")
        artifact_id = self.artifacts.register(source, kind=artifact, owner_id=job_id)
        return self.artifacts.read(artifact_id, offset=offset, max_bytes=max_bytes)
