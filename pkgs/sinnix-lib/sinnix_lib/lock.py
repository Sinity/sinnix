"""flock as a context manager.

Ten scripts opened their own lock fd and reasoned about ``flock -n``
semantics separately; this is that pattern once. The lock is per-open-file-
description (the same property the borg drill had to document by hand), so
nesting the same path in one process deadlocks by design — do not.
"""

from __future__ import annotations

import fcntl
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class LockBusy(RuntimeError):
    """Non-blocking acquisition found the lock held elsewhere."""


@contextmanager
def flock(
    path: Path | str,
    *,
    blocking: bool = True,
    timeout: float | None = None,
) -> Iterator[None]:
    """Hold an exclusive flock on *path* for the duration of the block.

    ``blocking=False`` raises :class:`LockBusy` immediately when held;
    ``timeout`` (seconds) polls until acquired or raises :class:`LockBusy`.
    The lock file is created if absent and never deleted (deleting a lock
    file that another process may have opened reintroduces the race the
    lock exists to prevent).
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as fh:
        if blocking and timeout is None:
            fcntl.flock(fh, fcntl.LOCK_EX)
        else:
            deadline = None if timeout is None else time.monotonic() + timeout
            while True:
                try:
                    fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if deadline is None or time.monotonic() >= deadline:
                        raise LockBusy(str(p)) from None
                    time.sleep(0.1)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)
