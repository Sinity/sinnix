"""run: submit job files to a video model, wait, and download each take: Seedance 2.5 on Replicate or Higgsfield, or a
model that takes a first frame only (Grok Imagine Video 1.5) on OpenRouter or Replicate.

  python -m claudia_kit run BOOK.json IDS --provider replicate|higgsfield|openrouter --max-usd N [--model ID] [--takes 1] [--dry-run]
  python -m claudia_kit run BOOK.json IDS --collect      # poll what was submitted, download what has finished
  python -m claudia_kit run BOOK.json --ledger           # the list-price spend recorded so far (takes and stills)

Keys come from the environment only: REPLICATE_API_TOKEN, HIGGSFIELD_API_KEY as "id:secret", or OPENROUTER_API_KEY;
they are never printed or written. Each submit is written to build/ledger.jsonl with its list-price estimate (the
stills of `frames` go in the same ledger), and --max-usd stops any submit that would take the ledger past the cap (it is
required: there is no submit without a cap). A paid submit is never retried: if the network fails while a submit is in
flight, the take may or may not exist, so the kit records it as uncertain and says so instead of trying again. One take
per job unless --takes says more. Takes land in takes/<id>/take-N.mp4 (N is never reused), and each request is kept in
takes/<id>/requests.json.

OpenRouter (--provider openrouter; --model x-ai/grok-imagine-video-1.5, x-ai/grok-imagine-video-1.5-lite or any video
model it lists; by default the book's video_model): the first frame goes up as a JPEG data URL at the take's size, with
no reference images and no audio, so the jobs must be built in the first-frame form (the book's "video_model"). Prices,
durations, resolutions and frame inputs are read from OpenRouter's list of video models when it answers, else from the
kit's own list below.

Replicate runs Seedance 2.5 unless --model names another model (by default the book's video_model): for a first-frame
model such as xai/grok-imagine-video-1.5, the first frame goes up through Replicate's files API as a JPEG at the take's
size, as "image", with the prompt, duration, resolution and aspect ratio. Replicate publishes no price for Grok Imagine:
give --rate, or the kit uses OpenRouter's list for the same model and says it is unconfirmed.
"""
import argparse, base64, json, mimetypes, os, re, subprocess, sys, time, urllib.error, urllib.request, uuid
from .common import Project, jload, jsave

UA = "claudia-kit/0.2"
RATES = {  # US$ per second of generated video at list price, as published by each provider in October 2026: check them
    "replicate": {"480p": 0.1028, "720p": 0.2312},
    "higgsfield": {"480p": 0.2056, "720p": 0.4622, "1080p": 1.1372}}
OR_PRICES = {  # US cents per second of output, and per input image: OpenRouter's list in November 2026, used when it does not answer
    "x-ai/grok-imagine-video-1.5": {"480p": 8, "720p": 14, "1080p": 25, "image": 1},
    "x-ai/grok-imagine-video-1.5-lite": {"480p": 2, "720p": 3, "1080p": 14, "image": 1}}
OR_CAPS = dict(supported_durations=list(range(1, 16)), supported_resolutions=["480p", "720p", "1080p"],   # the same, for both
               supported_aspect_ratios=["16:9", "9:16", "1:1", "4:3", "3:4", "3:2", "2:3"], supported_frame_images=["first_frame"])
REP_FF = {  # first-frame models on Replicate: their limits (the model's schema, November 2026) and a price per second that
    "xai/grok-imagine-video-1.5": dict(durations=list(range(1, 16)), resolutions=["480p", "720p"],   # Replicate does not
        aspects=["auto", "16:9", "4:3", "1:1", "9:16", "3:4", "3:2", "2:3"], usd={"480p": 0.08, "720p": 0.14})}  # publish (OpenRouter's)
PENDING, DONE = {"starting", "processing", "queued", "in_progress", "pending"}, {"succeeded", "completed"}


class RunError(Exception):
    def __init__(self, msg, code=None): super().__init__(msg); self.code = code


def http(method, url, headers, data=None, retry=False):
    """one HTTP call; with retry (free calls only: polls and uploads) it rides out 429/5xx and dropped connections. A JSON
    answer may come after blank lines (OpenRouter keeps a slow submit's connection open with them)."""
    for attempt in range(6 if retry else 1):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, method=method, headers=headers), timeout=180) as r:
                body = r.read(); s = body.lstrip(); return json.loads(s) if s[:1] in (b"{", b"[") else body
        except urllib.error.HTTPError as e:
            if retry and e.code in (429, 500, 502, 503, 504) and attempt < 5: time.sleep(5 * (attempt + 1)); continue
            raise RunError(f"HTTP {e.code} from {method} {url.split('?')[0]}: {e.read()[:400].decode(errors='replace')}", e.code)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if retry and attempt < 5: time.sleep(5 * (attempt + 1)); continue
            raise ConnectionError(f"{method} {url.split('?')[0]}: {e}")


def key(var):
    v = os.environ.get(var)
    if not v: sys.exit(f"set {var} in the environment (the kit reads keys from nowhere else)")
    return v


def take_size(resolution, aspect):
    """a take's frame size: the short side from the resolution (480p: 480; 1K, 2K, 4K: 1080, 1440, 2160), the long side
    from the aspect ratio, both even."""
    s = {"1K": 1080, "2K": 1440, "4K": 2160}.get(resolution) or int(re.match(r"\d+", resolution).group())
    a, b = (float(x) for x in aspect.split(":")); n = int(round(s * max(a, b) / min(a, b) / 2)) * 2
    return (n, s) if a >= b else (s, n)


def jpeg_at(path, W, H):
    """a still as JPEG bytes at W x H, the take's own size: scaled to cover the frame and centred (ffmpeg, the kit's one tool)."""
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase:"
                        f"flags=lanczos,crop={W}:{H},setsar=1,format=yuvj420p", "-frames:v", "1", "-q:v", "2", "-map_metadata", "-1",
                        "-f", "image2pipe", "-c:v", "mjpeg", "-"], capture_output=True)
    if r.returncode or not r.stdout: sys.exit(f"ffmpeg could not read {path}: {r.stderr.decode(errors='replace')[:300]}")
    return r.stdout


class Provider:
    """what every provider shares: list prices per second from RATES, no checks of its own, downloads without a key."""
    name = endpoint = None

    def price(self, job, rate=None):
        r = rate or RATES[self.name].get(job["resolution"])
        if r is None: raise RunError(f"{job['id']}: no list price for {job['resolution']} on {self.name}: give --rate (US$ per second)")
        return round(r * job["duration"], 4), f"${r:.4f} a second ({'--rate' if rate else 'list price, October 2026'})"

    def check(self, job): pass

    def auth(self, url): return {"User-Agent": UA}


class Replicate(Provider):
    """Replicate's HTTP API: files up through /v1/files, the model's predictions. Seedance 2.5 (references named
    [Image1]) unless another model is named: a first-frame model gets the first frame as "image" and the plain prompt."""
    name, api, seedance = "replicate", "https://api.replicate.com/v1", "bytedance/seedance-2.5"

    def __init__(self, model=None):
        self.model = model or self.seedance; self.endpoint = f"models/{self.model}/predictions"
        # a first-frame model (Grok) fetches its image from outside Replicate, and a /v1/files URL needs the token, so
        # the first frame goes inline as a data URL (found by an outside agent's first run: every submit failed unbilled)
        self.inline = self.ff()

    def ff(self): return "seedance" not in self.model

    def check(self, job):
        if not self.ff(): return
        sid, c = job["id"], REP_FF.get(self.model)
        if job.get("mode") != "image":
            raise RunError(f"{sid}: built in Seedance's reference form (her sheet and the vocal as inputs), which {self.model} "
                           "cannot take: set the book's video_model (e.g. grok-imagine-video-1.5) and build again")
        if job.get("last_frame"): raise RunError(f"{sid}: {self.model} takes a first frame only: take the shot's last frame out and build again")
        if c is None: return                            # a model the kit does not know: Replicate answers a wrong value with a 422
        for k, v in (("durations", job["duration"]), ("resolutions", job["resolution"]), ("aspects", job["aspect_ratio"])):
            if v not in c[k]: raise RunError(f"{sid}: {self.model} on Replicate takes {k} {spans(c[k])}, not {v}")

    def price(self, job, rate=None):
        if not self.ff(): return super().price(job, rate)
        r = rate or REP_FF.get(self.model, {}).get("usd", {}).get(job["resolution"])
        if r is None: raise RunError(f"{job['id']}: no price for {self.model} at {job['resolution']}: give --rate (US$ per second)")
        return round(r * job["duration"], 4), f"${r:.4f} a second (" + ("--rate" if rate else "unconfirmed: Replicate publishes no "
                                                                         "price for this model, so this is OpenRouter's for the same model; give --rate") + ")"

    def h(self, extra=None): return {"Authorization": "Bearer " + key("REPLICATE_API_TOKEN"), "User-Agent": UA, **(extra or {})}

    def upload(self, path):
        b = uuid.uuid4().hex; mt = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        data = (f'--{b}\r\nContent-Disposition: form-data; name="content"; filename="{path.name}"\r\nContent-Type: {mt}\r\n\r\n').encode() \
            + path.read_bytes() + f"\r\n--{b}--\r\n".encode()
        return http("POST", self.api + "/files", self.h({"Content-Type": f"multipart/form-data; boundary={b}"}), data, retry=True)["urls"]["get"]

    def body(self, job, url):
        self.endpoint = f"models/{self.model}/predictions"
        if self.ff():                                   # a first frame, no references and no audio
            return dict(prompt=job["prompt"], image=url(job["first_frame"], take_size(job["resolution"], job["aspect_ratio"])),
                        duration=job["duration"], resolution=job["resolution"], aspect_ratio=job["aspect_ratio"])
        p = re.sub(r"@(Image|Audio|Video)(\d+)", r"[\1\2]", job["prompt"])
        base = dict(prompt=p, duration=job["duration"], resolution=job["resolution"], aspect_ratio=job["aspect_ratio"],
                    generate_audio=job["generate_audio"])
        if job["mode"] == "image":
            return dict(base, image=url(job["first_frame"]), **({"last_frame_image": url(job["last_frame"])} if job.get("last_frame") else {}))
        return dict(base, reference_images=[url(x) for x in job["images"]], **({"reference_audios": [url(x) for x in job["audio"]]} if job["audio"] else {}))

    def submit(self, body):
        d = http("POST", f"{self.api}/models/{self.model}/predictions", self.h({"Content-Type": "application/json"}),
                 json.dumps({"input": body}).encode())
        if not isinstance(d, dict) or not d.get("id"): raise ConnectionError(f"no prediction id in the answer: {str(d)[:300]}")
        return d["id"]

    def status(self, rid):
        d = http("GET", f"{self.api}/predictions/{rid}", self.h(), retry=True); out = d.get("output")
        url = out if isinstance(out, str) else (out[0] if isinstance(out, list) and out else (out or {}).get("video") if isinstance(out, dict) else None)
        return d.get("status"), url, d.get("error"), None


class Higgsfield(Provider):
    """Higgsfield's public API: presigned uploads, one endpoint per mode, references named @Image1."""
    name, api = "higgsfield", "https://api.higgsfield.ai"

    def h(self, extra=None):
        return {"Authorization": "Key " + key("HIGGSFIELD_API_KEY"), "Accept": "application/json", "User-Agent": UA, **(extra or {})}

    def upload(self, path):
        ct = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        u = http("POST", self.api + "/files/generate-upload-url", self.h({"Content-Type": "application/json"}),
                 json.dumps({"content_type": ct}).encode(), retry=True)
        http("PUT", u["upload_url"], {**(u.get("upload_headers") or {"Content-Type": ct}), "User-Agent": UA}, path.read_bytes(), retry=True)
        return u["public_url"]

    def body(self, job, url):
        base = dict(prompt=job["prompt"], duration=job["duration"], resolution=job["resolution"], generate_audio=job["generate_audio"])
        if job["mode"] == "image":
            self.endpoint = "bytedance/seedance-2.5/image-to-video"
            return dict(base, image_url=url(job["first_frame"]), **({"end_image_url": url(job["last_frame"])} if job.get("last_frame") else {}))
        self.endpoint = "bytedance/seedance-2.5/reference-to-video"
        return dict(base, aspect_ratio=job["aspect_ratio"], image_urls=[url(x) for x in job["images"]],
                    **({"audio_urls": [url(x) for x in job["audio"]]} if job["audio"] else {}))

    def submit(self, body):
        d = http("POST", f"{self.api}/{self.endpoint}", self.h({"Content-Type": "application/json"}), json.dumps(body).encode())
        if not (d.get("request_id") or d.get("id")): raise ConnectionError(f"no request id in the answer: {str(d)[:300]}")
        return d.get("request_id") or d.get("id")

    def status(self, rid):
        d = http("GET", f"{self.api}/requests/{rid}/status", self.h(), retry=True)
        url = (d.get("video") or {}).get("url") or next((v.get("url") for v in d.get("videos") or [] if v.get("url")), None)
        return d.get("status"), url, d.get("error") or d.get("detail"), None


def or_model(video_model):
    """the OpenRouter id for a book's video_model: grok-imagine-video-1.5 -> x-ai/grok-imagine-video-1.5; an id with a
    slash as it is; anything else (Seedance's reference form) -> the default."""
    m = (video_model or "").strip().replace("xai/", "x-ai/")
    return m if "/" in m else f"x-ai/{m}" if m.startswith("grok") else OpenRouter.default


def rep_model(video_model):
    """the Replicate id for a book's video_model (or --model): grok-imagine-video-1.5 -> xai/grok-imagine-video-1.5;
    Seedance (or none) -> bytedance/seedance-2.5; an id with a slash as it is."""
    m = (video_model or "").strip().replace("x-ai/", "xai/")
    return m if "/" in m else f"xai/{m}" if m.startswith("grok") else Replicate.seedance


def spans(v):
    return f"{v[0]}-{v[-1]}" if len(v) > 2 and all(isinstance(x, int) for x in v) and v == list(range(v[0], v[-1] + 1)) else ", ".join(map(str, v))


class OpenRouter(Provider):
    """OpenRouter's video API: the first frame (and a last frame, where the model takes one) as a JPEG data URL at the
    take's size in frame_images; no reference images and no audio. Its list of video models gives prices and limits."""
    name, api, default, listing, inline = "openrouter", "https://openrouter.ai/api/v1", "x-ai/grok-imagine-video-1.5", {}, True

    def __init__(self, model=None): self.model = model or self.default; self.endpoint = self.model

    def h(self, extra=None): return {"Authorization": "Bearer " + key("OPENROUTER_API_KEY"), "User-Agent": UA, **(extra or {})}

    def info(self):
        """this model's entry in OpenRouter's list of video models, read once per run: None if the list did not answer,
        {} if it does not list the model."""
        if "models" not in self.listing:
            k = os.environ.get("OPENROUTER_API_KEY")         # the list is public; the key goes along when it is set
            try:
                self.listing["models"] = {m["id"]: m for m in http("GET", f"{self.api}/videos/models",
                                                                     {"User-Agent": UA, **({"Authorization": "Bearer " + k} if k else {})})["data"]}
            except (RunError, ConnectionError, KeyError, TypeError) as e:
                self.listing["models"] = None
                print(f"OpenRouter's list of video models did not answer ({str(e)[:120]}): the kit's own prices and limits are used", file=sys.stderr)
        return None if self.listing["models"] is None else self.listing["models"].get(self.model, {})

    def caps(self):
        m = self.info()
        return m if m else OR_CAPS if self.model in OR_PRICES else None

    def check(self, job):
        """stop, before anything is paid, what this model cannot take."""
        sid = job["id"]
        if job.get("mode") != "image":
            raise RunError(f"{sid}: built in Seedance's reference form (her sheet and the vocal as inputs), which a first-frame model "
                           "cannot take: set the book's video_model (e.g. grok-imagine-video-1.5) and build again")
        if self.info() == {}: raise RunError(f"{sid}: OpenRouter lists no video model {self.model!r} (see {self.api}/videos/models)")
        c = self.caps() or {}
        for k, v in (("supported_durations", job["duration"]), ("supported_resolutions", job["resolution"]),
                     ("supported_aspect_ratios", job["aspect_ratio"])):
            if c.get(k) and v not in c[k]: raise RunError(f"{sid}: {self.model} takes {k.split('_', 1)[1]} {spans(c[k])}, not {v}")
        if job.get("last_frame") and c and "last_frame" not in (c.get("supported_frame_images") or []):
            raise RunError(f"{sid}: {self.model} takes a first frame only: take the shot's last frame out and build again")

    def price(self, job, rate=None):
        """per second of output at the take's resolution, plus each input image (and a minimum, where the list has one)."""
        m, res, n = self.info(), job["resolution"], 1 + bool(job.get("last_frame")); sk = (m or {}).get("pricing_skus") or {}
        if sk:
            c = next((float(sk[k]) for k in (f"cents_per_video_output_second_{res}", f"cents_per_second_output_{res}", "cents_per_second_output") if k in sk), None)
            per_s, per_img, low, how = c and c / 100, float(sk.get("cents_per_image_input", 0)) / 100, float(sk.get("minimum_cents_per_generation", 0)) / 100, "OpenRouter's list, read now"
        else:
            fb = OR_PRICES.get(self.model, {}); per_s, per_img, low, how = fb.get(res) and fb[res] / 100, fb.get("image", 0) / 100, 0.0, "the kit's list, November 2026"
        if rate: per_s, how = rate, "--rate"
        if per_s is None: raise RunError(f"{job['id']}: no list price for {self.model} at {res}: give --rate (US$ per second)")
        return round(max(low, per_s * job["duration"] + per_img * n), 4), f"${per_s:.4f} a second + ${per_img:.2f} an input image ({how})"

    def body(self, job, url):
        size = take_size(job["resolution"], job["aspect_ratio"])
        fr = [dict(type="image_url", image_url=dict(url=url(job[k], size)), frame_type=k) for k in ("first_frame", "last_frame") if job.get(k)]
        b = dict(model=self.model, prompt=job["prompt"], duration=job["duration"], resolution=job["resolution"],
                 aspect_ratio=job["aspect_ratio"], frame_images=fr)
        if (self.info() or {}).get("generate_audio") is True: b["generate_audio"] = bool(job.get("generate_audio"))
        return b

    def submit(self, body):
        d = http("POST", f"{self.api}/videos", self.h({"Content-Type": "application/json"}), json.dumps(body).encode())
        if not isinstance(d, dict) or not d.get("id"): raise ConnectionError(f"no job id in the answer: {str(d)[:300]}")
        return d["id"]

    def status(self, rid):
        d = http("GET", f"{self.api}/videos/{rid}", self.h(), retry=True); st = d.get("status")
        return st, f"{self.api}/videos/{rid}/content?index=0" if st == "completed" else None, d.get("error"), (d.get("usage") or {}).get("cost")

    def auth(self, url):                                  # the content URL wants the key; nothing else ever gets it
        return self.h() if url.startswith(self.api + "/") else {"User-Agent": UA}


PROVIDERS = {"replicate": Replicate, "higgsfield": Higgsfield, "openrouter": OpenRouter}


def ledger_rows(P):
    f = P.build / "ledger.jsonl"
    return [json.loads(l) for l in f.read_text().splitlines() if l.strip()] if f.exists() else []


def spent(P):
    return sum(r["usd_est"] for r in ledger_rows(P))


def ledger(P, **row):
    """one paid submit, appended to build/ledger.jsonl (takes and stills share it, and one cap)."""
    P.build.mkdir(parents=True, exist_ok=True)
    with open(P.build / "ledger.jsonl", "a") as f: f.write(json.dumps(row) + "\n")


def requests_of(P, sid): return jload(P.dir / "takes" / sid / "requests.json", [])


def save_requests(P, sid, reqs): jsave(P.dir / "takes" / sid / "requests.json", reqs)


def uploader(P, prov, name):
    """local path -> URL, uploading once (the URL is reused for 20 hours). With a size, the still as a JPEG at that size:
    inline as a data URL where the provider takes one (OpenRouter), else written to build/sent/ and uploaded."""
    cache = jload(P.build / "uploads.json", {})

    def url(rel, size=None):
        if str(rel).startswith("http"): return rel
        f = P.p(rel)
        if size and getattr(prov, "inline", False): return "data:image/jpeg;base64," + base64.b64encode(jpeg_at(f, *size)).decode()
        if size:
            g = P.build / "sent" / (re.sub(r"[^\w.-]+", "_", str(rel)).rsplit(".", 1)[0] + f"-{size[0]}x{size[1]}.jpg")
            if not g.exists() or g.stat().st_mtime < f.stat().st_mtime: g.parent.mkdir(parents=True, exist_ok=True); g.write_bytes(jpeg_at(f, *size))
            f = g
        st = f.stat(); k = f"{name}:{f}:{st.st_mtime}:{st.st_size}"
        if k not in cache or time.time() - cache[k]["at"] > 20 * 3600:
            cache[k] = dict(url=prov.upload(f), at=time.time()); jsave(P.build / "uploads.json", cache)
        return cache[k]["url"]
    return url


def submit(P, sid, prov, cap, rate, dry, planned=0.0):
    """one paid submit (or, with dry, what it would send) -> its list-price estimate."""
    job = P.job(sid); name = prov.name; prov.check(job); c, how = prov.price(job, rate); total = spent(P) + planned
    if total + c > cap + 1e-9:
        raise RunError(f"{sid}: ${c:.2f} would take the ledger from ${total:.2f} past the cap of ${cap:.2f}; nothing sent")
    if dry:
        body = prov.body(job, lambda rel, size=None: f"<upload {rel}>" if not size else f"<JPEG data URL of {rel} at {size[0]}x{size[1]}>"
                         if getattr(prov, "inline", False) else f"<upload {rel} as a JPEG at {size[0]}x{size[1]}>")
        print(f"--- {sid}: {name} {prov.endpoint}, {job['duration']} s at {job['resolution']}, ${c:.2f} list "
              f"(ledger and this run ${total:.2f} -> ${total + c:.2f}, cap ${cap:.2f})")
        print(f"    price: {how}")
        cut = job.get("form") != "first_frame"            # a first-frame prompt is short: shown whole
        print(json.dumps({k: (v[:160] + " ..." if k == "prompt" and cut else v) for k, v in body.items()}, indent=1, ensure_ascii=False))
        return c
    body = prov.body(job, uploader(P, prov, name)); rec = dict(provider=name, at=time.strftime("%Y-%m-%d %H:%M:%S"), usd_est=c)
    if getattr(prov, "model", None): rec["model"] = prov.model
    try:
        rid = prov.submit(body)                           # the paid call: one attempt, never repeated by the kit
    except RunError as e:
        if not (e.code or 0) >= 500: raise              # a 4xx answer: nothing was started
        e = ConnectionError(str(e))                     # a 5xx may hide a started take: treat it as uncertain
        rec.update(id=None, status="uncertain", error=str(e))
        print(f"{sid}: the provider answered {e}; a take may or may not have been started. Check the {name} dashboard "
              "before submitting this shot again.", file=sys.stderr)
    except ConnectionError as e:
        rec.update(id=None, status="uncertain", error=str(e))
        print(f"{sid}: the connection failed during the submit, so a take may or may not have been started. Check the "
              f"{name} dashboard before submitting this shot again. ({e})", file=sys.stderr)
    else:
        rec.update(id=rid, status="submitted")
    ledger(P, at=rec["at"], shot=sid, provider=name, **({"model": rec["model"]} if "model" in rec else {}), id=rec.get("id"),
           usd_est=c, duration=job["duration"], resolution=job["resolution"], uncertain=rec["status"] == "uncertain")
    reqs = requests_of(P, sid); reqs.append(rec); save_requests(P, sid, reqs)
    print(f"{sid}: {rec['status']} {rec.get('id') or ''} (${c:.2f}; ledger ${spent(P):.2f} of ${cap:.2f})")
    return c


def collect(P, ids, every=10, timeout=3600):
    """poll every submitted request of these shots until each has finished; download the takes."""
    t0 = time.time(); left = {(sid, i) for sid in ids for i, r in enumerate(requests_of(P, sid)) if r.get("status") == "submitted"}
    while left and time.time() - t0 < timeout:
        for sid, i in sorted(left):
            reqs = requests_of(P, sid); r = reqs[i]; prov = PROVIDERS[r["provider"]](); st, url, err, usd = prov.status(r["id"])
            if st in PENDING: continue
            left.discard((sid, i))
            if st in DONE and url:
                n = max([int(f.stem.split("-")[1]) for f in P.takes(sid)] + [0]) + 1; out = P.dir / "takes" / sid / f"take-{n}.mp4"
                data = http("GET", url, prov.auth(url), retry=True)
                if not isinstance(data, bytes): print(f"{sid}: the download answered {str(data)[:200]}; run --collect again later"); continue
                tmp = out.with_suffix(".part"); tmp.write_bytes(data); tmp.rename(out)
                r.update(status="done", file=str(out.relative_to(P.dir)), **({"usd": usd} if usd is not None else {}))
                print(f"{sid}: take {n} -> {r['file']}" + (f" (${usd:.2f} as the provider reports it)" if usd is not None else ""))
            else:
                r.update(status=st or "failed", error=str(err)[:300]); print(f"{sid}: {st} {str(err)[:200]}")
            save_requests(P, sid, reqs)
        if left: time.sleep(every)
    for sid, i in sorted(left): print(f"{sid}: still running after {timeout} s; run again with --collect later")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="claudia_kit run", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("book"); ap.add_argument("ids", nargs="*"); ap.add_argument("--provider", choices=list(PROVIDERS))
    ap.add_argument("--model", help="openrouter or replicate: the video model (by default the book's video_model; on OpenRouter "
                                    "x-ai/grok-imagine-video-1.5 for a Seedance book, on Replicate Seedance 2.5)")
    ap.add_argument("--max-usd", type=float, help="the most the ledger may reach (required to submit)")
    ap.add_argument("--takes", type=int, default=1); ap.add_argument("--rate", type=float, help="US$ per second, overriding the list price")
    ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--collect", action="store_true"); ap.add_argument("--ledger", action="store_true")
    ap.add_argument("--timeout", type=float, default=3600); o = ap.parse_args(argv); P = Project(o.book)
    if o.ledger:
        rows = ledger_rows(P); st = [r for r in rows if r.get("kind") == "still"]; tk = [r for r in rows if r.get("kind") != "still"]
        return print(f"ledger: ${spent(P):.2f} at list price over {len(rows)} submits: {len(tk)} takes ${sum(r['usd_est'] for r in tk):.2f}, "
                     f"{len(st)} stills ${sum(r['usd_est'] for r in st):.2f}")
    ids = P.ids(o.ids)
    if o.collect: return collect(P, ids, timeout=o.timeout)
    if not o.provider: sys.exit("give --provider replicate, higgsfield or openrouter")
    if o.model and o.provider == "higgsfield": sys.exit("--model is for --provider openrouter or replicate (Higgsfield runs Seedance 2.5 here)")
    if o.max_usd is None: sys.exit("give --max-usd: the most the ledger may reach after these submits")
    vm = o.model or P.book.get("video_model")
    prov = OpenRouter(or_model(vm)) if o.provider == "openrouter" else Replicate(rep_model(vm)) if o.provider == "replicate" else Higgsfield()
    planned, n = 0.0, 0
    try:
        for sid in ids:
            for _ in range(o.takes): planned += submit(P, sid, prov, o.max_usd, o.rate, o.dry_run, planned if o.dry_run else 0.0); n += 1
    except RunError as e:
        print(e, file=sys.stderr)
    if o.dry_run: print(f"dry run: {n} submit(s) within the cap, ${planned:.2f} at list price; nothing was sent")
    elif planned: collect(P, ids, timeout=o.timeout)


if __name__ == "__main__":
    main()
