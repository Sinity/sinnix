from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path

SCRIPT = next(
    parent / "scripts" / "sinnix-sinex-dev-db"
    for parent in Path(__file__).resolve().parents
    if (parent / "scripts" / "sinnix-sinex-dev-db").is_file()
)


def test_postgres_probe_uses_declared_per_checkout_port(tmp_path: Path) -> None:
    state = tmp_path / "cache" / "operator" / "checkout" / "dev-state"
    pgdata = state / "data" / "postgres"
    pgdata.mkdir(parents=True)
    process = subprocess.Popen(
        [sys.executable, "-c", "import signal; signal.pause()", str(pgdata)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    pgrep = fake_bin / "pgrep"
    pgrep.write_text("#!/bin/sh\nexit 1\n")
    pgrep.chmod(0o755)
    psql_calls = tmp_path / "psql.calls"
    psql = fake_bin / "psql"
    psql.write_text(
        "#!/bin/sh\nprintf '%s\\n' \"$*\" >>\"$PSQL_CALLS\"\nprintf '1\\n'\n"
    )
    psql.chmod(0o755)
    (pgdata / "postmaster.pid").write_text(f"{process.pid}\n")
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "SINEX_DEV_CACHE_BASE": str(tmp_path / "cache"),
        "SINEX_DEV_POSTGRES_PORT": "45671",
        "PGPORT": "5432",
        "PSQL_CALLS": str(psql_calls),
    }
    try:
        result = subprocess.run(
            [str(SCRIPT), "reap", "--now"],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        calls = psql_calls.read_text()
        assert "-p 45671" in calls
        assert "-p 5432" not in calls
        assert process.poll() is None  # fake psql reports an active client
    finally:
        if process.poll() is None:
            process.send_signal(signal.SIGKILL)
        process.wait(timeout=3)
