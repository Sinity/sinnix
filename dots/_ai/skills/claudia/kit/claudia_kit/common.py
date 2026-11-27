"""Shared helpers: audio through ffmpeg, levels, JSON, the project file (the shot book) and optional imports."""
import importlib, json, pathlib, shutil, subprocess, sys, wave
import numpy as np

FRAME = 0.01                        # every level and feature in the kit is measured in 10 ms frames


def need(module, pip=None, what="this step"):
    """Import an optional package, or stop with a message saying how to get it."""
    try:
        return importlib.import_module(module)
    except ImportError:
        sys.exit(f"{what} needs the optional package '{pip or module}': pip install {pip or module}")


def ffmpeg(*args, quiet=True):
    """Run ffmpeg (stop with a clear message if it is not installed)."""
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg is not on PATH: install it from https://ffmpeg.org (it is the kit's one required tool)")
    return subprocess.run(["ffmpeg", "-v", "error" if quiet else "info", "-y", *map(str, args)], check=True)


def probe(path):
    """duration, audio present, width, height, fps and frame count of a media file (its picture, not a cover image)."""
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "format=duration:stream=codec_type,width,height,avg_frame_rate,nb_frames:stream_disposition=attached_pic",
                          "-of", "json", str(path)], capture_output=True, text=True, check=True).stdout
    d = json.loads(out); st = d.get("streams", [])
    v = next((s for s in st if s["codec_type"] == "video" and not (s.get("disposition") or {}).get("attached_pic")), {})
    num, _, den = (v.get("avg_frame_rate") or "0/1").partition("/")
    return dict(duration=float(d.get("format", {}).get("duration", 0)), audio=any(s["codec_type"] == "audio" for s in st),
                width=v.get("width"), height=v.get("height"), fps=float(num) / float(den or 1) if float(den or 1) else 0,
                frames=int(v.get("nb_frames") or 0))


def load_audio(path, sr=16000, channels=1, start=None, dur=None):
    """The first audio stream of any file as float32, (n,) or (n, channels); empty if the file has no sound."""
    pre = (["-ss", f"{start:.4f}"] if start is not None else []) + (["-t", f"{dur:.4f}"] if dur is not None else [])
    r = subprocess.run(["ffmpeg", "-v", "error", *pre, "-i", str(path), "-map", "a:0", "-ac", str(channels), "-ar", str(sr),
                        "-f", "f32le", "-"], capture_output=True)
    y = np.frombuffer(r.stdout, np.float32).copy()
    return y.reshape(-1, channels) if channels > 1 else y


def level_db(y, sr=16000):
    """RMS level in dBFS per 10 ms frame."""
    hop = int(sr * FRAME); n = len(y) // hop
    return 20 * np.log10(np.sqrt((y[:n * hop].reshape(n, hop) ** 2).mean(1)) + 1e-7)


def ref_db(db):
    """A stem's working loudness: the 95th percentile of its frames above -60 dB. Thresholds are set relative to it."""
    v = db[db > -60]
    return float(np.percentile(v, 95)) if len(v) else -20.0


def write_wav(path, y, sr):
    """float (n,) or (n, ch) -> 16-bit PCM WAV."""
    y = y.reshape(len(y), -1); path = pathlib.Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(y.shape[1]); f.setsampwidth(2); f.setframerate(sr)
        f.writeframes((np.clip(y, -1, 1) * 32767).astype("<i2").tobytes())


def jload(path, default=None):
    """a JSON file (or YAML, if PyYAML is installed and the name ends .yaml or .yml)."""
    p = pathlib.Path(path)
    if not p.exists():
        if default is None: sys.exit(f"missing file: {p}")
        return default
    if p.suffix in (".yaml", ".yml"): return need("yaml", "PyYAML", "a YAML shot book").safe_load(p.read_text())
    return json.loads(p.read_text())


def jsave(path, obj):
    p = pathlib.Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n")


class Project:
    """The shot book (a JSON file) and everything it names. Paths inside it are relative to its own folder."""

    def __init__(self, path):
        self.path = pathlib.Path(path).resolve(); self.dir = self.path.parent; self.book = jload(self.path)
        self.build = self.p(self.book.get("build", "build")); self._lines = None

    def p(self, rel):
        return None if rel in (None, "") else self.dir / rel

    def audio(self, key, required=True):
        """song, lead, rest, group or words, as named in the book's "audio" block."""
        v = self.p((self.book.get("audio") or {}).get(key))
        if required and (v is None or not v.exists()): sys.exit(f"the book's audio.{key} is missing or not found: {v}")
        return v if v is not None and v.exists() else None

    @property
    def lines(self):
        if self._lines is None:
            self._lines = {x["id"]: x for x in jload(self.build / "lines.json")["lines"]}
        return self._lines

    @property
    def shots(self):
        return self.book.get("shots", [])

    def shot(self, sid):
        s = next((s for s in self.shots if s["id"] == sid), None)
        return s if s is not None else sys.exit(f"no shot {sid!r} in {self.path.name}")

    def ids(self, given):
        return given or [s["id"] for s in self.shots]

    def job(self, sid):
        return jload(self.build / "jobs" / f"{sid}.json")

    def takes(self, sid):
        """the take files of a shot, oldest first: takes/<id>/take-N.mp4"""
        return sorted((self.dir / "takes" / sid).glob("take-*.mp4"), key=lambda f: int(f.stem.split("-")[1]))

    def take(self, sid, n=None):
        """(file, N): take N, else the book's pick, else the newest; (None, None) if there is none."""
        fs = self.takes(sid); n = n or (self.book.get("picks") or {}).get(sid)
        if not fs: return None, None
        f = next((f for f in fs if int(f.stem.split("-")[1]) == n), None) if n else fs[-1]
        return (f, int(f.stem.split("-")[1])) if f else (None, None)
