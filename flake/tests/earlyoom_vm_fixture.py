"""Small guest-only victims and sensor recovery for earlyoom signal tests."""

import ctypes
import os
import select
import signal
import sys
from pathlib import Path

mode, *args = sys.argv[1:]
if mode == "victim":
    name, size, ready = args
    assert ctypes.CDLL(None).prctl(15, name.encode(), 0, 0, 0) == 0
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    memory = bytearray(int(size) * 1024 * 1024)
    Path(ready).write_text(str(os.getpid()))
    while True:
        signal.pause()
elif mode == "recover":
    pid, sensors, ready = args
    # Wake on the actual victim's exit, then model the memory it released.
    # Updating the same inode preserves earlyoom's already-open meminfo FD.
    fd = os.pidfd_open(int(pid))
    poll = select.poll()
    poll.register(fd, select.POLLIN)
    Path(ready).touch()
    assert poll.poll(30000), "victim did not exit within 30 seconds"
    Path(sensors, "meminfo").write_text(
        "MemTotal: 1000000 kB\nMemAvailable: 400000 kB\n"
        "AnonPages: 400000 kB\nSwapTotal: 400000 kB\nSwapFree: 200000 kB\n"
    )
    os.close(fd)
else:
    raise ValueError(mode)
