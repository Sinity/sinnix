"""Real child processes discriminate startup, exit and cancellation ownership."""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
from agentctl import service_run
from agentctl.projects import ProjectConfigError, load_project_adapter
from conftest import write_project


def service(tmp_path, body=None):
    pidfile = tmp_path / "service.pid"
    code = (
        "import os,time;from pathlib import Path;"
        f"Path({str(pidfile)!r}).write_text(str(os.getpid()));"
        "Path(os.environ['AGENTCTL_SERVICE_READY']).write_text('ready');"
        "time.sleep(30)"
    )
    return {
        "name": "fixture",
        "command": [sys.executable, "-c", body or code],
        "ready_probe": [
            sys.executable,
            "-c",
            "import os;from pathlib import Path;raise SystemExit(0 if Path(os.environ['AGENTCTL_SERVICE_READY']).is_file() else 1)",
        ],
        "ready_timeout_seconds": 1,
    }


def settled(tmp_path):
    pid = int((tmp_path / "service.pid").read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def test_verifier_exit_preserved_and_service_settled(tmp_path):
    assert (
        service_run.execute(
            [service(tmp_path)], [sys.executable, "-c", "raise SystemExit(23)"]
        )
        == 23
    )
    settled(tmp_path)


def test_failed_startup_never_runs_verifier(tmp_path):
    marker = tmp_path / "verified"
    command = [
        sys.executable,
        "-c",
        f"from pathlib import Path;Path({str(marker)!r}).touch()",
    ]
    assert (
        service_run.execute([service(tmp_path, "raise SystemExit(7)")], command) == 78
    )
    assert not marker.exists()


def test_readiness_deadline_settles_service(tmp_path):
    config = service(tmp_path)
    config["ready_probe"] = [sys.executable, "-c", "raise SystemExit(1)"]
    assert (
        service_run.execute([config], [sys.executable, "-c", "raise SystemExit(0)"])
        == 78
    )
    settled(tmp_path)


def test_service_failure_during_verification_is_failure(tmp_path):
    config = service(tmp_path)
    config["command"][-1] = config["command"][-1].replace(
        "time.sleep(30)", "time.sleep(0.4);raise SystemExit(7)"
    )
    assert (
        service_run.execute(
            [config], [sys.executable, "-c", "import time;time.sleep(30)"]
        )
        == 78
    )
    settled(tmp_path)


def test_cancellation_settles_required_service(tmp_path):
    config = service(tmp_path)
    process = subprocess.Popen(
        [
            sys.executable,
            str(Path(service_run.__file__)),
            json.dumps([config]),
            "--",
            sys.executable,
            "-c",
            "import time;time.sleep(30)",
        ]
    )
    try:
        deadline = time.monotonic() + 5
        while not (tmp_path / "service.pid").exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert (tmp_path / "service.pid").exists()
        process.terminate()
        assert process.wait(timeout=10) == 128 + signal.SIGTERM
        settled(tmp_path)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()


def test_descriptor_requires_declared_probe_and_no_nested_services(tmp_path):
    root = write_project(tmp_path / "project")
    descriptor = root / ".agentctl/project.toml"
    text = descriptor.read_text().replace(
        'exec = ["true"]', 'exec = ["true"]\nrequires=["database"]'
    )
    descriptor.write_text(text)
    with pytest.raises(ProjectConfigError, match="ready_probe"):
        load_project_adapter(root)
    descriptor.write_text(
        text
        + '\n[operations.database]\ndescription="fixture database"\nexec=["sleep","30"]\nready_probe=["true"]\n'
    )
    assert load_project_adapter(root).operation("check").requires == ("database",)
    descriptor.write_text(
        descriptor.read_text().replace(
            'ready_probe=["true"]', 'ready_probe=["true"]\nrequires=["check"]'
        )
    )
    with pytest.raises(ProjectConfigError, match="self-contained"):
        load_project_adapter(root)
