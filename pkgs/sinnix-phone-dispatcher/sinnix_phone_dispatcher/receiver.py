"""The persistent TCP receiver for the phone's always-on push, absorbed from
the retired `sinnix-phone-receiver` unit (sinnix-tjqi). Protocol: newline-
delimited JSON, one line in -> one envelope written, demuxed by `kind` into
a per-kind capture lane (`phone-<kind>`) under `--capture-root`
(sinnix.paths.machineRoot, NOT this package's own LAKE_ROOT -- the two roots
are deliberately different subjects). Deliberately dumb: no backpressure,
no batching, no reconnect logic -- that lives entirely on the phone-side
client, which owns retry policy for a link that sleeps and roams. A
malformed or oversized line is logged and dropped, not fatal: a single bad
line must never take down a connection carrying everything else the phone
is sending.

The envelope writer is `sinnix_capture.writer.CaptureWriter` -- while this
lived under `scripts/`, a script only got CLI tools on PATH via
runtimeInputs, not a Python package's site-packages, so the writer/envelope
shape was carried as a deliberate stdlib-only duplicate of
pkgs/sinnix-capture/sinnix_capture/{writer,envelope}.py. Packaging this as a
buildPythonApplication removes that constraint: `dependencies = [
sinnix-capture-lib ]` in pkg.nix makes the real implementation importable,
so the port is gone and both sides are now the same code.
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import socketserver
import struct
import sys
import threading
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from sinnix_capture.writer import CaptureWriter

#: The STT hub. Loopback: this process and the hub are the same host.
_STT_ENDPOINT = "http://127.0.0.1:8090/v1/audio/transcriptions"

#: Anything longer than this in one utterance is a VAD that failed open, and
#: decoding it would block the connection for everything behind it.
_MAX_UTTERANCE_SECONDS = 120

#: asyncio's StreamReader (the original receiver's transport) defaults to a
#: 64 KiB line limit, ample for a battery reading and far too small for an
#: utterance: a speech line carries base64 PCM, so its size follows directly
#: from the duration ceiling above. Deriving one from the other means raising
#: the ceiling cannot silently start dropping connections.
_PCM_BYTES_PER_SECOND = 16000 * 2  # 16 kHz, mono, s16le
_PHONE_STREAM_READ_LIMIT = int(
    _MAX_UTTERANCE_SECONDS * _PCM_BYTES_PER_SECOND * 4 / 3
) + (1 << 16)


def _phone_stream_lane_name(kind: str) -> str:
    safe = "".join(c if (c.isalnum() or c in "-_") else "-" for c in kind.strip())
    return f"phone-{safe or 'unknown'}"


def _phone_stream_wav_bytes(pcm: bytes, rate: int) -> bytes:
    """Wrap raw mono 16-bit PCM in a WAV header (44 bytes of arithmetic; the
    phone sends PCM because its VAD already works on samples, not a container)."""
    return (
        b"RIFF"
        + struct.pack("<I", 36 + len(pcm))
        + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
        + b"data"
        + struct.pack("<I", len(pcm))
        + pcm
    )


def _phone_stream_transcribe(wav: bytes, *, timeout: float = 60.0) -> dict | None:
    """Hand a WAV to the STT hub. None means the hub did not answer -- not a
    lost utterance, since the audio is already on disk by the time this runs."""
    boundary = uuid.uuid4().hex
    body = (
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="utterance.wav"\r\n'
            "Content-Type: audio/wav\r\n\r\n"
        ).encode()
        + wav
        + f"\r\n--{boundary}--\r\n".encode()
    )
    req = urllib.request.Request(
        _STT_ENDPOINT,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        print(
            f"phone-dispatcher: phone-stream: stt hub did not answer: {exc}",
            file=sys.stderr,
        )
        return None


class _PhoneSpeechLane:
    """Where utterances land: audio to the lake first, then transcribed
    through the same Parakeet endpoint everything else uses, then the
    transcript joins the capture lane as an envelope. What deliberately does
    NOT happen here is agent dispatch -- see pkgs/sinnix-phone-receiver's
    speech.py module docstring for why an always-on mic stays record-only."""

    def __init__(self, capture_root: Path) -> None:
        self.blob_dir = capture_root / "phone" / "speech"
        self.blob_dir.mkdir(parents=True, exist_ok=True)

    def ingest(self, obj: dict) -> dict:
        payload = obj.pop("audio_b64", None)
        rate = int(obj.get("rate") or 16000)
        seconds = float(obj.get("seconds") or 0)

        if not payload:
            obj["error"] = "speech line carried no audio"
            return obj
        if seconds > _MAX_UTTERANCE_SECONDS:
            obj["error"] = (
                f"utterance of {seconds:.0f}s exceeds the {_MAX_UTTERANCE_SECONDS}s ceiling"
            )
            return obj

        try:
            pcm = base64.b64decode(payload)
        except (ValueError, TypeError) as exc:
            obj["error"] = f"undecodable audio payload: {exc}"
            return obj

        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        name = f"speech-{stamp}-{uuid.uuid4().hex[:8]}.wav"
        wav = _phone_stream_wav_bytes(pcm, rate)

        # Written before transcription, deliberately: the recording must
        # survive a transcription failure.
        part = self.blob_dir / (name + ".part")
        part.write_bytes(wav)
        part.rename(self.blob_dir / name)
        obj["audio_file"] = name
        obj["bytes"] = len(wav)

        result = _phone_stream_transcribe(wav)
        if result is None:
            obj["transcribed"] = False
            return obj
        obj["transcribed"] = True
        obj["text"] = result.get("text", "")
        obj["speech_seconds"] = result.get("speech_seconds")
        obj["engine"] = result.get("engine")
        if obj["text"]:
            print(
                f"phone-dispatcher: phone-stream: utterance ({seconds:.1f}s): {obj['text'][:120]}",
                file=sys.stderr,
            )
        return obj


class _PhoneStreamDemuxer:
    def __init__(self, capture_root: Path) -> None:
        self.capture_root = capture_root
        self._writers: dict[str, CaptureWriter] = {}
        self._speech = _PhoneSpeechLane(capture_root)

    def _writer_for(self, lane: str) -> CaptureWriter:
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
            print(
                f"phone-dispatcher: phone-stream: dropped malformed line ({len(line)} bytes)",
                file=sys.stderr,
            )
            return
        if not isinstance(obj, dict):
            print(
                "phone-dispatcher: phone-stream: dropped non-object line",
                file=sys.stderr,
            )
            return
        kind = str(obj.get("kind", "unknown"))
        if kind == "speech":
            obj = self._speech.ingest(obj)
        lane = _phone_stream_lane_name(kind)
        self._writer_for(lane).write(obj)


class _PhoneStreamHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        peer = self.client_address
        demux: _PhoneStreamDemuxer = self.server.demux  # type: ignore[attr-defined]
        print(
            f"phone-dispatcher: phone-stream: client connected: {peer}", file=sys.stderr
        )
        try:
            while True:
                raw = self.rfile.readline(_PHONE_STREAM_READ_LIMIT + 1)
                if not raw:
                    break
                if raw.endswith(b"\n"):
                    line = raw[:-1]
                    if len(line) > _PHONE_STREAM_READ_LIMIT:
                        print(
                            f"phone-dispatcher: phone-stream: dropped an oversized line "
                            f"({len(line)} bytes) from {peer}",
                            file=sys.stderr,
                        )
                        continue
                    try:
                        demux.ingest_line(line.decode("utf-8", "replace"))
                    except Exception as exc:  # noqa: BLE001 - one bad line must not kill the connection
                        print(
                            f"phone-dispatcher: phone-stream: error ingesting line from {peer}: {exc}",
                            file=sys.stderr,
                        )
                    continue
                if len(raw) <= _PHONE_STREAM_READ_LIMIT:
                    # Fewer bytes than the cap and still no terminator: the
                    # connection closed mid-line.
                    break
                # Over the cap with no terminator yet: drain until the real
                # line ends, then drop the whole thing. A single bad line
                # must never take down a connection carrying everything else
                # the phone is sending.
                print(
                    f"phone-dispatcher: phone-stream: dropped an oversized line from {peer}",
                    file=sys.stderr,
                )
                while True:
                    more = self.rfile.readline(1 << 16)
                    if not more or more.endswith(b"\n"):
                        break
        finally:
            print(
                f"phone-dispatcher: phone-stream: client disconnected: {peer}",
                file=sys.stderr,
            )


class _PhoneStreamServer(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, host: str, port: int, capture_root: Path) -> None:
        self.demux = _PhoneStreamDemuxer(capture_root)
        super().__init__((host, port), _PhoneStreamHandler)


def start_phone_stream_server(
    host: str, port: int, capture_root: Path
) -> _PhoneStreamServer:
    """Start the always-on telemetry receiver as a background thread of this process."""
    server = _PhoneStreamServer(host, port, capture_root)
    thread = threading.Thread(
        target=server.serve_forever, daemon=True, name="phone-stream"
    )
    thread.start()
    print(
        f"phone-dispatcher: phone-stream: listening on {host}:{port}, capture_root={capture_root}",
        file=sys.stderr,
    )
    return server
