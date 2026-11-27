"""shotbook: from the shot book and the line table to what you pay for: each shot's window, its gated vocal, its
prompt and a provider-neutral job file. Then lint all of it before anything is submitted.

  python -m claudia_kit shotbook build BOOK.json [IDS]    # build/jobs/<id>.json + build/windows/<id>.wav, and a check
  python -m claudia_kit shotbook show BOOK.json ID        # print one prompt
  python -m claudia_kit shotbook lint BOOK.json [IDS]     # exit code 1 on any error
  python -m claudia_kit shotbook board BOOK.json OUT.jpg  # contact sheet of first frames (needs Pillow)

A shot names lines, never times: a new take of the song re-times the whole book. Kinds:
  sung    her on screen singing her lines: @Image1 the first frame, @Image2 her sheet, @Audio1 the gated lead stem
  silent  her on screen, no voice: a timeline of events you write in whole seconds
  noface  no face (paper sets, objects, puppets): image-to-video from a first frame and an optional last frame
The window opens `lead_in` (0.7 s) before her first word, in silence, and runs whole seconds (4-15). The vocal is the
lead stem gated to the shot's own lines (20 ms fades); a take hears only what its timeline names.

What the prompts do and do not say (measured on earlier films): the model takes every word literally, so define only
what matters (the words, their seconds, the key action) and let the reference images carry her identity; no standing
posture rules in a performance (they make her read frozen): write movement into each second instead; one mood word,
warm by default; and a full stop between words she sings straight through becomes a pause in the take, so those are
written with commas.

The book's "video_model" picks the form. Seedance 2.5 (the default) gets the structured form above, with her sheet and
the vocal as inputs. Any other model (e.g. "grok-imagine-video-1.5") is taken to read a first frame and nothing else: it
gets a short plain-prose prompt (what she does in each whole second, the words she sings in quotes, the camera in one
line, her look as in the first frame), no reference sheet and no audio. Its window still sets the take's length and
where it sits on the song, but no sound is sent, so its takes are placed by her lips (sync).
"""
import argparse, math, re, sys, textwrap
import numpy as np
from .common import Project, jload, jsave, level_db, load_audio, ref_db, write_wav

POLICY = ("The soundtrack is @Audio1 itself, copied sample for sample with the same timing, pitch and level; do not re-sing or "
          "re-generate it, and add no music, other voices or sound effects.")
NOFACE_KEEP = ("Keep the colours, light and materials of the first frame for the whole video; pieces move like real objects and "
               "never melt or morph. No people and no faces appear. No subtitles, captions, watermarks or new lettering appear.")
MOOD = r"\b(dry|deadpan|knowing(ly)?|smirk\w*|menac\w*|rueful\w*|sly|wry|sardonic\w*|ironic\w*|mock\w*|sarcas\w*|smug\w*|cynic\w*|sinister|icy|haughty|sneer\w*)\b"
FROZEN = [r"head (stays |is )?(perfectly )?upright", r"no head tilt", r"straight neck", r"chin level", r"shoulders level",
          r"faces the camera with her whole body", r"(stays|keeps|holds) (perfectly |completely )?still", r"does not move", r"motionless"]
MOVES = (r"\b(turn|nod|tilt|step|lean|shift|sway|gestur|point|lift|rais|lower|open|reach|shrug|look|glanc|smil|laugh|wave|walk|"
         r"touch|tap|hold|lay|press|spin|bow|clap|count|cup|tip|bounc|rock|danc|swing|sweep|tug|pull|push|tighten|grip|breath|"
         r"blink|wink|brush|fold|clasp|squeez|adjust|settl|bob|flick|toss|roll|pat|stretch|kneel|sit|stand|rise|bend|jump|run|"
         r"move|hand|shoulder|head|arm|finger)")
LOOKAWAY = r"(eyes (lift|go|roll)\w* (up|above)|over her shoulder|turns (her head )?(right )?round|looks back at)"
BRANDS = ("Nike Adidas Apple iPhone Coca-Cola Pepsi Disney Marvel Gucci Chanel Prada Rolex Tesla Google Microsoft Amazon Netflix "
          "Spotify McDonald's Starbucks Lego Barbie Pokemon Nintendo PlayStation Xbox Ferrari Porsche BMW Mercedes Supreme").split()
PULLBACK = (r"\bpull(s|ing|ed)?[ -]?(back|out|away)\b|\bdoll(y|ies|ying)[ -]?(out|back)\b|\bzoom(s|ing)?[ -]?out\b|\bup and back\b|"
            r"\b(track|draw|move|ease)s?(ing)? back\b|\bwiden(s|ing)?\b|\breveal(s|ing)? the (whole|wider)\b")


def name(P): return P.book.get("character", "Claudia")


def video_model(P): return P.book.get("video_model") or "seedance-2.5"


def first_frame_only(model):
    """the kit's reference form (sheet and vocal as inputs, @Image/@Audio) is Seedance's; any other model gets the first-frame form."""
    return "seedance" not in model.lower()


def shot_lines(P, s):
    """the lines a sung shot's timeline names, in order: [(line, action)]"""
    out = []
    for key, act in s.get("timeline", []):
        if key == "rest": continue
        if key not in P.lines: sys.exit(f"{s['id']}: line {key} is not in the line table (run songmap lines)")
        L = P.lines[key]
        if L.get("t0") is None or L.get("t1") is None: sys.exit(f"{s['id']}: line {key} has no times (set a line_fix)")
        out.append((L, act))
    return out


def sung_through(L, next_gap):
    """the words as the prompt quotes them: a stop inside the line where the stem does not pause becomes a comma (placed
    by syllables along the line, matched to its measured pauses), and so does the stop at its end when the next line
    follows within 0.25 s. A full stop in the quoted words makes the take pause."""
    from .lyric import analyse
    text = L["words"].strip(); toks = text.split(); syl = [len(analyse(t)[0]) for t in toks]; tot = max(1, sum(syl))
    dur, free, out = L["t1"] - L["t0"], [((a + b) / 2) for a, b in L.get("pauses", [])], []
    for i, tok in enumerate(toks):
        if re.search(r"[.!;:]$", tok):
            last = i == len(toks) - 1; te = L["t0"] + dur * sum(syl[:i + 1]) / tot
            near = [p for p in free if abs(p - te) < 0.8]
            if (last and next_gap is not None and next_gap < 0.25) or (not last and not near): tok = tok[:-1] + ","
            elif near: free.remove(min(near, key=lambda p: abs(p - te)))
        out.append(tok)
    return " ".join(out)


def wordless_w0(P, s):
    """a silent or no-face shot starts at its "w0", or `lead_in` before the line it is "at" (it names a line, not a time)."""
    if "at" in s: return round(P.lines[s["at"]]["t0"] - s.get("lead_in", P.book.get("defaults", {}).get("lead_in", 0.7)), 2)
    return s.get("w0", s["show"][0] - 0.1 if s.get("show") else None)


def auto_start(P, s, beats):
    """where the cut enters a shot the book gives no show for: the last beat before her first word (never inside the
    take's first 0.1 s); a shot without words enters 0.1 s into its take."""
    if s.get("show"): return s["show"][0]
    if s.get("kind", "sung") != "sung": w = wordless_w0(P, s); return None if w is None else w + 0.1
    if not shot_lines(P, s): sys.exit(f"{s['id']}: a sung shot needs at least one line in its timeline")
    first = shot_lines(P, s)[0][0]; w0 = s.get("w0", round(first["t0"] - s.get("lead_in", P.book.get("defaults", {}).get("lead_in", 0.7)), 2))
    bt = [b for b in (beats or []) if w0 + 0.1 <= b <= first["t0"] - 0.1]
    return max(bt[-1] if bt else first["t0"] - 0.3, w0 + 0.1)


def window(P, s, beats=None):
    """w0, D, show and the timeline items [(kind, a, b, words, action, line id)] in window seconds. Without a "show",
    a shot runs on to where the next shot starts (so the cut tiles), if that is close."""
    d = P.book.get("defaults", {}); kind = s.get("kind", "sung")
    if kind != "sung" and (wordless_w0(P, s) is None or not s.get("duration")):
        sys.exit(f"{s['id']}: a {kind} shot needs a duration, and w0, at (a line) or show")
    me = auto_start(P, s, beats)
    nxt = min([t for t in (auto_start(P, x, beats) for x in P.shots if x is not s) if t is not None and t > me + 0.5], default=None)
    if kind != "sung":
        show = s.get("show"); w0 = wordless_w0(P, s)
        end = w0 + s["duration"] - 0.05       # on to the next shot when it starts within 0.1 s of the take's end
        return w0, int(s["duration"]), show or [round(me, 2), round(nxt if nxt and nxt <= end + 0.15 else end, 2)], []
    sl = shot_lines(P, s); first, last = sl[0][0], sl[-1][0]
    w0 = s.get("w0", round(first["t0"] - s.get("lead_in", d.get("lead_in", 0.7)), 2))
    show = list(s.get("show") or [me, nxt if nxt and nxt <= last["t1"] + 2.5 else last["t1"] + 0.6])
    show[0] = max(show[0], w0 + 0.1)
    D = int(s.get("duration") or max(4, math.ceil(max(last["t1"] - w0 + 0.9, show[1] - w0 + 0.05) - 1e-6)))
    show[1] = min(show[1], w0 + D - 0.05)
    parts, items = s["timeline"], []
    for n, (key, act) in enumerate(parts):
        if key != "rest":
            L = P.lines[key]; follow = parts[n + 1][0] if n + 1 < len(parts) and parts[n + 1][0] != "rest" else None
            gap = P.lines[follow]["t0"] - L["t1"] if follow else None    # the next line follows straight on
            words = L["words"] if s.get("punctuation") == "as written" else sung_through(L, gap)
            items.append((L["who"], L["t0"] - w0, L["t1"] - w0, words, act, key)); continue
        prev = next((P.lines[p[0]] for p in reversed(parts[:n]) if p[0] != "rest"), None)
        later = next((P.lines[p[0]] for p in parts[n + 1:] if p[0] != "rest"), None)
        items.append(("rest", prev["t1"] - w0 if prev else 0.0, later["t0"] - w0 - 0.05 if later else D, None, act, None))
    return w0, D, [round(show[0], 2), round(show[1], 2)], items


def segments(items, D):
    """the whole-second timeline: a boundary is a whole second inside the gap between two items when there is one (so
    every segment holds the words really sung in it), else the nearest second. A rest shorter than 0.9 s in the middle
    folds into the line after it; a closing rest with no second left folds into the line before it."""
    raw = [[k, a, min(b, D), w, act, lid] for k, a, b, w, act, lid in items if a < D]; folded, pre = [], None
    for n, (k, a, b, w, act, lid) in enumerate(raw):
        if k == "rest" and 0 < n < len(raw) - 1 and b - a < 0.9: pre = (a, act); continue
        if pre: a, act, pre = pre[0], f"first {pre[1]}; then {act}", None
        folded.append([k, a, b, w, act, lid])
    out, t = [], 0
    for n, (k, a, b, w, act, lid) in enumerate(folded):
        if t >= D:
            if out and k == "rest": out[-1] = out[-1][:4] + (out[-1][4] + "; then " + act, out[-1][5])
            continue
        if n == len(folded) - 1: end = D
        elif n == 0 and k == "rest": end = max(1, math.floor(folded[1][1] + 1e-6))
        else:
            lo, hi = b, folded[n + 1][1]; mid = (lo + hi) / 2; nk = folded[n + 1][0]
            ints = list(range(math.ceil(lo - 1e-6), math.floor(hi + 1e-6) + 1))
            end = (min(ints, key=lambda x: abs(x - mid)) if ints else math.ceil(b - 0.05) if k != "rest" and nk == "rest"
                   else math.floor(hi + 0.05) if k == "rest" and nk != "rest" else round(mid))
            end = max(t + 1, min(end, D))
        out.append((t, end, k, w, act, lid)); t = end
    return out


def gated(P, s, w0, D, sr=48000):
    """the window's audio: the lead stem from the shot's first lead line to its last, the group stem over its group
    lines, never into a neighbouring line, with 20 ms fades; exactly D seconds of 48 kHz stereo."""
    sl = [L for L, _ in shot_lines(P, s)]; others = [x for x in P.lines.values() if x.get("t0") is not None and x not in sl]
    y = np.zeros((D * sr, 2), np.float32); spans = []
    for who, key in (("lead", "lead"), ("group", "group")):
        mine = [L for L in sl if L["who"] == who]
        if not mine: continue
        if who == "group" and not P.audio("group", False): sys.exit(f"{s['id']}: a group line needs audio.group")
        a, b = mine[0]["t0"], mine[-1]["t1"]
        before = max((x["t1"] for x in others if x["t1"] <= a + 0.02), default=-9)
        after = min((x["t0"] for x in others if x["t0"] >= b - 0.15), default=1e9)
        a, b = max(w0, a - min(0.07, max(0.03, a - before - 0.01))), min(w0 + D, b + min(0.25, max(0.03, after - b - 0.02)))
        x = load_audio(P.audio(key), sr, 2, w0, D); x = np.vstack([x, np.zeros((max(0, D * sr - len(x)), 2), np.float32)])[:D * sr]
        g = np.zeros(D * sr, np.float32); i0, i1, r = int((a - w0) * sr), int((b - w0) * sr), int(0.02 * sr); g[i0:i1] = 1
        g[i0:i0 + r] *= 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, r)); g[i1 - r:i1] *= 0.5 + 0.5 * np.cos(np.linspace(0, np.pi, r))
        y += x * g[:, None]; spans.append((who, round(a, 3), round(b, 3)))
    return y, spans


def prompt(P, s, segs, D):
    nm, kind = name(P), s.get("kind", "sung"); look = (P.book.get("looks") or {}).get(s.get("look"), s.get("look", ""))
    who = (P.book.get("subject", nm) + (", " + look if look else "")).rstrip(".")
    sheet = (f"@Image2 is {nm}'s character reference sheet: use it for her face, her hair and her skin. It is never shown as a "
             "shot; its layout, its plain background and its several views are not used.")
    if kind == "noface":
        return "\n\n".join(x for x in [
            f"【Generation Goal】 {s['goal']}",
            f"【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the scene: "
            f"{s.get('first', s.get('place', ''))}; its colours, its light and the camera's starting view.",
            "【Last Frame】 The video ends exactly on the provided last-frame image: by the final second everything has arrived "
            "at the state shown there." if s.get("last_frame") else "",
            "【Event Script】\n" + "\n".join(s["events"]), f"【Camera】 {s['camera']}",
            f"【Maintain Consistency】 {NOFACE_KEEP} {s.get('keep', '')}".rstrip()] if x)
    roles = ["Use @Image1 as the first frame.", f"This first frame defines {nm}'s clothes, the set ({s.get('place', 'as shown')}), "
             "the light and the camera's starting view.", sheet]
    if s.get("last_frame"):
        roles += ["Use @Image3 as the last frame.", f"This last frame defines where the shot arrives: {s.get('last', 'the view it shows')}."]
    req = [f"Keep {nm}'s face, hair and clothes as in @Image1 and @Image2 throughout; the set, its colours and the light stay as in @Image1.",
           "Natural anatomy: hands with five fingers, no extra or fused fingers, no distorted limbs.",
           "No on-screen text, captions or subtitles appear."]
    manner = s.get("manner", P.book.get("manner", "warm and open: she enjoys singing to us"))
    if kind == "silent":
        return "\n\n".join([f"【Generation Goal】 {s['goal']} Her manner is {manner}.", "【Reference Asset Roles】\n" + "\n".join(roles),
                            f"【Subject】 {who}. Only one {nm} appears.", f"【World】 {P.book.get('world', '')}",
                            "【Performance Timeline】\n" + "\n".join(s["events"]), f"【Camera】 {s['camera']}",
                            "【Core Requirements】\n" + "\n".join(f"{i}. {r}" for i, r in enumerate(
                                ["Nobody sings or speaks: her lips stay closed (a smile is fine)."] + req, 1))])
    roles.append(f"@Audio1 is {nm}'s own voice and the complete soundtrack of this video. Her mouth follows @Audio1.")
    T = []
    for a, b, k, w, act, _ in segs:
        if k == "lead": T.append(f'{a}-{b}s: in @Audio1 she sings "{w}"; her lips form each of those words when it sounds in @Audio1; {act}.')
        elif k == "group": T.append(f'{a}-{b}s: in @Audio1 a group of voices, not {nm}, sings "{w}"; her mouth stays closed while they sing; {act}.')
        else: T.append(f"{a}-{b}s: @Audio1 is silent; her mouth is closed; {act}.")
    req = [f"Lip sync word by word to @Audio1: mouth shapes match every syllable of @Audio1, its start and its end; her mouth rests "
           "closed while @Audio1 is silent."] + req
    if any(x[2] == "group" for x in segs): req.append("The group's voices in @Audio1 are never hers: while they sing, her lips stay closed.")
    return "\n\n".join([f"【Audio Policy】 {POLICY}", f"【Generation Goal】 @Image1 sings @Audio1: {s['goal']} Her manner is {manner}.",
                        "【Reference Asset Roles】\n" + "\n".join(roles), f"【Subject】 {who}. Only one {nm} appears.",
                        f"【World】 {P.book.get('world', '')}",
                        "【Performance Timeline】 What @Audio1 contains, and what happens at that moment:\n" + "\n".join(T),
                        f"【Camera】 {s['camera']}", "【Core Requirements】\n" + "\n".join(f"{i}. {r}" for i, r in enumerate(req, 1))])


def prompt_ff(P, s, segs, D):
    """the form for a video model that reads a first frame and nothing else (it cannot hear the song): plain prose, one
    whole-second step a line, the words she sings in quotes so her mouth moves to them, about 80-150 words. A book written
    for Seedance reads the same: @Image1 becomes the first frame (and @Image3 the last, where the shot has one)."""
    nm, kind = name(P), s.get("kind", "sung"); look = (P.book.get("looks") or {}).get(s.get("look"), s.get("look", ""))
    fix = lambda t: re.sub(r"@Image1\b", "the first frame", re.sub(r"@Image3\b", "the last frame", t) if s.get("last_frame") else t)
    if kind == "noface":
        return fix("\n".join(x for x in [s["goal"], f"The video starts on the first frame: {s.get('first', s.get('place', 'as shown'))}.",
                                         f"It ends on the last frame: {s.get('last', 'everything arrives at the state shown there')}."
                                         if s.get("last_frame") else "", *s["events"], f"Camera: {s['camera']}",
                                         "Keep the colours, light and materials of the first frame; things move like real objects "
                                         "and never melt or morph. No people and no faces appear. No on-screen text.", s.get("keep", "")] if x))
    manner = s.get("manner", P.book.get("manner", "warm and open: she enjoys singing to us"))
    her = (f"{nm} looks as in the first frame" + (f", {look.rstrip('.')}" if look else "") + "; natural anatomy, five fingers on each "
           f"hand. Only one {nm} appears. No on-screen text.")
    if kind == "silent":
        return fix("\n".join([f"{s['goal']} Her manner is {manner}.", *s["events"],
                              "Nobody sings or speaks: her lips stay closed (a smile is fine).", f"Camera: {s['camera']}", her]))
    T = []
    for a, b, k, w, act, _ in segs:
        if k == "lead": T.append(f'{a}-{b}s: she sings "{w}"; {act}.')
        elif k == "group": T.append(f"{a}-{b}s: her lips closed, she listens; {act}.")
        else: T.append(f"{a}-{b}s: her lips closed; {act}.")
    return fix("\n".join([f"{s['goal']} Her manner is {manner}.", *T, "While she sings there is a smile in her eyes, never a grin.",
                          f"Camera: {s['camera']}", her]))


def build(P, s, write=True, beats=None):
    """one shot -> its job dict (and, with write, its job file and window WAV)."""
    kind, d, vm = s.get("kind", "sung"), P.book.get("defaults", {}), video_model(P); ff = first_frame_only(vm)
    if kind not in ("sung", "silent", "noface"): sys.exit(f"{s['id']}: kind must be sung, silent or noface")
    w0, D, show, items = window(P, s, beats); segs = segments(items, D) if kind == "sung" else []
    sound = bool(kind == "sung" and s.get("sound", d.get("sound", True))) and not ff    # a first-frame model hears nothing
    job = dict(id=s["id"], kind=kind, model=vm, form="first_frame" if ff else "seedance", mode="image" if kind == "noface" or ff else "reference",
               prompt=(prompt_ff if ff else prompt)(P, s, segs, D), first_frame=s["first_frame"], last_frame=s.get("last_frame"),
               images=[] if kind == "noface" or ff else [s["first_frame"], P.book["sheet"]] + ([s["last_frame"]] if s.get("last_frame") else []),
               audio=[], duration=D, resolution=s.get("resolution", d.get("resolution", "720p")),
               aspect_ratio=s.get("aspect_ratio", d.get("aspect_ratio", "16:9")),
               generate_audio=sound, sync=("sound" if sound else "lips") if kind == "sung" else None, w0=w0, show=show,
               lines=[k for k, _ in s.get("timeline", []) if k != "rest"], segments=[list(x) for x in segs], phrases=[])
    for k, a, b, w, act, _ in items:       # her sung phrases in window time, joined across gaps under 0.45 s (for sync)
        if k == "rest": continue
        if job["phrases"] and a - job["phrases"][-1][1] < 0.45: job["phrases"][-1][1] = round(b, 3); job["phrases"][-1][2] += " / " + w
        else: job["phrases"].append([round(a, 3), round(b, 3), w])
    y = None
    if kind == "sung":                     # the window: sent as @Audio1 to Seedance; for a first-frame model only kept, to listen to
        y, job["gate"] = gated(P, s, w0, D); f = P.build / "windows" / f"{s['id']}.wav"; job["window"] = str(f.relative_to(P.dir))
        if not ff: job["audio"] = [job["window"]]
        if write: write_wav(f, y, 48000)
    if write: jsave(P.build / "jobs" / f"{s['id']}.json", job)
    return job, y


def voice_edges(y, sr=48000, rel=-19.0):
    """the first and last moments of the window's audio above (its loudest level + rel) dB."""
    db = level_db(y.mean(1), sr); on = np.nonzero(db > max(-60, db.max() + rel - 2))[0]
    return (on[0] / 100, on[-1] / 100 + 0.01) if len(on) else (None, None)


def lint(P, ids):
    """everything that has cost a take before: -> [(shot, level, message)]"""
    out = []; frames = {}; names = (P.book.get("lint") or {}).get("names", []) + BRANDS
    allow = set((P.book.get("lint") or {}).get("allow", [])) | {name(P)}
    beats = jload(P.build / "beats.json", {}).get("beats"); vm = video_model(P); ff = first_frame_only(vm); grok = "grok" in vm.lower()
    if ff: out.append(("book", "info", f"{vm} reads a first frame and cannot hear the song: its takes are placed by her lips (sync "
                                       "align --face-model), which is approximate; frame the close singing shots to hide it"))
    for sid in ids:
        s = P.shot(sid); job, y = build(P, s, write=False, beats=beats); p = job["prompt"]; kind = job["kind"]
        add = lambda lvl, msg: out.append((sid, lvl, msg))
        lo = 1 if ff and kind != "sung" else 4               # a first-frame model makes 1-15 s; a sung window needs its lead-in
        if not lo <= job["duration"] <= 15: add("ERROR", f"window {job['duration']} s: keep a take to {lo}-15 whole seconds (the method's range); split the shot")
        nw = len(p.split())
        if ff and nw > 150: add("info" if nw <= 200 else "warn", f"{nw} words: about 80-150 suit a first-frame model, which is not tuned "
                                                                 "for long structured prompts; say what she does, the words and the camera once")
        elif kind == "sung" and nw > 450: add("info", f"{nw} words: about 200-400 suit a sung take; say each thing once and keep only what matters")
        if grok and job.get("last_frame"): add("ERROR", "Grok Imagine takes a first frame only: take the last frame out (or make this shot on Seedance)")
        if grok and re.search(PULLBACK, s.get("camera", ""), re.I):
            add("warn", "a pull-back: Grok Imagine has pushed in when asked to pull back, and redrew a painted frame as it pulled "
                        "back; start wide and push in, or cut to the wider view")
        moods = [m.group(0) for m in re.finditer(MOOD, p, re.I)]
        if len(moods) >= 2: add("warn", f"stacked mood words {moods}: each is obeyed literally; keep one, warm by default")
        elif moods: add("info", f"mood word {moods}: make sure it is the one you mean")
        for pat in FROZEN:
            if re.search(pat, p, re.I): add("warn", f"posture rule /{pat}/ in a performance: she will read frozen; keep posture "
                                                   "for the sheet and write movement into the timeline")
        for ln in (p.splitlines() if kind == "sung" else []):
            bare = re.sub(r'"[^"]*"', " ", ln)
            if re.search(r"\bsings?\b", ln, re.I) and re.search(r"\bsmil(e|es|ing)\b|\bgrin", bare, re.I) \
                    and not re.search(r"smil\w* in her eyes|lips (stay )?closed|closed[- ]lip|nobody sings", bare, re.I):
                add("info", "a smile on her mouth while she sings drew a toothy grin: write a smile in her eyes, lips closed "
                            "until her voice begins"); break
        if re.search(LOOKAWAY, p, re.I): add("info", "a look past the lens or behind her turns her head too far: keep her looks in front "
                                                     "of her and point at what is behind her with a hand (and don't pin her eyes "
                                                     "to the lens take after take: it reads as a stare)")
        for nmx in names:
            if re.search(r"\b%s\b" % re.escape(nmx), p) and nmx not in allow:
                add("warn", f'"{nmx}": a real name or a brand in the prompt pulls a real likeness or a logo into the picture')
        refs = set(re.findall(r"@(Image|Audio|Video)(\d)", p)); has = {("Image", str(i + 1)) for i in range(len(job["images"]))} | \
            {("Audio", str(i + 1)) for i in range(len(job["audio"]))}
        for r in sorted(refs - has): add("ERROR", f"the prompt names @{r[0]}{r[1]} but the job has no such input")
        for r in sorted(has - refs): add("ERROR", f"input @{r[0]}{r[1]} has no role in the prompt")
        for f in [job["first_frame"], job.get("last_frame")] + job["images"]:
            if f and not P.p(f).exists(): add("ERROR", f"missing file {f}")
        if job["first_frame"] in frames and frames[job["first_frame"]] != s.get("continues"):
            add("warn", f"same first frame as {frames[job['first_frame']]}: two takes should not start from one frame")
        frames.setdefault(job["first_frame"], sid)
        if kind != "sung":
            ev = [tuple(map(float, m.groups())) for m in (re.match(r"\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*s", e) for e in s.get("events", [])) if m]
            if not ev or ev[0][0] != 0 or ev[-1][1] != job["duration"] or any(a[1] != b[0] for a, b in zip(ev, ev[1:])):
                add("ERROR", f"events must run 0-{job['duration']} s in contiguous 'a-bs:' steps")
            continue
        segs = job["segments"]; lead_in = job["phrases"][0][0] if job["phrases"] else 0
        if segs[0][0] != 0 or segs[-1][1] != job["duration"] or any(a[1] != b[0] for a, b in zip(segs, segs[1:])):
            add("ERROR", "the timeline does not run 0-%d s in whole seconds" % job["duration"])
        wref = ref_db(level_db(y.mean(1), 48000))
        for a, b, k, w, act, lid in segs:
            L = P.lines.get(lid) if lid else None
            if L and (L["t0"] - job["w0"] < a - 0.5 or L["t1"] - job["w0"] > b + 0.6):
                add("warn", f"{a}-{b}s quotes words sung at {L['t0'] - job['w0']:.2f}-{L['t1'] - job['w0']:.2f} s: a segment must hold the words sung in it")
            if k == "rest" and (level_db(y[int(a * 48000):int(b * 48000)].mean(1), 48000) > wref - 19).sum() > 40:
                add("warn", f"{a}-{b}s is written as silent, but the window sings for more than 0.4 s in it")
            if w and re.search(r"[.!;:]\s+\S", w): add("info", f'a stop inside the quoted words ("{w[:40]}..."): right only where the song pauses')
            if w and re.search(r"[.!;:]$", w) and any(x[2] != "rest" and x[0] == b for x in segs):
                nxt = next(x for x in segs if x[0] == b); gap = P.lines[nxt[5]]["t0"] - L["t1"] if L and nxt[5] else 9
                if gap < 0.25: add("warn", f"a full stop between two lines sung straight through ({w[-20:]} / {nxt[3][:20]}): write a comma")
            if k != "rest" and not re.search(MOVES, act, re.I): add("info", f"{a}-{b}s has no movement written: she may read frozen")
        if job["phrases"] and not 0.5 <= lead_in <= 1.0:
            add("warn", f"the window opens {lead_in:.2f} s before her first word: 0.5-1.0 s copies best")
        for who, a, b in job.get("gate", []):        # does the gate cut into the shot's own words? (where a neighbouring
            st = load_audio(P.audio(who), 16000, 1, max(0, a - 0.06), b - a + 0.12); db = level_db(st); q = ref_db(db) - 18
            near = lambda t, key: any(abs(x[key] - t) < 0.15 for x in P.lines.values() if x.get(key) is not None and x["id"] not in job["lines"])
            if len(db) > 12 and db[:4].max() > q and not near(a, "t1"):      # line touches, cutting there is right)
                add("warn", f"the {who} gate opens at {a:.2f} inside sound: the first word may be clipped (check with songmap prof)")
            if len(db) > 12 and db[-4:].max() > q and not near(b, "t0"):
                add("warn", f"the {who} gate closes at {b:.2f} inside sound: the last word may be clipped (check with songmap prof)")
        if job["generate_audio"] is False and not ff: add("info", "sound off: the take is placed by her lips, not by its soundtrack (less exact)")
    return out


def board(P, out_path, beats=None):
    """first frames, windows and lines on one sheet, to look at before paying."""
    from .common import need
    Image = need("PIL.Image", "Pillow", "board"); ImageDraw = need("PIL.ImageDraw", "Pillow", "board")
    cards = []
    for s in P.shots:
        w0, D, show, _ = window(P, s, beats); im = Image.new("RGB", (480, 360), "#f4f2ee"); d = ImageDraw.Draw(im)
        if P.p(s["first_frame"]).exists(): fr = Image.open(P.p(s["first_frame"])).convert("RGB"); fr.thumbnail((480, 270)); im.paste(fr, (0, 0))
        words = " / ".join(P.lines[k]["words"] for k, _ in s.get("timeline", []) if k != "rest") or P.lines.get(s.get("at"), {}).get("words", "")
        rows = [f"{s['id']}  {s.get('kind', 'sung')}  window {w0:.2f} + {D} s  show {show[0]:.2f}-{show[1]:.2f}"] + \
            (textwrap.wrap(words, 72)[:2] + ["", ""])[:2] + textwrap.wrap(s.get("goal") or "", 72)[:1]
        for i, t in enumerate(rows): d.text((8, 276 + 20 * i), t, fill="#111")
        cards.append(im)
    cols = 4; sheet = Image.new("RGB", (cols * 490, 370 * math.ceil(len(cards) / cols)), "white")
    for i, c in enumerate(cards): sheet.paste(c, ((i % cols) * 490, (i // cols) * 370))
    sheet.save(out_path, quality=88); print("wrote", out_path)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="claudia_kit shotbook", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["build", "show", "lint", "board"]); ap.add_argument("book"); ap.add_argument("ids", nargs="*")
    o = ap.parse_args(argv); P = Project(o.book); beats = jload(P.build / "beats.json", {}).get("beats")
    if o.cmd == "board": return board(P, o.ids[0] if o.ids else str(P.build / "board.jpg"), beats)
    if o.cmd == "show": return print(build(P, P.shot(o.ids[0]), write=False, beats=beats)[0]["prompt"])
    if o.cmd == "lint":
        res = lint(P, P.ids(o.ids))
        for sid, lvl, msg in res: print(f"{sid:6s} {lvl:5s} {msg}")
        n = sum(l == "ERROR" for _, l, _ in res); print(f"{len(res)} notes, {n} errors"); sys.exit(1 if n else 0)
    if first_frame_only(video_model(P)):
        print(f"first-frame form for {video_model(P)}: a first frame and a short prompt, no sheet and no audio sent; the windows set "
              "each take's length and place on the song")
    for sid in P.ids(o.ids):
        job, y = build(P, P.shot(sid), beats=beats); msg = ""
        if y is not None:
            a, b = voice_edges(y); p = job["phrases"]
            msg = "<< the window is silent: check the line times" if a is None else \
                f"voice {a:.2f}-{b:.2f} s, timeline {p[0][0]:.2f}-{p[-1][1]:.2f} s" + ("  << lead-in under 0.5 s" if a < 0.5 else "")
        print(f"{sid:6s} {job['kind']:6s} w0 {job['w0']:7.2f}  {job['duration']:2d} s  show {job['show'][0]:.2f}-{job['show'][1]:.2f}  {msg}")


if __name__ == "__main__":
    main()
