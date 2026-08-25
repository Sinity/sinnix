from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence

from .jobs import GenericJobStore, JobRecordError, MAX_RESULT_BYTES
from .limits import maximum_timeout_seconds, valid_timeout_seconds
from .projects import ProjectConfigError, revalidate_registered_checkout

AGENT_PREFLIGHT_TIMEOUT_SECONDS = 30


class RunnerError(ValueError):
    pass


def _require_strings(value: Mapping[str, Any], fields: Sequence[str]) -> None:
    if any(not isinstance(value.get(field), str) or not value[field] for field in fields):
        raise RunnerError("private typed-job input is invalid")


def _non_empty_argv(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(
        isinstance(item, str) and item for item in value
    )


def _load(path: Path, job_id: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise RunnerError("private typed-job input is unavailable") from error
    if not isinstance(value, dict) or value.get("job_id") != job_id:
        raise RunnerError("private typed-job identity is invalid")
    kind = value.get("kind")
    if kind not in {"operator-shell", "attested-agent"}:
        raise RunnerError("private typed-job kind is invalid")
    if kind == "attested-agent" and value.get("schema_version") != 2:
        raise RunnerError(
            "stale attested-agent private input schema; retry the agent launch after the environment contract upgrade"
        )
    if kind == "operator-shell" and value.get("schema_version") != 1:
        raise RunnerError("private typed-job schema is invalid")
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
    try:
        return revalidate_registered_checkout(checkout)
    except ProjectConfigError as error:
        raise RunnerError(str(error)) from error


def _require_environment(job_id: str, unit: str, value: Mapping[str, Any]) -> None:
    expected = {
        "SINNIXD_JOB_ID": job_id,
        "SINNIXD_PROJECT_ID": value["checkout"]["project_id"],
        "SINNIXD_CHECKOUT_ID": value["checkout"]["checkout_id"],
        "SINNIXD_PRINCIPAL": value["principal"],
        "SINNIXD_TIMEOUT_SECONDS": os.environ.get("SINNIXD_TIMEOUT_SECONDS", ""),
    }
    timeout_seconds = expected["SINNIXD_TIMEOUT_SECONDS"]
    if not timeout_seconds.isdecimal() or not valid_timeout_seconds(int(timeout_seconds), kind=value["kind"]):
        raise RunnerError("typed-job timeout identity is invalid")
    if any(os.environ.get(key) != expected_value for key, expected_value in expected.items()):
        raise RunnerError("typed-job environment identity is invalid")
    if any(key.startswith("SINNIX") and key not in expected for key in os.environ):
        raise RunnerError("typed-job environment contains an untrusted SINNIX identity")
    if unit != f"sinnixd-job-{job_id}.service":
        raise RunnerError("typed-job unit identity is invalid")


def _run_declared(state_root: Path, job_id: str, unit: str) -> None:
    """Revalidate a bound checkout at the unit's check-to-exec boundary."""
    try:
        store = GenericJobStore(state_root.resolve(strict=True))
        record = store.load(job_id)
        command, environment = store.declared_launch(job_id)
    except (OSError, JobRecordError) as error:
        raise RunnerError("declared-job launch input is invalid") from error
    checkout = record.spec.checkout
    if (
        record.unit != unit
        or record.spec.kind != "declared-operation"
        or not isinstance(checkout, Mapping)
        or record.spec.working_directory != checkout.get("path")
    ):
        raise RunnerError("declared-job identity is invalid")
    expected = {
        "SINNIXD_JOB_ID": job_id,
        "SINNIXD_PROJECT_ID": record.spec.project_id,
        "SINNIXD_OPERATION": record.spec.operation,
        "SINNIXD_CHECKOUT_ID": checkout.get("checkout_id"),
        "SINNIXD_CHECKOUT_HEAD": checkout.get("head"),
    }
    if any(not isinstance(value, str) or os.environ.get(key) != value for key, value in expected.items()):
        raise RunnerError("declared-job environment identity is invalid")
    checkout_path = _revalidate_checkout(checkout)
    os.chdir(checkout_path)
    os.execvpe(command[0], command, {**os.environ, **environment})


def _exec_shell(value: Mapping[str, Any], checkout: Path) -> None:
    argv = value.get("argv")
    environment_command = value.get("environment_command")
    cwd = value.get("cwd")
    if value.get("principal") != "operator" or not _non_empty_argv(argv):
        raise RunnerError("operator shell contract is invalid")
    if not _non_empty_argv(environment_command):
        raise RunnerError("operator shell project environment is invalid")
    if not isinstance(cwd, str):
        raise RunnerError("operator shell cwd is invalid")
    workdir = Path(cwd).resolve(strict=True)
    if not workdir.is_dir() or (workdir != checkout and checkout not in workdir.parents):
        raise RunnerError("operator shell cwd escaped the registered checkout")
    command = [*environment_command, *argv]
    os.chdir(workdir)
    os.execvpe(command[0], command, dict(os.environ))


def _run_agent(
    value: Mapping[str, Any],
    checkout: Path,
    *,
    native_runner: Path,
    state_root: Path,
) -> int:
    _require_strings(value, ("backend", "model", "effort", "credential_profile", "prompt_path", "result_path"))
    if value.get("principal") not in {"agent-control", "operator"} or value["backend"] not in {"claude", "codex", "gemini", "grok", "antigravity"}:
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
    environment_command = value.get("environment_command")
    environment_preflight = value.get("environment_preflight")
    if not _non_empty_argv(environment_command):
        raise RunnerError(
            "typed agent project environment is missing; declare a non-empty environment.command"
        )
    if not _non_empty_argv(environment_preflight):
        raise RunnerError(
            "typed agent project environment is missing; declare a non-empty environment.preflight"
        )
    preflight_command = [*environment_command, *environment_preflight]
    try:
        preflight = subprocess.run(
            preflight_command,
            cwd=checkout,
            check=False,
            timeout=AGENT_PREFLIGHT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        raise RunnerError(
            "agent-preflight-timeout: project environment preflight exceeded "
            f"{AGENT_PREFLIGHT_TIMEOUT_SECONDS} seconds before agent implementation; "
            "inspect the declared preflight and retry"
        ) from error
    except OSError as error:
        raise RunnerError(
            "project environment preflight is unavailable; repair environment.command and retry"
        ) from error
    if preflight.returncode != 0:
        raise RunnerError(
            "project environment preflight failed before agent implementation "
            f"(exit status {preflight.returncode}); repair the declared environment and retry"
        )
    command = [
        *environment_command,
        str(native_runner),
        "--agent",
        value["backend"],
        "--workdir",
        str(checkout),
        "--prompt-file",
        str(prompt_path),
        "--last-file",
        str(result_path),
        "--credential-profile",
        value["credential_profile"],
        "--model",
        value["model"],
        "--reasoning-effort",
        value["effort"],
    ]
    try:
        completed = subprocess.run(command, cwd=checkout, check=False)
        if result_path.exists() and result_path.stat().st_size > MAX_RESULT_BYTES:
            result_path.write_bytes(result_path.read_bytes()[:MAX_RESULT_BYTES])
        return completed.returncode
    finally:
        prompt_path.unlink(missing_ok=True)


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sinnixd-contract-runner")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--declared", action="store_true")
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--unit", required=True)
    parser.add_argument("--native-runner", type=Path)
    parser.add_argument("--state-root", type=Path, required=True)
    args = parser.parse_args(arguments)
    try:
        if args.declared:
            if args.input is not None or args.native_runner is not None:
                raise RunnerError("declared-job runner arguments are invalid")
            _run_declared(args.state_root, args.job_id, args.unit)
        if args.input is None or args.native_runner is None:
            raise RunnerError("typed-job runner arguments are invalid")
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
            state_root=args.state_root.resolve(),
        )
    except RunnerError as error:
        parser.error(str(error))
    raise AssertionError("contract runner must exec its payload")


if __name__ == "__main__":
    raise SystemExit(main())
