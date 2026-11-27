"""sync: place each take on the song, word by word.

  python -m claudia_kit sync align BOOK.json [IDS] [--take N] [--face-model face_landmarker.task] [--by sound|lips]
  python -m claudia_kit sync check BOOK.json [IDS] [--take N]      # per phrase: cost, rate, offsets, and what to look at
  python -m claudia_kit sync mouth BOOK.json [IDS] [--take N] --face-model face_landmarker.task
  python -m claudia_kit sync lips  BOOK.json [IDS] [--take N] [--face-model ...]   # lips shut on every b, m and p?

Sync is a path, not an offset: takes come back from 0.6 s early to 0.4 s late, each phrase with its own offset (the
model moves the silences), often 10-16% slower than the stem.
- A take WITH sound: its own soundtrack is aligned to the window it was given (log-mel every 10 ms, subsequence DTW
  per sung phrase). The map song time -> clip time follows that path where the window is voiced and runs straight
  through the silences. Cost 0 is the same sound; a clean copy is 0.05-0.2, a re-sung line 0.2-0.4, above that it
  sang something else.
- A take WITHOUT sound is placed by her lips (MediaPipe's face landmarker, optional): each sung phrase goes on the
  mouth's own singing, and each b, m and p after a line's first word goes on the frame where her lips part.
  The model file: download face_landmarker.task from the MediaPipe Face Landmarker guide (Google AI Edge) and pass
  --face-model.
- A take from a model that could not hear the song (a first-frame model: the job says sync "lips") is placed by her
  lips too, whatever sound it came back with: that sound is its own invention. `sync check` then says how well her
  lips match the song as cut. It is approximate; --by sound or --by lips overrides the job.
Writes takes/<id>/take-N.sync.json (and take-N.mouth.json). The cut reads the map from there, plus any hand knots
and nudges in the book.
"""
import argparse, re, sys
import numpy as np
from .common import Project, jload, jsave, level_db, load_audio, probe, need, ref_db

SR, HOP, NFFT, NM = 16000, 160, 512, 40


def melfb():
    hz2m = lambda f: 2595 * np.log10(1 + f / 700); m2hz = lambda m: 700 * (10 ** (m / 2595) - 1)
    pts = m2hz(np.linspace(hz2m(120), hz2m(6500), NM + 2)); bins = np.fft.rfftfreq(NFFT, 1 / SR); fb = np.zeros((NM, len(bins)))
    for i in range(NM):
        l, c, r = pts[i:i + 3]; fb[i] = np.clip(np.minimum((bins - l) / (c - l), (r - bins) / (r - c)), 0, None)
    return fb


def feats(x):
    """log-mel every 10 ms with each frame's mean removed, so level does not matter."""
    n = 1 + (len(x) - NFFT) // HOP
    if n < 10: return np.zeros((0, NM))
    idx = np.arange(NFFT)[None, :] + HOP * np.arange(n)[:, None]
    M = np.log((np.abs(np.fft.rfft(x[idx] * np.hanning(NFFT), axis=1)) ** 2) @ melfb().T + 1e-9)
    return M - M.mean(1, keepdims=True)


def subdtw(R, T, step=0.06):
    """align all of R (window frames) somewhere inside T (take frames) -> take frame per window frame, mean cost."""
    Rn = R / (np.linalg.norm(R, axis=1, keepdims=True) + 1e-9); Tn = T / (np.linalg.norm(T, axis=1, keepdims=True) + 1e-9)
    C = 1 - Rn @ Tn.T; n, m = C.shape; D = np.full((n, m), np.inf, np.float32); B = np.zeros((n, m), np.int8); D[0] = C[0]
    for i in range(1, n):
        diag = np.r_[np.inf, D[i - 1, :-1]]; up = D[i - 1] + step                 # up: the take holds while the window runs
        row = np.minimum(diag, up) + C[i]; B[i] = (up < diag)
        for j in range(1, m):                                                     # left: the take runs while the window holds
            v = row[j - 1] + C[i, j] + step
            if v < row[j]: row[j] = v; B[i, j] = 2
        D[i] = row
    j = int(np.argmin(D[-1])); i = n - 1; path = np.zeros(n); cnt = np.zeros(n); cost = float(D[-1, j]) / n
    while True:
        path[i] += j; cnt[i] += 1
        if i == 0: break
        b = B[i, j]
        if b == 0: i -= 1; j -= 1
        elif b == 1: i -= 1
        else: j -= 1
        j = max(j, 0)
    return path / np.maximum(cnt, 1), cost


def align(take, win, phrases):
    """per phrase (window seconds): knots (window time, take time) every 0.1 s along the smoothed path, and its cost."""
    T, R = feats(load_audio(take, SR)), feats(load_audio(win, SR)); out = []
    for a, b, w in phrases:
        i0, i1 = max(0, int((a - 0.05) * 100)), min(len(R), int((b + 0.05) * 100)); j0, j1 = max(0, i0 - 130), min(len(T), i1 + 90)
        if i1 - i0 < 20 or j1 - j0 < i1 - i0 - 60: out.append(dict(a=a, b=b, words=w, cost=None, knots=[])); continue
        j, cost = subdtw(R[i0:i1], T[j0:j1]); tt = (j + j0) / 100.0; wt = np.arange(i0, i1) / 100.0
        k, e = 25, 12                                     # smooth over 0.25 s, carry the end slopes out from inside
        sm = np.convolve(np.pad(tt, (e, e), mode="edge"), np.ones(k) / k, mode="valid")
        if len(sm) > 4 * e:
            sm[:e] = sm[e] - (sm[2 * e] - sm[e]) / e * np.arange(e, 0, -1); sm[-e:] = sm[-e - 1] + (sm[-e - 1] - sm[-2 * e - 1]) / e * np.arange(1, e + 1)
        kn = [(float(wt[q]), float(sm[q])) for q in list(range(0, len(wt), 10)) + [len(wt) - 1]]
        fixed = [kn[0]]
        for w1, t1 in kn[1:]:                              # the rate stays within 0.7-1.4 between knots
            w0_, t0_ = fixed[-1]; r = min(1.4, max(0.7, (t1 - t0_) / max(1e-6, w1 - w0_))); fixed.append((w1, t0_ + r * (w1 - w0_)))
        out.append(dict(a=round(a, 2), b=round(b, 2), words=w, cost=round(cost, 3), knots=[[round(x, 3), round(y, 3)] for x, y in fixed]))
    return out


def env_db(path):
    return level_db(load_audio(path, SR), SR)


def sound_map(job, res, win):
    """follow the path where the window is VOICED and nowhere else: in a silence the path is free and wanders, and a
    map that follows it makes the picture stutter. A 0.5 s median takes the jitter out of the treads."""
    w0, D = job["w0"], job["duration"]; good = [r for r in res if r["cost"] is not None and r["cost"] <= 0.45 and len(r["knots"]) >= 2]
    if not good: return [[w0, 0.0], [w0 + D, float(D)]]
    db = env_db(win); voiced = db > db.max() - 28
    ok = lambda w: int((w - .08) * 100) >= 0 and int((w + .08) * 100) < len(voiced) and voiced[int((w - .08) * 100):int((w + .08) * 100) + 1].all()
    kn = [(w, t) for r in good for w, t in r["knots"] if ok(w)] or [(w, t) for r in good for w, t in r["knots"]]
    W = np.array([a for a, _ in kn]); O = np.array([b - a for a, b in kn]); Om = np.array([np.median(O[abs(W - w) <= 0.25]) for w in W])
    k = [(w0 - Om[0], 0.0)] + [(w0 + w, w + o) for w, o in zip(W, Om)] + [(w0 + D - Om[-1], float(D))]
    return monotone(k)


def monotone(k):
    out = []
    for a, b in k:
        if not out or (a > out[-1][0] + 1e-6 and b >= out[-1][1]): out.append([round(a, 3), round(b, 3)])
    return out


def at(k, t):
    """clip time for song time t along knots k (straight at 1x outside them)."""
    ks, kc = [a for a, _ in k], [b for _, b in k]
    return kc[0] - (ks[0] - t) if t < ks[0] else kc[-1] + (t - ks[-1]) if t > ks[-1] else float(np.interp(t, ks, kc))


def final_map(P, sid, job=None, n=None):
    """the map the cut uses: the measured one, then hand knots from the book in its place between their first and last
    song times (a first or last knot whose clip time is null says where the measured map stops and starts again:
    [[160.6, null], [160.9, 6.03], [161.0, 6.36], [163.5, null]]), then a nudge (seconds added to clip time)."""
    job = job or P.job(sid); f, n = P.take(sid, n)
    sj = jload(f.with_suffix(".sync.json"), {}) if f else {}
    k = sj.get("map") or [[job["w0"], 0.0], [job["w0"] + job["duration"], float(job["duration"])]]
    hand = (P.book.get("knots") or {}).get(sid)
    if hand:
        pts = [[float(a), float(b)] for a, b in hand if b is not None]
        lo = hand[0][0] if hand[0][1] is None else pts[0][0] - 1e-6; hi = hand[-1][0] if hand[-1][1] is None else pts[-1][0] + 1e-6
        k = [q for q in k if q[0] <= lo] + pts + [q for q in k if q[0] >= hi]
    nudge = (P.book.get("nudge") or {}).get(sid, 0.0)
    return [[a, b + nudge] for a, b in monotone(k)]


# ---- her mouth, for takes without sound ----
WIN = [(1, .5, .5)] + [(2, cx, cy) for cy in (.36, .5) for cx in (.5, .3, .7, .18, .82)] + [(3, cx, .38) for cx in (.5, .3, .7)]


def mouth(take, model):
    """the mouth's opening per frame (inner lips over face height); a small face is looked for again in 2x and 3x crops."""
    need("mediapipe", what="the mouth measure"); cv2 = need("cv2", "opencv-python", "the mouth measure")
    import mediapipe as mp
    from mediapipe.tasks import python as mpp
    from mediapipe.tasks.python import vision
    fm = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
        base_options=mpp.BaseOptions(model_asset_path=str(model)), running_mode=vision.RunningMode.IMAGE, num_faces=1,
        min_face_detection_confidence=0.3, min_face_presence_confidence=0.3))
    cap, out, last = cv2.VideoCapture(str(take)), [], None
    while True:
        ok, im = cap.read()
        if not ok: break
        h, w = im.shape[:2]; val = None
        for z, cx, cy in ([last] if last else []) + WIN:
            if z == 1: c = im
            else:
                ch, cw = h // z, w // z; x0 = int(min(max(cx * w - cw / 2, 0), w - cw)); y0 = int(min(max(cy * h - ch / 2, 0), h - ch))
                c = cv2.resize(im[y0:y0 + ch, x0:x0 + cw], (w, h), interpolation=cv2.INTER_CUBIC)
            r = fm.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(cv2.cvtColor(c, cv2.COLOR_BGR2RGB))))
            if r.face_landmarks:
                L = r.face_landmarks[0]; last = (z, cx, cy); val = abs(L[14].y - L[13].y) / (abs(L[152].y - L[10].y) + 1e-6); break
        out.append(None if val is None else round(float(val), 4))
    fm.close()
    return dict(fps=probe(take)["fps"] or 24, open=out, found=round(sum(v is not None for v in out) / max(1, len(out)), 3))


def norm_mouth(d, lo=10):
    m = np.array([np.nan if v is None else v for v in d["open"]], float); i = np.arange(len(m)); g = ~np.isnan(m)
    m = np.interp(i, i[g], m[g]) if g.any() else np.zeros(len(m)); m = m - np.percentile(m, lo)
    return m / (np.percentile(m, 95) + 1e-6)


def bmp_words(P, job, skip_first=True):
    """(song time, word) for every word of the shot's lines that starts with b, m or p, at the transcription's time,
    leaving out each line's first word (after a pause a transcription puts words early; the lip offsets below were
    measured against transcription times, so the times are not moved)."""
    out = []
    for lid in job["lines"]:
        for i, w in enumerate(P.lines[lid].get("words_t") or []):
            tx = re.sub(r"[^a-z]", "", w["w"].lower())
            if tx and tx[0] in "bmp" and not (skip_first and i == 0): out.append((w["t0"], tx))
    return out


def lips_map(P, job, d):
    """a take placed by her lips: the longest open-mouth runs, in order, one per phrase (the mouth opens about 0.12 s
    before the line sounds; these takes sing 10-20% slower); then each b, m, p laid on the frame where her lips part.
    -> (map, notes), or (None, notes) with why it could not be placed."""
    w0, D, ph, fps = job["w0"], job["duration"], job["phrases"], d["fps"]; m = norm_mouth(d); on = m > 0.25; runs, i = [], 0
    while i < len(m):
        if not on[i]: i += 1; continue
        j = i
        while j < len(m) and (on[j] or on[j:j + 9].any()): j += 1
        while j > i and not on[j - 1]: j -= 1
        if j - i >= 7: runs.append((i / fps, j / fps))
        i = j + 1
    notes = dict(found=d["found"], runs=len(runs)); runs = sorted(sorted(runs, key=lambda r: r[0] - r[1])[:len(ph)])
    if d["found"] < 0.5: return None, dict(notes, why=f"her face was found in {d['found']:.0%} of the frames")
    if len(runs) != len(ph): return None, dict(notes, why=f"{len(runs)} open-mouth runs for {len(ph)} sung phrases")
    k, per = [], []
    for (ra, rb), (a, b, w) in zip(runs, ph):
        ca = ra + 0.05; raw = (rb + 0.12 - ca) / (b - a); r = min(1.22, max(0.95, raw)); k += [(w0 + a, ca), (w0 + b, ca + r * (b - a))]
        per.append(dict(a=round(a, 2), b=round(b, 2), words=w, mouth=[round(ra, 2), round(rb, 2)], rate=round(raw, 3), anchors=0))
    anchors = []
    for t, tx in bmp_words(P, job):
        c = at(k, t); i0, i1 = max(1, int((c - 0.15) * fps)), min(len(m) - 1, int((c + 0.45) * fps) + 1)
        if i1 - i0 < 3: continue
        j = i0 + int(np.argmin(m[i0:i1]))
        if m[j] > 0.25: continue
        while j + 1 < len(m) and m[j + 1] <= 0.25: j += 1          # the lips PART here: the word is heard as they open
        c = (j + 1) / fps - (0.08 if tx[0] == "m" else 0.04)
        if not anchors or c > anchors[-1][1] + 0.1: anchors.append((t, c))
    for p, (a, b, _) in zip(per, ph):                               # per phrase: the anchors, and on at a steady rate to its end
        an = [q for q in anchors if w0 + a <= q[0] <= w0 + b]; p["anchors"] = len(an)
        if not an: continue
        end_c = at(k, w0 + b); tl, cl = an[-1]; r = min(1.25, max(0.9, (end_c - cl) / max(0.2, w0 + b - tl)))
        k = [q for q in k if q[0] < w0 + a] + an + [(w0 + b, cl + r * (w0 + b - tl))] + [q for q in k if q[0] > w0 + b]
    k = sorted(k); return monotone([(k[0][0] - 3, k[0][1] - 3)] + k + [(k[-1][0] + 3, k[-1][1] + 3)]), dict(notes, phrases=per)


def agree(P, job, d, k):
    """her mouth against her voice, as the cut shows the take (song time over the shot's show, through the map k): the
    share of the frames where she sings that have her mouth open (within 0.1 s: it opens a little before the sound),
    and of the frames 0.2 s or more from her voice that have it shut. Her voice: the lead stem, inside the shot's own
    lead lines (a group's lines count as silence: her lips stay closed while they sing). -> (open, shut), None if unknown."""
    gate = [(a, b) for who, a, b in job.get("gate", []) if who == "lead"]; lead = P.audio("lead", False); s0, s1 = job["show"]
    if not gate or lead is None or s1 - s0 < 0.5: return None
    db = level_db(load_audio(lead, 16000, 1, s0, s1 - s0)); T = s0 + (np.arange(len(db)) + 0.5) / 100
    voice = (db > ref_db(db) - 18) & np.any([(T >= a) & (T <= b) for a, b in gate], axis=0)
    grow = lambda x, r: np.convolve(x.astype(float), np.ones(2 * r + 1), "same") > 0
    m = norm_mouth(d); i = np.clip(np.round(np.array([at(k, t) for t in T]) * d["fps"]).astype(int), 0, len(m) - 1); op = m[i] > 0.25
    sung, quiet = voice, ~grow(voice, 20)
    return (float((grow(op, 10) & sung).sum() / sung.sum()) if sung.sum() >= 20 else None,
            float((~op & quiet).sum() / quiet.sum()) if quiet.sum() >= 20 else None)


def check_sound(take, win, res):
    """the global lag and waveform match, and every pause the take makes inside a phrase that the song does not (a full
    stop in the prompt's words does that): -> dict(lag, ncc, pauses [(clip time, take pause s, song pause s)])"""
    a, b = load_audio(take, SR), load_audio(win, SR); n = 1 << int(np.ceil(np.log2(len(a) + len(b))))
    xc = np.fft.irfft(np.fft.rfft(a, n) * np.conj(np.fft.rfft(b, n)), n); lags = np.r_[np.arange(n // 2), np.arange(-n // 2, 0)]
    xc[abs(lags) > SR] = -np.inf; kk = int(np.argmax(xc)); ncc = float(xc[kk] / np.sqrt((a ** 2).sum() * (b ** 2).sum() + 1e-12))
    tdb, wdb = level_db(a, SR), level_db(b, SR); tq, wq = np.percentile(tdb[tdb > -60], 95) - 15, np.percentile(wdb[wdb > -60], 95) - 15
    pauses = []
    for r in res:
        if len(r["knots"]) < 2: continue
        W, T = np.array(r["knots"]).T; i0 = int(T[0] * 100); q = np.r_[tdb[i0:int(T[-1] * 100)] < tq, False]; j = None
        for i, v in enumerate(q):
            if v and j is None: j = i
            elif not v and j is not None:
                if i - j >= 15:
                    ta, tb = (i0 + j) / 100, (i0 + i) / 100; wa, wb = np.interp([ta, tb], T, W)
                    sq = (wdb[max(0, int((wa - .1) * 100)):int((wb + .1) * 100)] < wq).sum() / 100
                    if tb - ta - sq > 0.15: pauses.append((round(ta, 2), round(tb - ta, 2), round(sq, 2)))
                j = None
    return dict(lag=round(lags[kk] / SR, 3), ncc=round(ncc, 3), pauses=pauses)


def do_align(P, sid, n, model, by=None):
    job = P.job(sid); f, n = P.take(sid, n)
    if job["kind"] != "sung" or f is None: return None
    win = job.get("window") or (job.get("audio") or [None])[0]; by = by or job.get("sync")
    y = load_audio(f, 8000); heard = len(y) > 4000 and np.abs(y).max() > 0.003      # a take with no sound track, or a silent one,
    if by == "sound" and not (heard and win): print(f"{sid} take {n}: no soundtrack to align by: placed by her lips")   # is placed
    if heard and win and by != "lips":                                                                                  # by her lips
        res = align(f, P.p(win), job["phrases"]); k = sound_map(job, res, P.p(win)); method, notes = "sound", None
    else:
        mj = f.with_suffix(".mouth.json")
        if not mj.exists() and model: jsave(mj, mouth(f, model))
        d = jload(mj, {}); k, notes = lips_map(P, job, d) if d else (None, dict(why="no mouth measure (give --face-model)")); res = []; method = "lips"
        if k is None:
            k = [[job["w0"] - 0.1, 0.0], [job["w0"] + job["duration"] - 0.1, float(job["duration"])]]; method = "none"
            print(f"{sid} take {n}: not placed by her lips ({notes['why']}): placed at its window, judge by eye")
    sj = dict(take=n, w0=job["w0"], D=job["duration"], method=method, phrases=res, map=k, **({"lips": notes} if notes else {}))
    jsave(f.with_suffix(".sync.json"), sj)
    return sj


def lips_report(P, sid, n, job, sj, f):
    """how a take placed by her lips sits on the song: per phrase, the open-mouth run it went on and the rate; as cut, her
    mouth against her voice; and her lips on the b, m and p (with word times from songmap words)."""
    why = "the model did not hear the song" if job.get("sync") == "lips" and not job.get("audio") else "no soundtrack"
    notes = sj.get("lips") or {}; d = jload(f.with_suffix(".mouth.json"), {})
    print(f"{sid} take {n}  window from {job['w0']:.2f} s  placed by her lips ({why}); her face found in {notes.get('found', d.get('found', 0)):.0%} of the frames")
    for p in notes.get("phrases", []):
        flag = "  << slower or faster than she can sing it: look at it" if not 0.95 <= p["rate"] <= 1.22 else ""
        print(f"   {p['a']:5.2f}-{p['b']:5.2f}  mouth {p['mouth'][0]:5.2f}-{p['mouth'][1]:5.2f}  rate {p['rate']:.2f}  "
              f"{p['anchors']} b/m/p  {p['words'][:44]}{flag}")
    k = final_map(P, sid, job, n); g = agree(P, job, d, k) if d else None
    if g and any(x is not None for x in g):
        txt = " and ".join(t for t in [f"open on {g[0]:.0%} of the frames where she sings" if g[0] is not None else "",
                                       f"shut on {g[1]:.0%} of those where she is silent" if g[1] is not None else ""] if t)
        print(f"   as cut, her mouth is {txt}" + ("  << look at it" if min(x for x in g if x is not None) < 0.6 else ""))
    out, med = closures(P, job, d, k) if d and d.get("found", 0) >= 0.6 else ([], None)
    if out: print(f"   b, m, p: " + (f"median {med:+.2f} s over {sum(o is not None for _, o in out)} of {len(out)} closed" if med is not None
                                     else "none found closed") + ("  << look at it" if med is None or abs(med) > 0.09 else "  in sync"))
    elif d: print("   b, m, p: no word times to check them against (songmap words)")
    print("   lips alone place a take approximately: judge it by eye, closest in the close singing shots")


def report(P, sid, n):
    job = P.job(sid); f, n = P.take(sid, n)
    if f is None or job["kind"] != "sung": return
    sj = jload(f.with_suffix(".sync.json"), {}) or do_align(P, sid, n, None); head = f"{sid} take {n}  window from {job['w0']:.2f} s"
    if sj["method"] == "lips": return lips_report(P, sid, n, job, sj, f)
    if sj["method"] != "sound":
        return print(f"{head}  placed at its window ({(sj.get('lips') or {}).get('why', 'no measure')}): judge it by eye, or measure "
                     "her mouth (sync align --face-model)")
    c = check_sound(f, P.p(job.get("window") or job["audio"][0]), sj["phrases"])
    print(f"{head}  global lag {c['lag']:+.2f} s, waveform match {c['ncc']:.2f} (above 0.6 is a sample copy; judge by the cost)")
    for r in sj["phrases"]:
        if r["cost"] is None: print(f"   {r['a']:5.2f}-{r['b']:5.2f}  no measure  {r['words'][:50]}"); continue
        offs = [t - w for w, t in r["knots"]]; rate = (r["knots"][-1][1] - r["knots"][0][1]) / max(1e-6, r["knots"][-1][0] - r["knots"][0][0])
        flag = ("" if r["cost"] <= 0.2 else "  << re-sung: look at it" if r["cost"] <= 0.4 else "  << NOT our line") + \
               ("  << drifts: %+.0f%% speed" % (100 * (rate - 1)) if abs(rate - 1) > 0.18 else "")
        print(f"   {r['a']:5.2f}-{r['b']:5.2f}  cost {r['cost']:.2f}  rate {rate:.2f}  offsets {offs[0]:+.2f} {offs[len(offs) // 2]:+.2f} "
              f"{offs[-1]:+.2f}  {r['words'][:44]}{flag}")
    for t, tp, sp in c["pauses"]:
        print(f"   << the take pauses {tp:.2f} s at clip {t:.2f} where the song pauses {sp:.2f} s (a full stop in its words?): "
              "finish the map by hand through it (the book's knots)")


def closures(P, job, d, k):
    """for every b, m and p: the nearest closing of her lips to the word, along the map k, in s (None: open there)
    -> ([(word, s)], their median)"""
    fps = d["fps"]; m = norm_mouth(d, 5); out = []
    for t, tx in bmp_words(P, job):
        c = at(k, t); i0, i1 = int((c - 0.30) * fps), int((c + 0.30) * fps) + 1
        if i0 < 1 or i1 >= len(m) - 1: continue
        j = int(np.argmin(m[i0:i1])); out.append((tx, None if m[i0 + j] > 0.22 else round((i0 + j + 0.5) / fps - c, 2)))
    hits = [o for _, o in out if o is not None]
    return out, (float(np.median(hits)) if hits else None)


def lips(P, sid, n, model):
    """her lips must be SHUT on every b, m and p: where is the nearest closing to each, against the cut's map?"""
    job = P.job(sid); f, n = P.take(sid, n)
    if f is None or job["kind"] != "sung": return
    mj = f.with_suffix(".mouth.json")
    if not mj.exists():
        if not model: return print(f"{sid} take {n}: no mouth measure (run sync mouth with --face-model)")
        jsave(mj, mouth(f, model))
    d = jload(mj)
    if d["found"] < 0.6: return print(f"{sid} take {n}: face found in {d['found']:.0%} of frames: no measure")
    out, med = closures(P, job, d, final_map(P, sid, job, n)); hits = [o for _, o in out if o is not None]
    print(f"{sid:6s} take {n}: " + " ".join(f"{w}{o:+.2f}" if o is not None else f"{w}(open)" for w, o in out)
          + (f"   median {med:+.2f} s over {len(hits)}" if hits else "   no b/m/p found closed")
          + ("   << look at it" if med is None or abs(med) > 0.09 or len(hits) < max(1, len(out) // 2) else "   in sync"))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="claudia_kit sync", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["align", "check", "mouth", "lips"]); ap.add_argument("book"); ap.add_argument("ids", nargs="*")
    ap.add_argument("--take", type=int); ap.add_argument("--face-model", help="MediaPipe's face_landmarker.task")
    ap.add_argument("--by", choices=["sound", "lips"], help="align: by the take's soundtrack or by her lips, over the job's own choice")
    o = ap.parse_args(argv); P = Project(o.book)
    for sid in P.ids(o.ids):
        if P.shot(sid).get("kind", "sung") != "sung" or not P.takes(sid): continue
        if o.cmd == "align":
            sj = do_align(P, sid, o.take, o.face_model, o.by)
            if sj: print(f"{sid} take {sj['take']}: {sj['method']}, {len(sj['map'])} knots")
        elif o.cmd == "check": report(P, sid, o.take)
        elif o.cmd == "lips": lips(P, sid, o.take, o.face_model)
        else:
            if not o.face_model: sys.exit("give --face-model face_landmarker.task")
            f, n = P.take(sid, o.take); d = mouth(f, o.face_model); jsave(f.with_suffix(".mouth.json"), d)
            print(f"{sid} take {n}: face found in {d['found']:.0%} of frames")


if __name__ == "__main__":
    main()
