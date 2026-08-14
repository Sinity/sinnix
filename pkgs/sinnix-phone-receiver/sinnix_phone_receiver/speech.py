"""The speech half of the phone's always-on push.

The phone's VAD decides what is speech and streams only that. What arrives
here is a short utterance, not a stream of silence, which is what makes an
always-on microphone affordable on a battery and on a link that roams.

Three things happen to an utterance, in this order, and the order is the
design:

1. The audio is written to the lake first. Raw audio is the thing that can be
   re-examined -- re-transcribed by a better engine, re-diarized, attributed to
   a speaker once enrollment is trustworthy -- and a pipeline that transcribed
   and discarded would foreclose all of that. If the later steps fail, the
   recording survives them.
2. It is transcribed through the estate's STT hub, the same Parakeet endpoint
   everything else uses. Inline rather than by a later batch pass, because the
   point of this lane is that speaking reaches prime now.
3. The transcript is written to the capture lane as an envelope, joinable with
   everything else the phone sends.

What deliberately does NOT happen is agent dispatch. An always-on microphone
that can drive agents is an open command channel for anyone in the room, on a
speakerphone, or on a TV -- sinnix-7oly's problem statement -- and the
speaker-conditioning that would filter that is built but measured
NOT discriminative (a different-source clip scored higher than a same-speaker
one). Until that is fixed, this lane listens and records; the deliberate
push-to-talk verb in the phone app remains the way to actually ask for
something. Shipping the channel ungated because the gate is nearly ready is
how an estate acquires a voice-activated foot-gun.
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import logging
import struct
import urllib.error
import urllib.request
import uuid
from pathlib import Path

log = logging.getLogger("sinnix-phone-receiver.speech")

#: The estate's STT hub. Loopback: the receiver and the hub are the same host.
STT_ENDPOINT = "http://127.0.0.1:8090/v1/audio/transcriptions"

#: Anything longer than this in one utterance is a VAD that failed open, and
#: decoding it would block the connection for everything behind it.
MAX_UTTERANCE_SECONDS = 120


def wav_bytes(pcm: bytes, rate: int) -> bytes:
    """Wrap raw mono 16-bit PCM in a WAV header.

    The phone sends PCM because it already has it -- the VAD works on samples,
    not on a container -- and a header is 44 bytes of arithmetic here rather
    than an encoder there.
    """
    return (
        b"RIFF"
        + struct.pack("<I", 36 + len(pcm))
        + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
        + b"data"
        + struct.pack("<I", len(pcm))
        + pcm
    )


def transcribe(wav: bytes, *, timeout: float = 60.0) -> dict | None:
    """Hand a WAV to the STT hub. Returns None when the hub does not answer.

    A missing transcript is not a lost utterance: the audio is already in the
    lake by the time this runs, and the lake pass will pick it up later. So a
    hub that is down degrades the lane's latency, not its record.
    """
    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="utterance.wav"\r\n'
        "Content-Type: audio/wav\r\n\r\n"
    ).encode() + wav + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        STT_ENDPOINT,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        log.warning("stt hub did not answer: %s", exc)
        return None


class SpeechLane:
    """Where utterances land, and what happens to them."""

    def __init__(self, capture_root: Path) -> None:
        self.blob_dir = capture_root / "phone" / "speech"
        self.blob_dir.mkdir(parents=True, exist_ok=True)

    def ingest(self, obj: dict) -> dict:
        """Turn a speech line into the envelope the capture lane should hold.

        Returns the object to write. The audio payload is stripped from it --
        a capture lane is a record, not a place to keep half a megabyte of
        base64 per utterance; the WAV path points at the real thing.
        """
        payload = obj.pop("audio_b64", None)
        rate = int(obj.get("rate") or 16000)
        seconds = float(obj.get("seconds") or 0)

        if not payload:
            obj["error"] = "speech line carried no audio"
            return obj
        if seconds > MAX_UTTERANCE_SECONDS:
            obj["error"] = f"utterance of {seconds:.0f}s exceeds the {MAX_UTTERANCE_SECONDS}s ceiling"
            return obj

        try:
            pcm = base64.b64decode(payload)
        except (ValueError, TypeError) as exc:
            obj["error"] = f"undecodable audio payload: {exc}"
            return obj

        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        name = f"speech-{stamp}-{uuid.uuid4().hex[:8]}.wav"
        wav = wav_bytes(pcm, rate)

        # Written before transcription, deliberately: see the module docstring.
        part = self.blob_dir / (name + ".part")
        part.write_bytes(wav)
        part.rename(self.blob_dir / name)
        obj["audio_file"] = name
        obj["bytes"] = len(wav)

        result = transcribe(wav)
        if result is None:
            obj["transcribed"] = False
            return obj
        obj["transcribed"] = True
        obj["text"] = result.get("text", "")
        obj["speech_seconds"] = result.get("speech_seconds")
        obj["engine"] = result.get("engine")
        if obj["text"]:
            log.info("utterance (%.1fs): %s", seconds, obj["text"][:120])
        return obj
