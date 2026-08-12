"""Low-latency dual-use tee: mic PCM mirrored to a SEQPACKET socket.

`$XDG_RUNTIME_DIR/sinnix/audio/mic.pcm` carries raw 16kHz mono s16le frames
straight from the mic capture -- no resampling needed, because the mic
channel is *already* captured at 16kHz mono for the Opus archive tier (see
segment.CHANNEL_PROFILES["mic"]). One capture, two consumers.

This is a best-effort mirror, not a queue: archive liveness must never
depend on a consumer being attached. The socket is `SOCK_SEQPACKET` +
`SOCK_NONBLOCK`, and every send is wrapped so a full kernel buffer (slow or
absent reader) drops that frame rather than blocking the recorder loop --
a dropped mirror frame is invisible to the archive, which keeps flowing
through OpusSegmentWriter regardless.
"""

from __future__ import annotations

import errno
import logging
import socket
from pathlib import Path

logger = logging.getLogger("sinnix_audio_capture.tee")


class SeqpacketTee:
    def __init__(self, socket_path: Path | str) -> None:
        self.socket_path = Path(socket_path)
        self._sock = socket.socket(
            socket.AF_UNIX, socket.SOCK_SEQPACKET | socket.SOCK_NONBLOCK
        )
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        if self.socket_path.exists():
            self.socket_path.unlink()
        self._sock.bind(str(self.socket_path))
        # Consumers connect (SOCK_SEQPACKET is connection-oriented); until
        # one does, sends below simply have no destination and fail with
        # ENOTCONN/EAGAIN, which send_nonblocking treats as a drop.
        self._sock.listen(1)
        self._conn: socket.socket | None = None

    def _accept_if_pending(self) -> None:
        if self._conn is not None:
            return
        try:
            conn, _ = self._sock.accept()
        except BlockingIOError:
            return
        conn.setblocking(False)
        self._conn = conn

    def send_nonblocking(self, data: bytes) -> bool:
        """Best-effort mirror of one frame. Returns True if delivered, False
        if dropped (no listener, full buffer, or a dead connection -- any of
        these clear the stale connection so a future consumer can attach)."""
        self._accept_if_pending()
        if self._conn is None:
            return False
        try:
            self._conn.send(data)
            return True
        except BlockingIOError:
            return False
        except OSError as exc:
            if exc.errno in (errno.EPIPE, errno.ECONNRESET, errno.ENOTCONN):
                try:
                    self._conn.close()
                finally:
                    self._conn = None
                return False
            logger.warning("sinnix-audio-capture: tee send failed: %s", exc)
            return False

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except OSError:
                pass
            self._conn = None
        try:
            self._sock.close()
        finally:
            try:
                self.socket_path.unlink()
            except FileNotFoundError:
                pass
