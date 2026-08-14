"""Persistent TCP receiver for the phone's always-on telemetry push.

Protocol: newline-delimited JSON. Each line is a JSON object with at least
``kind`` (a short string naming the stream, e.g. "battery", "sensor",
"speech") and
``ts`` (ISO-8601 UTC). Every field is passed through into the capture
envelope's payload verbatim; this receiver's only job is demuxing by
``kind`` into a per-kind capture lane (``phone-<kind>``) so downstream
consumers can query one stream without filtering out the others, matching
this repo's existing per-lane JSONL convention (sinnix-capture-v1).

Deliberately dumb: no backpressure, no batching, no reconnect logic (that
lives entirely on the phone-side client, which owns retry policy for a
link that sleeps/roams). One line in -> one envelope written, as fast as
the phone sends them. A malformed line is logged and dropped, not fatal --
a single corrupt line must never take down a connection carrying everything
else the phone is sending.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from sinnix_capture.writer import CaptureWriter

from .speech import MAX_UTTERANCE_SECONDS, SpeechLane

#: asyncio's StreamReader defaults to a 64 KiB line limit, which is ample for a
#: battery reading and far too small for an utterance: a speech line carries
#: base64 PCM, so its size follows directly from the duration ceiling the
#: speech lane enforces. Deriving one from the other means raising the ceiling
#: cannot silently start killing connections -- which is exactly what happened
#: the first time a real utterance was pushed at this receiver.
_PCM_BYTES_PER_SECOND = 16000 * 2  # 16 kHz, mono, s16le
_READ_LIMIT = int(MAX_UTTERANCE_SECONDS * _PCM_BYTES_PER_SECOND * 4 / 3) + (1 << 16)

log = logging.getLogger("sinnix-phone-receiver")

_KIND_ALLOWLIST_PATTERN = None  # no restriction; any kind gets its own lane


def _lane_name(kind: str) -> str:
    # Keep lane names filesystem-safe and namespaced under phone-*.
    safe = "".join(c if (c.isalnum() or c in "-_") else "-" for c in kind.strip())
    return f"phone-{safe or 'unknown'}"


class Demuxer:
    def __init__(self, capture_root: Path) -> None:
        self.capture_root = capture_root
        self._writers: dict[str, CaptureWriter] = {}
        # One kind gets special handling, and only one: speech carries audio
        # rather than a reading, so it is written to the lake and transcribed
        # before its envelope is worth anything. Everything else stays on the
        # deliberately dumb path above.
        self._speech = SpeechLane(capture_root)

    def writer_for(self, lane: str) -> CaptureWriter:
        w = self._writers.get(lane)
        if w is None:
            w = CaptureWriter(self.capture_root, lane, host="phone")
            self._writers[lane] = w
        return w

    def ingest_line(self, line: str) -> None:
        line = line.strip()
        if not line:
            return
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            log.warning("dropped malformed line (%d bytes)", len(line))
            return
        if not isinstance(obj, dict):
            log.warning("dropped non-object line")
            return
        kind = str(obj.get("kind", "unknown"))
        if kind == "speech":
            obj = self._speech.ingest(obj)
        lane = _lane_name(kind)
        writer = self.writer_for(lane)
        writer.write(obj)


async def handle_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    demux: Demuxer,
) -> None:
    peer = writer.get_extra_info("peername")
    log.info("client connected: %s", peer)
    try:
        while True:
            try:
                line = await reader.readline()
            except ValueError:
                # Over the limit even so. The module's own rule applies: a
                # single bad line must never take down a connection carrying
                # everything else the phone is sending.
                log.warning("dropped an oversized line from %s", peer)
                continue
            if not line:
                break
            try:
                demux.ingest_line(line.decode("utf-8", errors="replace"))
            except Exception:
                log.exception("error ingesting line from %s", peer)
    finally:
        log.info("client disconnected: %s", peer)
        writer.close()


async def run(host: str, port: int, capture_root: Path) -> None:
    demux = Demuxer(capture_root)
    server = await asyncio.start_server(
        lambda r, w: handle_client(r, w, demux), host=host, port=port, limit=_READ_LIMIT
    )
    addrs = ", ".join(str(s.getsockname()) for s in server.sockets or [])
    log.info("listening on %s, capture_root=%s", addrs, capture_root)
    async with server:
        await server.serve_forever()


def main() -> None:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="bind address (tailscale0 IP, never 0.0.0.0)")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--capture-root", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(run(args.host, args.port, args.capture_root))


if __name__ == "__main__":
    main()
