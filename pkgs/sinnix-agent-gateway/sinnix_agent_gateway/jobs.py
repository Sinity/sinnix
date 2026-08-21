from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import tempfile
import time
import uuid
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

    def _authorized_agent_worktree(
        self, project_path: Path, requested: str | None
    ) -> Path:
        registered = project_path.resolve(strict=True)
        if requested is None:
            return registered
        try:
            candidate = Path(requested).expanduser().resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise JobError("requested worktree is unavailable") from exc
        if not candidate.is_dir():
            raise JobError("requested worktree is not a directory")
        if candidate == registered:
            return candidate

        def git_value(path: Path, *args: str) -> str:
            result = subprocess.run(
                ["git", "-C", str(path), *args],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                check=False,
                text=True,
            )
            if result.returncode != 0:
                raise JobError("requested worktree is not a Git worktree")
            return result.stdout.strip()

        try:
            candidate_root = Path(
                git_value(
                    candidate, "rev-parse", "--path-format=absolute", "--show-toplevel"
                )
            ).resolve(strict=True)
            candidate_common = Path(
                git_value(
                    candidate, "rev-parse", "--path-format=absolute", "--git-common-dir"
                )
            ).resolve(strict=True)
            registered_common = Path(
                git_value(
                    registered, "rev-parse", "--path-format=absolute", "--git-common-dir"
                )
            ).resolve(strict=True)
        except (OSError, RuntimeError, ValueError) as exc:
            raise JobError("requested worktree has an invalid Git identity") from exc
        if candidate_root != candidate or candidate_common != registered_common:
            raise JobError("requested worktree is not linked to the registered project")

        listed = subprocess.run(
            ["git", "-C", str(registered), "worktree", "list", "--porcelain"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            text=True,
        )
        if listed.returncode != 0:
            raise JobError("could not attest registered project worktrees")
        worktree_paths = {
            Path(line.removeprefix("worktree ")).resolve()
            for line in listed.stdout.splitlines()
            if line.startswith("worktree ")
        }
        if candidate not in worktree_paths:
            raise JobError("requested path is not a linked Git worktree")
        return candidate

    @staticmethod
    def _shell_environment(overlay: dict[str, str] | None) -> dict[str, str]:
        environment = {
            "HOME": os.environ.get("HOME", "/home/sinity"),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "PATH": os.environ.get("PATH", "/run/current-system/sw/bin"),
        }
        for name in ("DBUS_SESSION_BUS_ADDRESS", "WAYLAND_DISPLAY", "XDG_RUNTIME_DIR"):
            value = os.environ.get(name)
            if value:
                environment[name] = value
        if overlay is None:
            return environment
        if len(overlay) > 64:
            raise JobError("environment overlay has more than 64 variables")
        for name, value in overlay.items():
            if not name or not name.replace("_", "a").isalnum() or not name[0].isalpha():
                raise JobError(f"invalid environment variable name: {name!r}")
            if not isinstance(value, str) or len(value) > 8_192:
                raise JobError(f"invalid environment value for {name}")
            environment[name] = value
        return environment

    @staticmethod
    def _shell_request(
        argv: list[str], cwd: str, timeout_seconds: int, environment: dict[str, str] | None
    ) -> tuple[Path, dict[str, Any]]:
        if not argv or len(argv) > 128 or any(not isinstance(arg, str) for arg in argv):
            raise JobError("argv must contain 1-128 string arguments")
        if sum(len(arg) for arg in argv) > 32_768:
            raise JobError("argv exceeds the configured bound")
        if timeout_seconds < 30 or timeout_seconds > 86_400:
            raise JobError("timeout_seconds must be 30-86400")
        workdir = Path(cwd).expanduser().resolve(strict=True)
        if not workdir.is_dir():
            raise JobError("cwd is not a directory")
        return workdir, {
            "argv": argv,
            "cwd": str(workdir),
            "timeout_seconds": timeout_seconds,
            "environment": environment,
        }

    @staticmethod
    def _proc_start(pid: int) -> str:
        try:
            stat = Path(f"/proc/{pid}/stat").read_text()
        except OSError:
            return ""
        fields = stat.rsplit(") ", 1)[-1].split()
        return fields[19] if len(fields) >= 20 else ""

    @staticmethod
    def _cgroup_for_pid(pid: int) -> str:
        try:
            for line in Path(f"/proc/{pid}/cgroup").read_text().splitlines():
                hierarchy, _, cgroup = line.partition("::")
                if hierarchy == "0":
                    return cgroup
        except OSError:
            pass
        return ""

    def _manifest_path(self, job_id: str) -> Path:
        if not JOB_ID_RE.fullmatch(job_id):
            raise JobError("invalid job ID")
        return self.root / f"{job_id}.json"

    @staticmethod
    def _abort_launch(process: subprocess.Popen[bytes]) -> None:
        if process.poll() is not None:
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=1)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=1)
            except ProcessLookupError:
                pass

    def _load(self, job_id: str) -> dict[str, Any]:
        path = self._manifest_path(job_id)
        try:
            value = json.loads(path.read_text())
        except FileNotFoundError as exc:
            raise JobError("unknown job ID") from exc
        except json.JSONDecodeError as exc:
            raise JobError("malformed job manifest") from exc
        version = value.get("schema_version")
        if version not in {2, 3, 4} or value.get("job_id") != job_id:
            raise JobError("unattested job manifest")
        if version == 4 and value.get("kind") != "shell":
            raise JobError("unattested execution job manifest")
        return value

    def launch_agent(self, request: AgentLaunchRequest) -> dict[str, Any]:
        self.principal.require(Capability.JOB_START)
        try:
            project = self.config.projects[request.project_id]
        except KeyError as exc:
            raise JobError(f"unknown project: {request.project_id}") from exc
        if not project.path.is_dir():
            raise JobError("project checkout is unavailable")
        worktree = self._authorized_agent_worktree(project.path, request.worktree)
        common_result = subprocess.run(
            [
                "git",
                "-C",
                str(project.path.resolve()),
                "rev-parse",
                "--path-format=absolute",
                "--git-common-dir",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            text=True,
        )
        expected_git_common_dir = ""
        if common_result.returncode == 0:
            expected_git_common_dir = str(Path(common_result.stdout.strip()).resolve())
        if not self.config.agent_runner.is_file():
            raise JobError("agent runner is unavailable")

        job_id = str(uuid.uuid4())
        launch_id = secrets.token_hex(16)
        prompt_path = self.root / f"{job_id}.{launch_id}.prompt.md"
        log_path = self.root / f"{job_id}.log"
        final_path = self.root / f"{job_id}.final.md"
        prompt_path.write_text(request.prompt)
        prompt_path.chmod(0o600)
        command = [
            str(self.config.agent_runner),
            "--agent",
            request.backend,
            "--workdir",
            str(worktree),
            "--registered-project",
            str(project.path.resolve()),
            "--expected-git-common-dir",
            expected_git_common_dir,
            "--prompt-file",
            str(prompt_path),
            "--log-file",
            str(log_path),
            "--last-file",
            str(final_path),
            "--job-id",
            job_id,
            "--launch-id",
            launch_id,
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
        for option, value in (
            ("--parent-job-id", request.parent_job_id),
            ("--coordinator-job-id", request.coordinator_job_id),
            ("--provider", request.provider),
            ("--account-hash", request.account_hash),
            ("--vendor-session-id", request.vendor_session_id),
            ("--polylogue-session-id", request.polylogue_session_id),
            ("--kitty-socket", request.kitty_socket),
            ("--kitty-window-id", request.kitty_window_id),
            ("--hyprland-address", request.hyprland_address),
            ("--quota-snapshot-id", request.quota_snapshot_id),
        ):
            if value:
                command.extend([option, value])

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
                    **(
                        {"SINNIX_WORK_ITEM": request.work_item}
                        if request.work_item
                        else {}
                    ),
                    **(
                        {"SINNIX_PARENT_JOB_ID": request.parent_job_id}
                        if request.parent_job_id
                        else {}
                    ),
                    **(
                        {"SINNIX_COORDINATOR_JOB_ID": request.coordinator_job_id}
                        if request.coordinator_job_id
                        else {}
                    ),
                },
            )
        except OSError as exc:
            raise JobError("failed to launch attested agent job") from exc
        manifest = self._manifest_path(job_id)
        for _ in range(40):
            if manifest.exists() or process.poll() is not None:
                break
            time.sleep(0.05)
        try:
            value = self._load(job_id)
        except JobError as exc:
            self._abort_launch(process)
            prompt_path.unlink(missing_ok=True)
            raise JobError("agent runner did not create its manifest") from exc
        if value.get("launch_id") != launch_id:
            self._abort_launch(process)
            prompt_path.unlink(missing_ok=True)
            raise JobError("job ID collision was rejected")
        return {
            "job_id": job_id,
            "accepted": True,
            "backend": request.backend,
            "project_id": request.project_id,
        }

    def start_shell(
        self,
        argv: list[str],
        cwd: str = "/",
        timeout_seconds: int = 3_600,
        environment: dict[str, str] | None = None,
        as_root: bool = False,
    ) -> dict[str, Any]:
        self.principal.require(Capability.SHELL_RUN)
        workdir, request = self._shell_request(
            argv, cwd, timeout_seconds, self._shell_environment(environment)
        )
        scope_command = shutil.which(self.config.agent_scope_exec_command)
        execution_command = shutil.which(self.config.execution_job_command)
        if scope_command is None or execution_command is None:
            raise JobError("execution job launcher is unavailable")
        if as_root:
            sudo = shutil.which("sudo")
            if sudo is None:
                raise JobError("sudo command is unavailable")
            request["argv"] = [sudo, "-n", "--", *argv]
            request["identity"] = "root"
        else:
            request["identity"] = "user"
        job_id = str(uuid.uuid4())
        launch_id = secrets.token_hex(16)
        scope_unit = f"sinnix-gateway-exec-{job_id}.scope"
        reservation_root = self.root / ".reservations"
        reservation_root.mkdir(mode=0o700, exist_ok=True)
        reservation_root.chmod(0o700)
        reservation = reservation_root / job_id
        try:
            reservation.mkdir(mode=0o700)
        except FileExistsError as exc:
            raise JobError("job ID collision was rejected") from exc
        launch_file = reservation / "launch-id"
        launch_file.write_text(launch_id)
        launch_file.chmod(0o600)
        request["job_id"] = job_id
        request["launch_id"] = launch_id
        request_path = self.root / f"{job_id}.{launch_id}.request"
        request_path.write_text(json.dumps(request, sort_keys=True, separators=(",", ":")))
        request_path.chmod(0o600)
        command = [
            scope_command,
            "--allow-nested-scope",
            "--unit",
            scope_unit,
            "--property",
            f"RuntimeMaxSec={timeout_seconds + 10}",
            "--",
            execution_command,
            "--job-id",
            job_id,
            "--launch-id",
            launch_id,
            "--state-dir",
            str(self.root),
            "--request",
            str(request_path),
            "--scope-unit",
            scope_unit,
        ]
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                env=self._environment(),
            )
        except OSError as exc:
            request_path.unlink(missing_ok=True)
            shutil.rmtree(reservation, ignore_errors=True)
            raise JobError("failed to launch execution job") from exc
        manifest = self._manifest_path(job_id)
        for _ in range(40):
            if manifest.exists() or process.poll() is not None:
                break
            time.sleep(0.05)
        try:
            value = self._load(job_id)
        except JobError as exc:
            self._stop_execution_unit(scope_unit)
            self._abort_launch(process)
            request_path.unlink(missing_ok=True)
            shutil.rmtree(reservation, ignore_errors=True)
            raise JobError("execution launcher did not create its manifest") from exc
        if value.get("launch_id") != launch_id:
            self._stop_execution_unit(scope_unit)
            self._abort_launch(process)
            raise JobError("job ID collision was rejected")
        return {
            "job_id": job_id,
            "accepted": True,
            "kind": "shell",
            "identity": request["identity"],
            "cwd": str(workdir),
            "unit": scope_unit,
        }

    def _stop_execution_unit(self, unit: str) -> None:
        subprocess.run(
            [self.config.systemctl_command, "--user", "stop", unit],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            env=self._environment(),
        )

    def _controller_status(self, job_id: str) -> dict[str, Any]:
        if not self.config.agent_controller.is_file():
            raise JobError("agent controller is unavailable")
        result = subprocess.run(
            [
                str(self.config.agent_controller),
                "--state-dir",
                str(self.root),
                "status",
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
            raise JobError(result.stderr.strip() or "agent status lookup failed")
        try:
            value = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise JobError("agent controller returned malformed status") from exc
        if value.get("schema_version") not in {2, 3} or value.get("job_id") != job_id:
            raise JobError("agent controller returned unattested status")
        return value

    def _shell_live(self, unit: str) -> dict[str, Any]:
        result = subprocess.run(
            [
                self.config.systemctl_command,
                "--user",
                "show",
                unit,
                "--property=ActiveState",
                "--property=SubState",
                "--property=MainPID",
                "--property=ControlGroup",
                "--property=Result",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            text=True,
            env=self._environment(),
        )
        if result.returncode != 0:
            return {"available": False}
        values = {
            key: value
            for line in result.stdout.splitlines()
            if "=" in line
            for key, value in [line.split("=", 1)]
        }
        return {"available": True, **values}

    def _store_shell_manifest(self, job_id: str, manifest: dict[str, Any]) -> None:
        path = self._manifest_path(job_id)
        descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(self.root))
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                json.dump(manifest, output, sort_keys=True, separators=(",", ":"))
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, path)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass

    def _shell_status(self, job_id: str, manifest: dict[str, Any]) -> dict[str, Any]:
        launcher = manifest.get("launcher")
        if not isinstance(launcher, dict) or not isinstance(launcher.get("scope_unit"), str):
            raise JobError("unattested execution job manifest")
        live = self._shell_live(launcher["scope_unit"])
        if (
            live.get("available")
            and live.get("ActiveState") in {"inactive", "failed"}
            and manifest.get("lifecycle") in {"accepted", "starting", "running", "cancel_requested"}
        ):
            if manifest["lifecycle"] == "cancel_requested":
                lifecycle, exit_status = "cancelled", 143
            elif live.get("Result") == "timeout":
                lifecycle, exit_status = "timed_out", 124
            else:
                lifecycle, exit_status = "failed", 1
            manifest["lifecycle"] = lifecycle
            manifest["exit_status"] = exit_status
            manifest["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            self._store_shell_manifest(job_id, manifest)
        return {**manifest, "live": live}

    def status(self, job_id: str) -> dict[str, Any]:
        self.principal.require(Capability.JOB_READ)
        loaded = self._load(job_id)
        manifest = (
            self._shell_status(job_id, loaded)
            if loaded.get("schema_version") == 4
            else self._controller_status(job_id)
        )
        sanitized = json.loads(json.dumps(manifest))
        for section in ("prompt", "artifacts"):
            if isinstance(sanitized.get(section), dict):
                for key in list(sanitized[section]):
                    if key == "sha256":
                        continue
                    sanitized[section][key] = bool(sanitized[section][key])
        command = sanitized.get("command")
        if isinstance(command, dict) and isinstance(command.get("argv"), list):
            argv = command["argv"]
            command["argv"] = {
                "count": len(argv),
                "executable": Path(argv[0]).name if argv else None,
                "sha256": command.get("argv_sha256"),
            }
        sanitized.pop("repo", None)
        sanitized.pop("worktree", None)
        return sanitized

    def list(self, limit: int = 100) -> dict[str, Any]:
        self.principal.require(Capability.JOB_READ)
        jobs: list[dict[str, Any]] = []
        malformed: list[dict[str, str]] = []
        paths = sorted(
            self.root.glob("*.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for path in paths[: max(1, min(limit, 1000))]:
            try:
                value = json.loads(path.read_text())
                job_id = value.get("job_id")
                if value.get("schema_version") not in {2, 3, 4} or not isinstance(job_id, str):
                    raise ValueError("invalid manifest contract")
                jobs.append(self.status(job_id))
            except (ValueError, json.JSONDecodeError, JobError) as exc:
                malformed.append({"record": path.name, "error": str(exc)})
        return {"jobs": jobs, "malformed_records": malformed}

    def _cancel_shell(self, job_id: str, manifest: dict[str, Any]) -> dict[str, Any]:
        launcher = manifest.get("launcher")
        if not isinstance(launcher, dict):
            raise JobError("unattested execution job manifest")
        unit = launcher.get("scope_unit")
        cgroup = launcher.get("cgroup")
        pid = launcher.get("pid")
        start = launcher.get("proc_start")
        launcher_cwd = launcher.get("cwd")
        expected_unit = f"sinnix-gateway-exec-{job_id}.scope"
        if unit != expected_unit or not isinstance(cgroup, str) or not cgroup:
            raise JobError("execution job scope identity is invalid")
        if not isinstance(pid, int) or not isinstance(start, str):
            raise JobError("execution job launcher identity is invalid")
        if launcher_cwd is not None and not isinstance(launcher_cwd, str):
            raise JobError("execution job launcher identity is invalid")
        if manifest.get("lifecycle") == "cancelled":
            return {"job_id": job_id, "cancelled": True, "already_terminal": True}
        if manifest.get("lifecycle") not in {
            "accepted",
            "starting",
            "running",
            "cancel_requested",
        }:
            raise JobError("execution job is not live")
        if self._proc_start(pid) != start or self._cgroup_for_pid(pid) != cgroup:
            raise JobError("execution job process identity no longer matches")
        if launcher_cwd is not None:
            try:
                actual_cwd = str(Path(f"/proc/{pid}/cwd").resolve(strict=True))
            except OSError as exc:
                raise JobError("execution job working directory is unavailable") from exc
            if actual_cwd != str(Path(launcher_cwd).resolve()):
                raise JobError("execution job launcher directory no longer matches")
        live = self._shell_live(unit)
        if not live.get("available") or live.get("ControlGroup") != cgroup:
            raise JobError("execution job systemd identity no longer matches")
        manifest["lifecycle"] = "cancel_requested"
        manifest["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self._store_shell_manifest(job_id, manifest)
        result = subprocess.run(
            [self.config.systemctl_command, "--user", "stop", unit],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            env=self._environment(),
        )
        if result.returncode != 0:
            raise JobError("execution job cancellation was refused")
        manifest["lifecycle"] = "cancelled"
        manifest["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        manifest["exit_status"] = 143
        self._store_shell_manifest(job_id, manifest)
        return {"job_id": job_id, "cancelled": True, "already_terminal": False}

    def cancel(self, job_id: str) -> dict[str, Any]:
        self.principal.require(Capability.JOB_CANCEL)
        manifest = self._load(job_id)
        if manifest.get("schema_version") == 4:
            return self._cancel_shell(job_id, manifest)
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
        self,
        job_id: str,
        artifact: str = "log",
        offset: int = 0,
        max_bytes: int = 64_000,
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
