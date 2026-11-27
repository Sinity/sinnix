"""Exercise a real PTY/recorder while the destination cannot even open."""

import json
import os
import shlex
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

helper = sys.argv[1]
root = Path(os.environ["TMPDIR"])
fifo = root / "blocked.cast"
os.mkfifo(fifo)
shell = root / "shell.py"
shell.write_text(
    "import sys\n"
    "sys.stdout.write('capture-payload-' * 131072)\n"
    "sys.stdout.write('\\nSHELL-FINISHED\\n')\n"
    "sys.stdout.flush()\n"
)
command = [
    sys.executable,
    helper,
    "record",
    str(fifo),
    "asciinema",
    "rec",
    "--quiet",
    "--return",
    "--output-format",
    "asciicast-v3",
    "--command",
    shlex.join([sys.executable, str(shell)]),
]
transcript = root / "terminal.log"
with transcript.open("wb") as output:
    process = subprocess.Popen(
        ["script", "-qfec", shlex.join(command), "/dev/null"],
        stdout=output,
        stderr=subprocess.STDOUT,
    )
    try:
        deadline = time.monotonic() + 10
        while b"SHELL-FINISHED" not in transcript.read_bytes():
            assert process.poll() is None, transcript.read_text(errors="replace")[
                -2000:
            ]
            assert time.monotonic() < deadline, "shell stalled behind destination"
            time.sleep(0.05)
        # Destination stays unread for another few seconds after shell output.
        time.sleep(2)
        assert process.poll() is None, "transport should wait for lossless drain"
        captured = bytearray()

        def drain():
            with fifo.open("rb") as source:
                captured.extend(source.read())

        reader = threading.Thread(target=drain, daemon=True)
        reader.start()
        assert process.wait(timeout=15) == 0
        reader.join(timeout=5)
        assert not reader.is_alive()
        rows = [json.loads(line) for line in captured.splitlines()]
        assert rows[0]["version"] == 3
        text = "".join(row[2] for row in rows[1:] if row[1] == "o")
        assert text.count("capture-payload-") == 131072
        assert "SHELL-FINISHED" in text
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()

# A failed disk write must fail the supervised recorder rather than silently
# reporting the shell's successful exit.
command[3] = "/dev/full"
result = subprocess.run(
    ["script", "-qfec", shlex.join(command), "/dev/null"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    timeout=15,
)
assert result.returncode != 0

# SIGTERM must also release a recorder whose cast writer cannot drain. Use a
# real PTY and leave the FIFO unread throughout the stop.
command[3] = str(fifo)
command[-1] = "printf 'STOP-READY\\n'; exec sleep 60"
with transcript.open("wb") as output:
    process = subprocess.Popen(
        ["script", "-qfec", "exec " + shlex.join(command), "/dev/null"],
        stdout=output,
        stderr=subprocess.STDOUT,
    )
    supervisor = None
    try:
        deadline = time.monotonic() + 10
        while b"STOP-READY" not in transcript.read_bytes():
            assert process.poll() is None
            assert time.monotonic() < deadline, "recorder did not start"
            time.sleep(0.05)
        children = Path(f"/proc/{process.pid}/task/{process.pid}/children")
        (supervisor,) = map(int, children.read_text().split())
        os.kill(supervisor, signal.SIGTERM)
        assert process.wait(timeout=8) != 0
        assert not Path(f"/proc/{supervisor}").exists()
        assert b"stopping with an unfinished recording" in transcript.read_bytes()
    finally:
        if process.poll() is None:
            if supervisor is not None:
                os.kill(supervisor, signal.SIGKILL)
            process.kill()
            process.wait()

# Exercise exhaustion with a small bound instead of consuming 256 MiB in CI.
# The producer must block, emit a warning, then resume without losing bytes.
small_fifo = root / "small-buffer.cast"
os.mkfifo(small_fifo)
code = (
    "import runpy,sys; scope=runpy.run_path(sys.argv[1]); "
    "scope['write_capture'].__globals__['BUFFER']=65536; "
    "sys.exit(scope['write_capture'](sys.argv[2]))"
)
with (root / "exhaustion.log").open("wb") as errors:
    writer = subprocess.Popen(
        [sys.executable, "-c", code, helper, str(small_fifo)],
        stdin=subprocess.PIPE,
        stderr=errors,
    )
    payload = b"bounded-capture\n" * 131072
    sent = threading.Event()

    def produce():
        writer.stdin.write(payload)
        writer.stdin.close()
        sent.set()

    producer = threading.Thread(target=produce, daemon=True)
    producer.start()
    deadline = time.monotonic() + 5
    while b"buffer exhausted" not in (root / "exhaustion.log").read_bytes():
        assert time.monotonic() < deadline, "missing exhaustion warning"
        time.sleep(0.05)
    assert not sent.is_set(), "exhaustion must block the producer"
    with small_fifo.open("rb") as source:
        restored = source.read()
    producer.join(timeout=5)
    assert sent.is_set()
    assert writer.wait(timeout=5) == 0
    assert restored == payload
