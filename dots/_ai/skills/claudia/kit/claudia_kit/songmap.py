"""songmap: the song's beat map, hits and sections, the voiced phrases of the lead stem, and the LINE TABLE.

  python -m claudia_kit songmap all BOOK.json            # beats, hits, phrases and lines, then the table
  python -m claudia_kit songmap beats|hits|phrases|lines BOOK.json
  python -m claudia_kit songmap words BOOK.json [--model small]    # optional word labels (faster-whisper)
  python -m claudia_kit songmap prof BOOK.json A B [--stem lead]   # the stem's level from A to B s, 50 ms a column
  python -m claudia_kit songmap separate IN.wav OUTDIR   # optional: demucs htdemucs, vocals / everything else

The book's "audio" block names: song (the mix), lead (the lead-vocal stem), rest (everything else), and optionally
group (the group or backing voices alone) and words (a transcription [{"w", "t0", "t1"}], from any tool).
Writes beats.json, hits.json, phrases.json and lines.json into the build folder.

Why the stem's level and not the transcription: a transcriber puts the first word after a pause early, by up to 2 s.
Its words only say WHICH line is where; the lead stem's level says WHEN each line starts and ends.
"""
import argparse, importlib.util, math, re, subprocess, sys
import numpy as np
from .common import Project, jload, jsave, level_db, load_audio, ref_db
from . import lyric

QUIET, CORE, EDGE, WORD = -18.0, -8.0, -22.0, -6.0     # dB from the stem's working level: a pause, a voiced core,
                                                      # a voice's edge, a sung word


def stem_level(path):
    """(level per 10 ms, the same smoothed by a 50 ms median, the stem's working level)."""
    db = level_db(load_audio(path, 16000)); pad = np.pad(db, 2, mode='edge')
    sm = np.median(np.stack([pad[i:i + len(db)] for i in range(5)]), axis=0)
    return db, sm, ref_db(db)


def stft_mag(y, sr, N=1024, H=256):
    """magnitude spectrogram in chunks (frames x bins) and its frame rate."""
    n = 1 + (len(y) - N) // H; win = np.hanning(N).astype(np.float32); out = []
    for c in range(0, n, 2000):
        idx = np.arange(N)[None, :] + H * np.arange(c, min(n, c + 2000))[:, None]
        out.append(np.abs(np.fft.rfft(y[idx] * win, axis=1)).astype(np.float32))
    return np.vstack(out), sr / H


# ---- beats: a variable-tempo map (Suno takes speed up and slow down: never assume one BPM) ----
def beats(P, bpm_hint=None):
    src = P.audio('rest', False) or P.audio('song'); sr = 22050
    S, fr = stft_mag(load_audio(src, sr), sr); f = np.fft.rfftfreq(1024, 1 / sr)
    L = np.log1p(10 * S); flux = np.r_[0, np.maximum(0, np.diff(L, axis=0)).sum(1)]; flux -= flux.mean()
    kick = S[:, f < 150].sum(1); T = len(flux) / fr
    if not bpm_hint:                         # one tempo for the song: autocorrelation, weighted toward 120 BPM
        x = flux[:int(min(T, 90) * fr)]; lags = np.arange(int(fr * 60 / 200), int(fr * 60 / 60))
        ac = np.array([np.dot(x[:-k], x[k:]) for k in lags]); bpms = 60 * fr / lags
        bpm_hint = float(bpms[np.argmax(ac * np.exp(-0.5 * np.log2(bpms / 120) ** 2))])
    lo, hi = bpm_hint * 0.96, bpm_hint * 1.04; pts = []
    for a in np.arange(0, max(1.0, T - 20), 5.0):          # (tempo, phase) fitted in 20 s windows every 5 s
        seg = flux[int(a * fr):int((a + 20) * fr)]; best = (-1e9, 0, 0)
        for b in np.arange(lo, hi, 0.05):
            per = 60 / b; offs = np.arange(0, per, 0.004)
            idx = np.clip(((offs[:, None] + np.arange(0, 20 - per, per)[None, :]) * fr).astype(int), 0, len(seg) - 1)
            v = seg[idx].mean(1); k = int(np.argmax(v))
            if v[k] > best[0]: best = (float(v[k]), float(b), float(a + offs[k]))
        pts.append((a + 10, *best))
    tc, sc, bc, ph = (np.array(c) for c in zip(*pts)); good = sc >= np.percentile(sc, 20)   # weak windows: breakdowns
    grid = np.arange(0, T, 0.5); bm = np.interp(grid, tc[good], bc[good])
    bm = np.convolve(np.pad(bm, 10, mode='edge'), np.ones(21) / 21, mode='valid')          # a smooth tempo curve
    tempo = lambda t: float(np.interp(t, grid, bm)); thr = 0.15 * np.percentile(flux, 99.5)

    def snap(t):                            # onto a real onset within 30 ms
        i0, i1 = max(0, int((t - .03) * fr)), int((t + .03) * fr) + 1; w = flux[i0:i1]
        return (i0 + int(np.argmax(w))) / fr if len(w) and w.max() > thr else t
    t0 = ph[int(np.argmax(sc))]; out = [t0]
    while out[0] - 60 / tempo(out[0]) > 0.05: out.insert(0, snap(out[0] - 60 / tempo(out[0])))
    while out[-1] + 60 / tempo(out[-1]) < T - 0.2: out.append(snap(out[-1] + 60 / tempo(out[-1])))
    kv = kick[np.clip((np.array(out) * fr).astype(int), 0, len(kick) - 1)]
    bt = np.array(out) + 512 / sr                     # frame i of the spectrogram is centred i/fr + half a window in
    votes = [int(np.argmax([kv[p + b:b + 32:4].sum() for p in range(4)])) for b in range(0, len(bt), 32)]
    phase = P.book.get('downbeat_phase', max(set(votes), key=votes.count))      # the kick's strongest phase
    res = dict(bpm=round(bpm_hint, 2), tempo_start=round(float(bm[2]), 2), tempo_end=round(float(bm[-3]), 2), phase=phase,
               beats=[round(float(b), 3) for b in bt], downbeats=[round(float(b), 3) for b in bt[phase::4]])
    jsave(P.build / 'beats.json', res)
    print(f"beats: {len(bt)} beats, {len(res['downbeats'])} bars, tempo {res['tempo_start']} -> {res['tempo_end']} BPM "
          f"(global {res['bpm']}), downbeat phase {phase}")
    return res


# ---- hits and sections: where the arrangement jumps, snapped to the bar ----
def env(path, sr=16000):
    e = np.sqrt(np.maximum(1e-12, 10 ** (level_db(load_audio(path, sr)) / 10)))
    return e / (np.percentile(e, 99.5) + 1e-9)


def hits(P):
    bj = jload(P.build / 'beats.json'); bt, db = np.array(bj['beats']), np.array(bj['downbeats'])
    E = [env(P.audio('song'))] + ([0.9 * env(P.audio('rest'))] if P.audio('rest', False) else [])
    n = min(len(e) for e in E); cs = [np.r_[0, np.cumsum(e[:n], dtype=np.float64)] for e in E]
    mean = lambda c, a, b: (c[min(n, b)] - c[max(0, a)]) / max(1, min(n, b) - max(0, a))
    sc = np.array([max(mean(c, i, i + 60) - mean(c, i - 150, i - 2) for c in cs) for i in range(n)])   # next 0.6 s over last 1.5 s
    raw = []
    for i in range(n):
        if sc[i] < 0.22 or sc[i] < sc[max(0, i - 50):i + 51].max(): continue
        t = i / 100; j = int(np.argmin(abs(db - t)))
        raw.append([float(db[j]) if abs(db[j] - t) <= 0.65 else float(bt[int(np.argmin(abs(bt - t)))]), float(sc[i])])
    imp = []
    for t, s in sorted(raw):                                     # one hit per 2 s, the strongest
        if imp and t - imp[-1][0] < 2.0:
            if s > imp[-1][1]: imp[-1] = [t, s]
        else: imp.append([t, s])
    _, lsm, lref = stem_level(P.audio('lead')); voiced = lsm >= lref + QUIET
    edges = [0.0] + [t for t, s in imp if t > 1] + [n / 100]; secs = []
    for a, b in zip(edges, edges[1:]):
        secs.append(dict(t0=round(a, 2), t1=round(b, 2), voice=round(float(voiced[int(a * 100):int(b * 100)].mean()), 2),
                         level=round(float(20 * np.log10(np.mean(E[0][int(a * 100):int(b * 100)]) + 1e-6)), 1)))
    res = dict(hits=[dict(t=round(t, 3), s=round(min(1.0, s / 0.45), 2)) for t, s in imp], sections=secs)
    jsave(P.build / 'hits.json', res)
    print(f"hits: {len(imp)} — " + ' '.join(f"{h['t']:.2f}:{h['s']:.2f}" for h in res['hits']))
    for s in secs: print(f"  section {s['t0']:7.2f}-{s['t1']:7.2f}  level {s['level']:6.1f} dB  voice {100 * s['voice']:3.0f}%")
    return res


# ---- the voiced phrases of the lead stem ----
def phrases(P):
    db, sm, ref = stem_level(P.audio('lead')); W = words_of(P); act = db > ref + CORE; n = len(db); out = []; i = 0
    while i < n:
        if not act[i]: i += 1; continue
        j = i
        while j < n and (act[j] or act[j:j + 15].any()): j += 1          # gaps under 0.15 s are joined
        if j - i >= 6:
            a, b = i, j                                                      # walk out to the voice's edges (breath, consonant)
            while a > 0 and db[a - 1] > ref + EDGE and i - a < 25: a -= 1
            while b < n - 1 and db[b] > ref + EDGE and b - j < 25: b += 1
            out.append(dict(t0=a / 100, t1=b / 100, peak=round(float(db[i:j].max()), 1),
                            words=' '.join(w['w'] for w in W if a / 100 - .25 <= (w['t0'] + w['t1']) / 2 <= b / 100 + .25)))
        i = j
    jsave(P.build / 'phrases.json', dict(ref_db=round(ref, 1), phrases=out))
    print(f"phrases: {len(out)} voiced phrases in the lead stem (working level {ref:.1f} dB)")
    return out


# ---- the line table ----
def words_of(P):
    f = P.audio('words', False) or (P.build / 'words.json' if (P.build / 'words.json').exists() else None)
    if not f: return []
    d = jload(f); return d['words'] if isinstance(d, dict) else d


def entries(P):
    """the lyric as sung, in order: each line split into its lead part and its (group) parts; ids L01, L02, ..."""
    out = []
    for sec, mode, lines in lyric.parse(P.p(P.book['lyric']).read_text()):
        for ln in lines:
            for g, lead in re.findall(r'\(([^)]*)\)|([^()]+)', ln):
                text = (g or lead).strip(' ,')
                if re.search(r'[A-Za-z0-9]', text):
                    out.append(dict(id=None, who='group' if g else 'lead', section=re.split(r'\s+-\s+', sec)[0], text=text,
                                    syl=len(lyric.analyse(text)[0])))
    for k, e in enumerate(out, 1): e['id'] = f"L{k:0{max(2, len(str(len(out))))}d}"
    return out


def norm(w):
    w = re.sub(r"[^a-z0-9']", '', w.lower().replace('’', "'")).strip("'")
    return lyric.num_words(w).split()[-1] if w.isdigit() else w


def match(lines, toks):
    """each line's first and last word in the transcription, in order, tolerant of misheard and missing words."""
    out, p = {}, 0
    for L in lines:
        lt = [x for x in (norm(w) for w in L['text'].split()) if x]; best = None
        for s in range(p, min(p + 30, len(toks))):
            j, hit = s, []
            for t in lt:
                k = next((q for q in range(j, min(j + 3, len(toks))) if toks[q] == t or (len(t) > 3 and toks[q][:4] == t[:4])), None)
                if k is not None: hit.append(k); j = k + 1
            if hit and (best is None or len(hit) - 0.15 * (s - p) > best[0]): best = (len(hit) - 0.15 * (s - p), hit)
        out[L['id']] = (best[1][0], best[1][-1], len(best[1]), len(lt)) if best and len(best[1]) >= max(1, len(lt) // 2) else None
        if out[L['id']]: p = best[1][-1] + 1
    return out


def rise_after(sm, k, quiet, n_ok=10, end=None):
    """the first moment after frame k (and before frame `end`) where the voice holds above the quiet line for 0.1 s."""
    for i in range(k, min(end or len(sm), len(sm) - n_ok)):
        if (sm[i:i + n_ok] >= quiet).all(): return i / 100
    return None


def line_end(sm, t_from, t_lim, quiet):
    """the end of a line: from its last frame at word level (10 dB under the line's peak, so a breath before the next
    line is left out) between t_from (its last word) and t_lim (the boundary), on to the first 0.12 s of quiet."""
    a, b = int(t_from * 100), min(int(t_lim * 100), len(sm) - 1)
    if b <= a: return t_lim
    seg = sm[a:b]; loud = np.nonzero(seg >= max(quiet + 4, seg.max() - 10))[0]; i = a + (loud[-1] if len(loud) else 0)
    while i < b and not (sm[i:i + 12] < quiet).all(): i += 1
    return i / 100


def times_from_words(lead, W, sm, quiet):
    """the boundary between two lines is the dip of the level between them: a real pause (below the quiet line) ends
    one line where the voice falls into it and starts the next where it rises out of it; with no pause (legato), both
    are the dip nearest the transcription's own boundary (the deepest dip in a wide search was wrong twice)."""
    mt = match(lead, [norm(w['w']) for w in W]); res, prev, n = {}, None, len(sm)
    for L in lead:
        m = mt[L['id']]
        if not m: continue
        s, e, got, tot = m; r = dict(w_t0=W[s]['t0'], w_t1=W[e]['t1'], got=got, n=tot, words_t=W[s:e + 1])
        lo = W[mt[prev][1]]['t0'] + 0.10 if prev else 0.0; hi = max(W[s]['t1'] - 0.05, lo + 0.1)
        a, b = int(lo * 100), min(n - 1, int(hi * 100)); k = a + int(np.argmin(sm[a:b + 1])); dip = float(sm[k])
        if prev and dip >= quiet:
            wb = (W[mt[prev][1]]['t1'] + W[s]['t0']) / 2; a, b = max(0, int((wb - .25) * 100)), min(n - 1, int((wb + .25) * 100))
            k = a + int(np.argmin(sm[a:b + 1])); dip = float(sm[k])
        on = rise_after(sm, k, quiet) if dip < quiet else None
        r.update(t0=round(on if on is not None else k / 100, 2), dip=round(dip, 1), gap_to_prev=None)
        if prev:
            res[prev]['t1'] = round(line_end(sm, W[mt[prev][1]]['t0'], k / 100, quiet) if dip < quiet else k / 100, 2)
            r['gap_to_prev'] = round(r['t0'] - res[prev]['t1'], 2)
        res[L['id']] = r; prev = L['id']
    if prev: res[prev]['t1'] = round(line_end(sm, W[mt[prev][1]]['t0'], min(n / 100 - 0.2, W[mt[prev][1]]['t1'] + 3), quiet), 2)
    return res


def times_from_level(lead, sm, quiet):
    """no transcription: the voiced pieces (split at pauses of 0.12 s or more, and at deep dips inside long phrases)
    are dealt out to the lines in order by dynamic programming: each line takes the run of pieces whose voiced length
    best fits its syllables, a gap inside a line costs by its length, and quiet pieces (bleed, breaths) are cheap to
    leave out. A first guess only: check it with `prof` and correct it with line_fixes."""
    v = sm >= quiet; n = len(sm); pcs, i = [], 0
    while i < n:
        if not v[i]: i += 1; continue
        j = i
        while j < n and (v[j] or v[j:j + 12].any()): j += 1
        while j > i and not v[j - 1]: j -= 1
        if j - i >= 8:
            cuts = [i]
            for q in range(i + 25, j - 25):          # a deep dip inside a long phrase may be a boundary between two lines
                if sm[q] == sm[q - 15:q + 16].min() and sm[q] < min(sm[q - 40:q].max(), sm[q:q + 40].max()) - 8 and q - cuts[-1] >= 25:
                    cuts.append(q)
            pcs += [(a / 100, b / 100, float(sm[a:b].max())) for a, b in zip(cuts, cuts[1:] + [j])]
        i = j
    if not pcs: return {}
    word = max(p[2] for p in pcs) - 10; syl = [L['syl'] for L in lead]; K, N = len(pcs), len(lead)
    rate = sum(syl) / sum(b - a for a, b, pk in pcs if pk >= word); skip = [(0.2 + 3 * (b - a)) * (1 if pk >= word else 0.2) for a, b, pk in pcs]
    D = np.full((N + 1, K + 1), np.inf); B = {}; D[0, 0] = 0
    for i_ in range(N + 1):
        for k in range(K + 1):
            if not np.isfinite(D[i_, k]): continue
            if k < K and D[i_, k] + skip[k] < D[i_, k + 1]: D[i_, k + 1] = D[i_, k] + skip[k]; B[(i_, k + 1)] = (i_, k)
            for j in range(k + 1, K + 1) if i_ < N else ():
                if pcs[j - 1][1] - pcs[k][0] > 15: break
                voiced = sum(pcs[q][1] - pcs[q][0] for q in range(k, j)); gaps = pcs[j - 1][1] - pcs[k][0] - voiced
                c = D[i_, k] + 2 * math.log(voiced * rate / syl[i_]) ** 2 + 1.5 * gaps
                if c < D[i_ + 1, j]: D[i_ + 1, j] = c; B[(i_ + 1, j)] = (i_, k)
    res, st = {}, (N, K)
    if not np.isfinite(D[N, K]): return res
    while st != (0, 0):
        pr = B[st]
        if pr[0] < st[0]: res[lead[pr[0]]['id']] = dict(t0=pcs[pr[1]][0], t1=pcs[st[1] - 1][1], dip=None, gap_to_prev=None)
        st = pr
    return res


def pauses(sm, t0, t1, quiet, min_s=0.25):
    """silences inside a line (the take should keep them; a full stop there is right)."""
    out, i, a, b = [], None, int(t0 * 100) + 5, int(t1 * 100) - 5
    for q in range(a, b + 1):
        if q < b and sm[q] < quiet: i = q if i is None else i
        elif i is not None:
            if q - i >= min_s * 100: out.append([round(i / 100, 2), round(q / 100, 2)])
            i = None
    return out


def lines(P):
    ents = entries(P); lead = [e for e in ents if e['who'] == 'lead']; W = words_of(P)
    _, sm, ref = stem_level(P.audio('lead')); quiet = ref + QUIET
    res = times_from_words(lead, W, sm, quiet) if W else times_from_level(lead, sm, quiet)
    g = P.audio('group', False); gsm = gq = None
    if g: _, gsm, gref = stem_level(g); gq = gref + QUIET
    fixes = P.book.get('line_fixes', {})
    for e in ents: e.update(res.get(e['id'], {}))
    for k, e in enumerate(ents):
        if e['who'] == 'group' and gsm is not None:   # the group's voices, looked for from the middle of the lead line before
            pl = next((x for x in reversed(ents[:k]) if x['who'] == 'lead' and x.get('t1')), None)     # to the middle of the next
            nl = next((x for x in ents[k + 1:] if x['who'] == 'lead' and x.get('t0')), None)
            a = int((pl['t0'] + pl['t1']) * 50) if pl else 0; b = min(len(gsm) - 26, int((nl['t0'] + nl['t1']) * 50) if nl else len(gsm))
            on = rise_after(gsm, a, gq, end=b)
            if on is not None:        # it runs to its first 0.25 s of quiet, and ends where it falls 12 dB under its peak
                i = j = int(round(on * 100))
                while j < b and not (gsm[j:j + 25] < gq).all(): j += 1
                loud = np.nonzero(gsm[i:j] >= max(gq, gsm[i:j].max() - 12))[0]
                e['t0'], e['t1'] = i / 100, (i + loud[-1] + 1) / 100 if len(loud) else j / 100
    for k, e in enumerate(ents):      # a group bleeds into the lead stem: in call and answer, her line starts after the
        if gsm is None or e['who'] != 'lead' or e.get('t0') is None: continue           # call and ends where the next starts
        pg = ents[k - 1] if k and ents[k - 1]['who'] == 'group' and ents[k - 1].get('t1') else None
        ng = ents[k + 1] if k + 1 < len(ents) and ents[k + 1]['who'] == 'group' and ents[k + 1].get('t0') else None
        if pg and e['t0'] < pg['t1'] - 0.1:          # her first frame at word level after the call, and its onset (<= 80 ms back)
            loud = np.nonzero(sm[int((pg['t1'] - 0.3) * 100):] >= ref + WORD)[0]
            if len(loud):
                i = int((pg['t1'] - 0.3) * 100) + loud[0]; j = i
                while j > i - 8 and sm[j - 1] >= quiet: j -= 1
                e['t0'] = j / 100; e['note'] = 'starts after the group line before it'
        if ng and e['t1'] > ng['t0'] + 0.1:
            e['t1'] = ng['t0']; e['note'] = (e.get('note', '') + '; ' if e.get('note') else '') + 'ends where the group line after it starts'
    for e in ents:
        f = fixes.get(e['id'])
        if f: e['t0'] = f[0] if f[0] is not None else e.get('t0'); e['t1'] = f[1] if f[1] is not None else e.get('t1'); e['fixed'] = True
        if e.get('t0') is not None and e.get('t1') is not None:
            e['pauses'] = pauses(gsm if e['who'] == 'group' and gsm is not None else sm, e['t0'], e['t1'],
                                 gq if e['who'] == 'group' and gq is not None else quiet)
    out = [dict(id=e['id'], who=e['who'], section=e['section'], words=e['text'], t0=e.get('t0'), t1=e.get('t1'),
                **{k: e[k] for k in ('pauses', 'w_t0', 'w_t1', 'got', 'n', 'dip', 'gap_to_prev', 'fixed', 'note', 'words_t') if k in e})
           for e in ents]
    jsave(P.build / 'lines.json', dict(lead=str(P.audio('lead').name), quiet_db=round(quiet, 1), transcription=bool(W), lines=out))
    print(f"lines: {sum(x['t0'] is not None for x in out)} of {len(out)} timed "
          f"({'from the stem with transcription labels' if W else 'from the stem alone: no transcription, check by ear'})")
    for x in out:
        t = f"{x['t0']:7.2f}-{x['t1']:7.2f} ({x['t1'] - x['t0']:4.2f})" if x['t0'] is not None and x['t1'] is not None else '   (not set: give audio.group or a line_fix)'
        w = f"  tr {x['w_t0']:7.2f}-{x['w_t1']:7.2f} {x['got']}/{x['n']}" if 'w_t0' in x else ''
        flag = ('  << transcription %+.2f s off the stem' % (x['w_t0'] - x['t0']) if 'w_t0' in x and abs(x['w_t0'] - x['t0']) > 0.35 else '') + \
               ('  << few words found' if 'got' in x and x['got'] < 0.7 * x['n'] else '') + ('  (fixed)' if x.get('fixed') else '') + \
               (f"  pauses {x['pauses']}" if x.get('pauses') else '') + (f"  << {x['note']}" if x.get('note') else '')
        print(f"{x['id']} {x['who']:5s} {t}{w}  dip {x.get('dip') if x.get('dip') is not None else '-':>6}  {x['words'][:48]}{flag}")
    return out


def _pcm16k(path):
    """the stem as 16 kHz mono float32, decoded by ffmpeg: newer PyAV releases broke faster-whisper's own file decoder."""
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def words(P, model='small'):
    """word labels with times from faster-whisper on the lead stem (optional; any transcriber's output will do)."""
    if not importlib.util.find_spec('faster_whisper'): sys.exit("songmap words needs faster-whisper: pip install faster-whisper")
    from faster_whisper import WhisperModel
    prompt = ' '.join(l for _, _, ls in lyric.parse(P.p(P.book['lyric']).read_text()) for l in ls)[:800]
    segs, _ = WhisperModel(model, device='auto', compute_type='default').transcribe(
        _pcm16k(P.audio('lead')), word_timestamps=True, language=P.book.get('language', 'en'), initial_prompt=prompt)
    W = [dict(w=w.word.strip(), t0=round(w.start, 2), t1=round(w.end, 2), p=round(w.probability, 3)) for s in segs for w in s.words]
    jsave(P.build / 'words.json', dict(words=W)); print(f"words: {len(W)} -> {P.build / 'words.json'}")


def prof(P, a, b, stem='lead'):
    db, _, ref = stem_level(P.audio(stem))
    print(f"{stem} stem, working level {ref:.1f} dB, quiet line {ref + QUIET:.1f} dB; each column = the loudest 10 ms in 50 ms")
    for i in range(int(a * 100), int(b * 100), 100):
        print('%7.2f: ' % (i / 100) + ' '.join('%3d' % max(-99, round(db[j:j + 5].max())) for j in range(i, min(i + 100, int(b * 100), len(db) - 4), 5)))


def separate(src, out):
    if not importlib.util.find_spec('demucs'): sys.exit('separate needs demucs: pip install demucs')
    subprocess.run([sys.executable, '-m', 'demucs', '-n', 'htdemucs', '--two-stems', 'vocals', '-o', out, src], check=True)
    print(f"wrote {out}/htdemucs/<name>/vocals.wav and no_vocals.wav")


def main(argv=None):
    ap = argparse.ArgumentParser(prog='claudia_kit songmap', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['all', 'beats', 'hits', 'phrases', 'lines', 'words', 'prof', 'separate'])
    ap.add_argument('book'); ap.add_argument('rest', nargs='*'); ap.add_argument('--stem', default='lead')
    ap.add_argument('--bpm', type=float, help='a tempo hint for the beat map'); ap.add_argument('--model', default='small')
    o = ap.parse_args(argv)
    if o.cmd == 'separate': return separate(o.book, o.rest[0] if o.rest else 'stems')
    P = Project(o.book)
    if o.cmd == 'prof': return prof(P, float(o.rest[0]), float(o.rest[1]), o.stem)
    if o.cmd == 'words': return words(P, o.model)
    if o.cmd in ('all', 'beats'): beats(P, o.bpm or P.book.get('bpm'))
    if o.cmd in ('all', 'hits'): hits(P)
    if o.cmd in ('all', 'phrases'): phrases(P)
    if o.cmd in ('all', 'lines'): lines(P)


if __name__ == '__main__':
    main()
