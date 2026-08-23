from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from .jobs import MAX_LOG_ARTIFACT_BYTES, MAX_RESULT_BYTES, _read_private_artifact
from .projects import ProjectConfigError, parse_worktree_records


class RunnerError(ValueError):
    pass


def _git(path: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), *arguments], check=True, capture_output=True, text=True, timeout=2
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise RunnerError("could not revalidate registered checkout") from error
    return result.stdout


def _require_strings(value: Mapping[str, Any], fields: Sequence[str]) -> None:
    if any(not isinstance(value.get(field), str) or not value[field] for field in fields):
        raise RunnerError("private typed-job input is invalid")


def _load(path: Path, job_id: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise RunnerError("private typed-job input is unavailable") from error
    if not isinstance(value, dict) or value.get("schema_version") != 1 or value.get("job_id") != job_id:
        raise RunnerError("private typed-job identity is invalid")
    if value.get("kind") not in {"operator-shell", "attested-agent"}:
        raise RunnerError("private typed-job kind is invalid")
    checkout = value.get("checkout")
    if not isinstance(checkout, dict) or set(checkout) != {
        "project_id",
        "project_path",
        "checkout_id",
        "path",
        "git_common_dir",
        "head",
    }:
        raise RunnerError("private typed-job checkout is invalid")
    _require_strings(checkout, tuple(checkout))
    return value


def _revalidate_checkout(checkout: Mapping[str, Any]) -> Path:
    recorded_path = Path(checkout["path"])
    if not recorded_path.is_absolute():
        raise RunnerError("registered checkout path is not absolute")
    try:
        path = recorded_path.resolve(strict=True)
    except OSError as error:
        raise RunnerError("registered checkout is unavailable") from error
    if str(path) != checkout["path"]:
        raise RunnerError("registered checkout path is not canonical")
    project_path = Path(checkout["project_path"])
    try:
        project_path = project_path.resolve(strict=True)
    except OSError as error:
        raise RunnerError("registered project is unavailable") from error
    if not project_path.is_absolute() or str(project_path) != checkout["project_path"]:
        raise RunnerError("registered project path is not canonical")
    if not (project_path / ".agentctl" / "project.toml").is_file():
        raise RunnerError("registered project is unavailable")
    top_level = Path(_git(path, "rev-parse", "--show-toplevel").strip()).resolve(strict=True)
    common_dir = Path(_git(path, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()).resolve(strict=True)
    project_top_level = Path(_git(project_path, "rev-parse", "--show-toplevel").strip()).resolve(strict=True)
    project_common_dir = Path(
        _git(project_path, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()
    ).resolve(strict=True)
    if (
        top_level != path
        or project_top_level != project_path
        or str(common_dir) != checkout["git_common_dir"]
        or common_dir != project_common_dir
    ):
        raise RunnerError("registered checkout identity changed")
    try:
        records = parse_worktree_records(_git(path, "worktree", "list", "--porcelain"))
    except ProjectConfigError as error:
        raise RunnerError(str(error)) from error
    if not any(
        record.get("worktree") == str(path) and record.get("HEAD") == checkout["head"] for record in records
    ):
        raise RunnerError("checkout is no longer a registered Git worktree")
    return path


def _require_environment(job_id: str, unit: str, value: Mapping[str, Any]) -> None:
    expected = {
        "SINNIXD_JOB_ID": job_id,
        "SINNIXD_PROJECT_ID": value["checkout"]["project_id"],
        "SINNIXD_CHECKOUT_ID": value["checkout"]["checkout_id"],
        "SINNIXD_PRINCIPAL": value["principal"],
        "SINNIXD_TIMEOUT_SECONDS": os.environ.get("SINNIXD_TIMEOUT_SECONDS", ""),
    }
    timeout_seconds = expected["SINNIXD_TIMEOUT_SECONDS"]
    if not timeout_seconds.isdecimal() or not 1 <= int(timeout_seconds) <= 3_600:
        raise RunnerError("typed-job timeout identity is invalid")
    if any(os.environ.get(key) != expected_value for key, expected_value in expected.items()):
        raise RunnerError("typed-job environment identity is invalid")
    if any(key.startswith("SINNIX") and key not in expected for key in os.environ):
        raise RunnerError("typed-job environment contains an untrusted SINNIX identity")
    if unit != f"sinnixd-job-{job_id}.service":
        raise RunnerError("typed-job unit identity is invalid")


def _exec_shell(value: Mapping[str, Any], checkout: Path) -> None:
    argv = value.get("argv")
    cwd = value.get("cwd")
    if value.get("principal") != "operator" or not isinstance(argv, list) or not argv or any(
        not isinstance(item, str) or not item for item in argv
    ):
        raise RunnerError("operator shell contract is invalid")
    if not isinstance(cwd, str):
        raise RunnerError("operator shell cwd is invalid")
    workdir = Path(cwd).resolve(strict=True)
    if not workdir.is_dir() or (workdir != checkout and checkout not in workdir.parents):
        raise RunnerError("operator shell cwd escaped the registered checkout")
    os.chdir(workdir)
    os.execvpe(argv[0], argv, dict(os.environ))


def _current_cgroup() -> str:
    try:
        for line in Path("/proc/self/cgroup").read_text().splitlines():
            hierarchy, _, cgroup = line.partition("::")
            if hierarchy == "0":
                return cgroup
    except OSError:
        pass
    return ""


def _emit_native_log(log_path: Path) -> None:
    """Relay a private native log through the shared bounded capture helper."""
    try:
        os.chmod(log_path, 0o600, follow_symlinks=False)
    except OSError:
        return
    content = _read_private_artifact(log_path, MAX_LOG_ARTIFACT_BYTES)
    if content:
        sys.stdout.buffer.write(content)
        sys.stdout.buffer.flush()


def _run_agent(
    value: Mapping[str, Any],
    checkout: Path,
    *,
    native_runner: Path,
    native_state_dir: Path,
    state_root: Path,
    unit: str,
) -> int:
    _require_strings(value, ("backend", "model", "effort", "credential_profile", "prompt_path", "result_path"))
    if value.get("principal") != "agent-control" or value["backend"] not in {"claude", "codex", "gemini", "grok", "antigravity"}:
        raise RunnerError("attested agent contract is invalid")
    if value["credential_profile"] not in {"subscription", "api"}:
        raise RunnerError("attested agent credential profile is invalid")
    prompt_path = Path(value["prompt_path"]).resolve(strict=True)
    result_path = Path(value["result_path"]).resolve()
    if not prompt_path.is_file() or (state_root / "inputs").resolve() not in prompt_path.parents:
        raise RunnerError("attested agent prompt input is invalid")
    if (state_root / "results").resolve() not in result_path.parents:
        raise RunnerError("attested agent result artifact is invalid")
    if not native_runner.is_file() or not os.access(native_runner, os.X_OK):
        raise RunnerError("native agent runner is unavailable")
    native_state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    log_path = native_state_dir / f"{value['job_id']}.agent.log"
    command = [
        str(native_runner),
        "--agent",
        value["backend"],
        "--registered-project",
        value["checkout"]["project_path"],
        "--expected-git-common-dir",
        value["checkout"]["git_common_dir"],
        "--workdir",
        str(checkout),
        "--prompt-file",
        str(prompt_path),
        "--log-file",
        str(log_path),
        "--last-file",
        str(result_path),
        "--job-id",
        value["job_id"],
        "--launch-id",
        value["job_id"].replace("-", ""),
        "--job-state-dir",
        str(native_state_dir),
        "--timeout-seconds",
        os.environ.get("SINNIXD_TIMEOUT_SECONDS", "3600"),
        "--credential-profile",
        value["credential_profile"],
        "--model",
        value["model"],
        "--reasoning-effort",
        value["effort"],
        "--checkout-ref",
        f"sinnix://projects/{value['checkout']['project_id']}/checkouts/{value['checkout']['checkout_id']}",
    ]
    environment = dict(os.environ)
    environment.update({"SINNIX_AGENT_SCOPED": "1", "SINNIX_AGENT_SCOPE_UNIT": unit, "SINNIX_AGENT_SCOPE_CGROUP": _current_cgroup(), "SINNIX_AGENT_JOB_STATE_DIR": str(native_state_dir), "SINNIX_CORRELATION_ID": value["job_id"]})
    try:
        completed = subprocess.run(command, cwd=checkout, env=environment, check=False)
        _emit_native_log(log_path)
        if result_path.exists() and result_path.stat().st_size > MAX_RESULT_BYTES:
            result_path.write_bytes(result_path.read_bytes()[:MAX_RESULT_BYTES])
        return completed.returncode
    finally:
        prompt_path.unlink(missing_ok=True)
        log_path.unlink(missing_ok=True)


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sinnixd-contract-runner")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--unit", required=True)
    parser.add_argument("--native-runner", type=Path, required=True)
    parser.add_argument("--native-state-dir", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    args = parser.parse_args(arguments)
    try:
        value = _load(args.input, args.job_id)
        _require_environment(args.job_id, args.unit, value)
        checkout = _revalidate_checkout(value["checkout"])
        if value["kind"] == "operator-shell":
            args.input.unlink(missing_ok=True)
            _exec_shell(value, checkout)
        args.input.unlink(missing_ok=True)
        return _run_agent(
            value,
            checkout,
            native_runner=args.native_runner.resolve(),
            native_state_dir=args.native_state_dir.resolve(),
            state_root=args.state_root.resolve(),
            unit=args.unit,
        )
    except RunnerError as error:
        parser.error(str(error))
    raise AssertionError("contract runner must exec its payload")


if __name__ == "__main__":
    raise SystemExit(main())
