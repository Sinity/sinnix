from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence

from .jobs import (
    MAX_RESULT_BYTES,
    GenericJobStore,
    JobRecordError,
    _open_preallocated_private_artifact,
)
from .limits import valid_timeout_seconds
from .projects import ProjectConfigError, revalidate_registered_checkout


class RunnerError(ValueError):
    pass


def _require_strings(value: Mapping[str, Any], fields: Sequence[str]) -> None:
    if any(
        not isinstance(value.get(field), str) or not value[field] for field in fields
    ):
        raise RunnerError("private typed-job input is invalid")


def _load(path: Path, job_id: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RunnerError("private typed-job input is unavailable") from error
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != 1
        or value.get("job_id") != job_id
    ):
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
    if not timeout_seconds.isdecimal() or not valid_timeout_seconds(
        int(timeout_seconds), kind=value["kind"]
    ):
        raise RunnerError("typed-job timeout identity is invalid")
    if any(
        os.environ.get(key) != expected_value
        for key, expected_value in expected.items()
    ):
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
    if any(
        not isinstance(value, str) or os.environ.get(key) != value
        for key, value in expected.items()
    ):
        raise RunnerError("declared-job environment identity is invalid")
    checkout_path = _revalidate_checkout(checkout)
    os.chdir(checkout_path)
    os.execvpe(command[0], command, {**os.environ, **environment})


def _exec_shell(value: Mapping[str, Any], checkout: Path) -> None:
    argv = value.get("argv")
    environment_command = value.get("environment_command")
    cwd = value.get("cwd")
    if (
        value.get("principal") != "operator"
        or not isinstance(argv, list)
        or not argv
        or any(not isinstance(item, str) or not item for item in argv)
    ):
        raise RunnerError("operator shell contract is invalid")
    if (
        not isinstance(environment_command, list)
        or not environment_command
        or any(not isinstance(item, str) or not item for item in environment_command)
    ):
        raise RunnerError("operator shell project environment is invalid")
    if not isinstance(cwd, str):
        raise RunnerError("operator shell cwd is invalid")
    workdir = Path(cwd).resolve(strict=True)
    if not workdir.is_dir() or (
        workdir != checkout and checkout not in workdir.parents
    ):
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
    _require_strings(
        value,
        (
            "backend",
            "model",
            "effort",
            "credential_profile",
            "prompt_path",
            "result_path",
        ),
    )
    if value.get("principal") not in {"agent-control", "operator"} or value[
        "backend"
    ] not in {"claude", "codex", "gemini", "grok", "antigravity"}:
        raise RunnerError("attested agent contract is invalid")
    if value["credential_profile"] not in {"subscription", "api"}:
        raise RunnerError("attested agent credential profile is invalid")
    prompt_path = Path(value["prompt_path"]).resolve(strict=True)
    result_path = Path(value["result_path"]).resolve()
    if (
        not prompt_path.is_file()
        or (state_root / "inputs").resolve() not in prompt_path.parents
    ):
        raise RunnerError("attested agent prompt input is invalid")
    if (state_root / "results").resolve() not in result_path.parents:
        raise RunnerError("attested agent result artifact is invalid")
    if not native_runner.is_file() or not os.access(native_runner, os.X_OK):
        raise RunnerError("native agent runner is unavailable")
    environment_command = value.get("environment_command")
    environment_preflight = value.get("environment_preflight")
    if not isinstance(environment_command, list) or not environment_command or any(
        not isinstance(item, str) or not item for item in environment_command
    ):
        raise RunnerError(
            "typed agent project environment is missing; declare a non-empty environment.command"
        )
    if not isinstance(environment_preflight, list) or not environment_preflight or any(
        not isinstance(item, str) or not item for item in environment_preflight
    ):
        raise RunnerError(
            "typed agent project environment is missing; declare a non-empty environment.preflight"
        )
    preflight_command = [*environment_command, *environment_preflight]
    try:
        preflight = subprocess.run(preflight_command, cwd=checkout, check=False)
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
        binding = value.get("bead_binding")
        if isinstance(binding, Mapping) and "write_scope" in binding:
            _seal_packet_result(value, checkout, result_path)
        if result_path.exists() and result_path.stat().st_size > MAX_RESULT_BYTES:
            result_path.write_bytes(result_path.read_bytes()[:MAX_RESULT_BYTES])
        return completed.returncode
    finally:
        prompt_path.unlink(missing_ok=True)


def _seal_packet_result(
    value: Mapping[str, Any], checkout: Path, result_path: Path
) -> None:
    """Bind a structured worker report to the runtime-observed terminal Git head."""
    try:
        if result_path.stat().st_size > MAX_RESULT_BYTES:
            raise RunnerError("packet result exceeds the artifact limit")
        raw = result_path.read_bytes()
        delivery = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RunnerError("packet worker result is unavailable or malformed") from error
    observed = subprocess.run(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    final_head = observed.stdout.strip()
    if (
        observed.returncode != 0
        or len(final_head) != 40
        or any(value not in "0123456789abcdef" for value in final_head)
    ):
        raise RunnerError("packet final Git head is unavailable")
    envelope = json.dumps(
        {
            "schema_version": 1,
            "job_id": value["job_id"],
            "start_head": value["checkout"]["head"],
            "final_head": final_head,
            "delivery": delivery,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    if len(envelope) > MAX_RESULT_BYTES:
        raise RunnerError("packet result exceeds the artifact limit")
    with _open_preallocated_private_artifact(result_path) as result_file:
        os.ftruncate(result_file.fileno(), 0)
        result_file.write(envelope)
        result_file.flush()
        os.fsync(result_file.fileno())


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
