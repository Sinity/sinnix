"""cut: the film. An edit list from the shot book and the picks, each take laid on the song along its own map.

  python -m claudia_kit cut edl BOOK.json                     # the cut list: shots, takes, gaps and overlaps
  python -m claudia_kit cut render BOOK.json OUT.mp4 [--from S] [--to S] [--draft] [--grain]
  python -m claudia_kit cut sections BOOK.json DIR [N ...]    # the film in parts, picture only: a new take re-renders one
  python -m claudia_kit cut join BOOK.json DIR OUT.mp4        # the parts joined without re-encoding, with the song
  python -m claudia_kit cut sheets BOOK.json FILM.mp4 OUTDIR [--film-start S]   # a review sheet per shot: 8 frames as shown
  python -m claudia_kit cut flash FILM.mp4                    # the photosensitivity check (exit code 1 on a failure)
  python -m claudia_kit cut audit BOOK.json                   # holds at a shot's head or tail, takes reused, hard bends

The book's edit keys: picks {"S01": 2}; nudge {"S01": 0.04} (seconds added to clip time); knots {"S01": [[song, clip],
...]} (a hand map in place of the measured one between its first and last song times); crop {"S01": [x, y, w, h]} in
the take's pixels; sections [[0, 62.5], ...]. Per shot: "dissolve" (frames of dissolve from the shot before) and
"blend" (mix neighbouring frames where the map slows a take, so a slow push-in does not judder).
Every frame of the film is its take's frame at clip time c(t), the map's time for song time t. A take's first two
frames are never shown (the first is the input still, sharper than what follows, and it pops). The song goes over
with one plain gain to about -14 LUFS (measured with ffmpeg's ebur128, the peak kept under -1 dBFS): nothing else.
Rendering needs Pillow.
"""
import argparse, json, re, subprocess, sys
import numpy as np
from .common import Project, ffmpeg, jload, jsave, need, probe
from .sync import at, final_map


def size(P):
    w, h = P.book.get("size") or ((1080, 1920) if P.book.get("defaults", {}).get("aspect_ratio") == "9:16" else (1920, 1080))
    return int(w), int(h)


def edl(P):
    """[{id, kind, show, file, take, map, dissolve, blend, crop}] in song order; entries without a take have file None.
    The show comes from the book as it is now (an edit), the window from the job the take was made from."""
    from .shotbook import window
    out = []; beats = jload(P.build / "beats.json", {}).get("beats")
    for s in P.shots:
        job = P.job(s["id"]); f, n = P.take(s["id"])
        out.append(dict(id=s["id"], kind=job["kind"], show=tuple(window(P, s, beats)[2]), file=f, take=n, dissolve=s.get("dissolve", 0),
                        blend=s.get("blend", False), crop=(P.book.get("crop") or {}).get(s["id"]),
                        map=final_map(P, s["id"], job, n) if f else None))
    return sorted(out, key=lambda x: x["show"][0])


def fills(P, x, W, H):
    """a take whose shape is not the film's (Grok Imagine's 480p came back 736 x 400) fills the frame, centred, its edges
    cropped, rather than being stretched; a crop in the book decides instead."""
    pr = probe(x["file"]); return not x["crop"] and bool(pr["width"]) and abs(pr["width"] / pr["height"] / (W / H) - 1) > 0.01


def cache(P, x, W, H, fps):
    """the take's frames at film size, decoded once."""
    c = x["crop"]; d = P.build / "framecache" / (f"{x['id']}-t{x['take']}-{W}x{H}" + ("-c%d_%d_%d_%d" % tuple(c) if c else ""))
    if not (d / "done").exists():
        d.mkdir(parents=True, exist_ok=True); fit = f":force_original_aspect_ratio=increase,crop={W}:{H}" if fills(P, x, W, H) else ""
        ffmpeg("-i", x["file"], "-map", "0:V:0", "-vf", (f"crop={c[2]}:{c[3]}:{c[0]}:{c[1]}," if c else "") +
               f"fps={fps},scale={W}:{H}:flags=lanczos{fit},setsar=1", "-q:v", "2", d / "f%05d.jpg")
        (d / "done").write_text("ok")
    return sorted(d.glob("f*.jpg"))


def loudness(P):
    """(integrated LUFS, sample peak dBFS) of the song, measured once with ffmpeg's ebur128."""
    song = P.audio("song"); key = f"{song}:{song.stat().st_mtime}"; c = jload(P.build / "loudness.json", {})
    if c.get("key") != key:
        r = subprocess.run(["ffmpeg", "-nostats", "-i", str(song), "-af", "ebur128=peak=sample", "-f", "null", "-"], capture_output=True, text=True)
        tail = r.stderr[r.stderr.rfind("Summary:"):]
        c = dict(key=key, lufs=float(re.search(r"I:\s+(-?[\d.]+) LUFS", tail).group(1)), peak=float(re.search(r"Peak:\s+(-?[\d.]+) dBFS", tail).group(1)))
        jsave(P.build / "loudness.json", c)
    return c["lufs"], c["peak"]


def gain_db(P, target=-14.0):
    lufs, peak = loudness(P); g = min(target - lufs, -1.0 - peak)
    return round(g, 2), lufs, peak


def render(P, out, a, b, draft=False, grain=False, picture_only=False, fades=True):
    Image = need("PIL.Image", "Pillow", "cut render"); fps = P.book.get("fps", 24); W, H = size(P)
    if draft: W, H = W // 2, H // 2
    song_end = probe(P.audio("song"))["duration"]; E = [x for x in edl(P) if x["file"] and x["show"][0] < b and x["show"][1] > a]
    miss = [x["id"] for x in edl(P) if not x["file"] and x["show"][0] < b and x["show"][1] > a]
    if miss: print("no take yet (black):", " ".join(miss))
    for x in E: x["frames"] = cache(P, x, W, H, fps)
    g, lufs, peak = gain_db(P); n_out = int(round((b - a) * fps)); black = Image.new("RGB", (W, H))
    aud = [] if picture_only else ["-ss", f"{a:.4f}", "-t", f"{n_out / fps:.4f}", "-i", str(P.audio("song"))]
    cmd = ["-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-", *aud, "-map", "0:v",
           *([] if picture_only else ["-map", "1:a", "-af", f"volume={g}dB", "-c:a", "aac", "-b:a", "256k"]),
           "-vf", ("noise=c0s=5:c0f=t+u," if grain else "") + "format=yuv420p", "-c:v", "libx264", "-preset",
           "veryfast" if draft else "medium", "-crf", "23" if draft else "16", "-movflags", "+faststart", str(out)]
    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", *cmd], stdin=subprocess.PIPE); memo = {}

    def img(path):
        if path not in memo:
            if len(memo) > 8: memo.clear()
            memo[path] = Image.open(path).convert("RGB")
        return memo[path]

    def frame_at(t):
        x = next((x for x in E if x["show"][0] <= t < x["show"][1]), None)
        if x is None: return black, None
        c = at(x["map"], t); pos = c * fps; i = min(max(int(pos), 2), len(x["frames"]) - 1); im = img(x["frames"][i])
        if x["blend"] and 2 <= i < len(x["frames"]) - 1 and 0.03 < pos - int(pos) < 0.97:
            im = Image.blend(im, img(x["frames"][i + 1]), pos - int(pos))
        return im, x

    for q in range(n_out):
        t = a + (q + 0.5) / fps; im, x = frame_at(t)
        if x is not None and x["dissolve"] and t - x["show"][0] < x["dissolve"] / fps:
            prev, _ = frame_at(x["show"][0] - 0.5 / fps); u = (t - x["show"][0]) * fps / x["dissolve"]
            im = Image.blend(prev, im, u * u * (3 - 2 * u))
        k = 1.0                                    # from black at the film's start, to black at its end; short fades on an excerpt
        if t < 1.0: k = min(k, max(0.0, (t - 0.2) / 0.6))
        if t > song_end - 1.5: k = min(k, max(0.0, (song_end - 0.25 - t) / 1.2))
        if fades and not picture_only and a > 0.5: k = min(k, (q + 0.5) / (0.2 * fps))
        if fades and not picture_only and b < song_end - 0.5: k = min(k, (n_out - q) / (0.4 * fps))
        if k < 1.0: im = Image.blend(black, im, max(0.0, k))
        proc.stdin.write(im.tobytes())
    proc.stdin.close(); proc.wait()
    print(f"wrote {out}: {a:.2f}-{b:.2f} s, {len(E)} shots, song {lufs:.1f} LUFS (peak {peak:.1f} dBFS) {'' if picture_only else f'+ {g:.1f} dB'}")
    if not picture_only and lufs + g < -16.0:
        print(f"  << the mix sits at {lufs + g:.1f} LUFS: the song's peak ({peak:.1f} dBFS) stops the plain gain short of -14. "
              "Master the song louder (a limiter, before the cut), or keep it as it is if it sounds right.")


def sections(P):
    """the book's sections, or cuts at shot boundaries about every 45 s."""
    if P.book.get("sections"): return [tuple(s) for s in P.book["sections"]]
    end = probe(P.audio("song"))["duration"]; cuts = [0.0]
    for x in edl(P):
        if x["show"][0] - cuts[-1] >= 45 and end - x["show"][0] > 20: cuts.append(x["show"][0])
    return list(zip(cuts, cuts[1:] + [end]))


def join(P, d, out):
    from pathlib import Path
    d = Path(d); S = sections(P); lst = d / "list.txt"; g, _, _ = gain_db(P)
    lst.write_text("".join(f"file '{(d / f's{i + 1:02d}.mp4').resolve()}'\n" for i in range(len(S))))
    ffmpeg("-f", "concat", "-safe", "0", "-i", lst, "-ss", f"{S[0][0]:.4f}", "-i", P.audio("song"), "-map", "0:v", "-map", "1:a",
           "-c:v", "copy", "-af", f"volume={g}dB", "-c:a", "aac", "-b:a", "320k", "-t", f"{S[-1][1] - S[0][0]:.3f}", "-movflags", "+faststart", out)
    print("wrote", out)


def sheets(P, film, outdir, t0=0.0):
    """for a fresh pair of eyes: per shot, eight frames spread over it as SHOWN in the film, 4 x 2."""
    from pathlib import Path
    outdir = Path(outdir); outdir.mkdir(parents=True, exist_ok=True); pr = probe(film); fps = pr["fps"] or 24
    for k, x in enumerate(edl(P), 1):
        a, b = x["show"]
        if a < t0 - 0.01 or b > t0 + pr["duration"] + 0.05: continue
        sel = "+".join(f"eq(n\\,{int((a + (b - a) * (i + 0.5) / 8 - t0) * fps)})" for i in range(8))
        f = outdir / f"{k:02d}-{x['id']}-{a:06.2f}.jpg"
        ffmpeg("-i", film, "-vf", f"select='{sel}',scale=640:-2,tile=4x2", "-frames:v", "1", "-vsync", "0", "-q:v", "3", f)
        print(f.name)


def flash(video, max_per_s=3, area=0.25, delta=0.10):
    """after WCAG 2.3.1's general flash threshold: a flash is a pair of opposing changes in relative luminance of at
    least `delta` (the darker state under 0.8) over at least `area` of the frame; more than `max_per_s` in any second fails."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", "fps=24,scale=96:54", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.uint8).reshape(-1, 54, 96, 3).astype(np.float32) / 255
    L = np.where(x <= .04045, x / 12.92, ((x + .055) / 1.055) ** 2.4) @ np.array([.2126, .7152, .0722], np.float32)
    d = L[1:] - L[:-1]; dark = np.minimum(L[1:], L[:-1]) < .8
    ev = np.zeros(len(d), int); ev[((d >= delta) & dark).mean(axis=(1, 2)) >= area] = 1; ev[((d <= -delta) & dark).mean(axis=(1, 2)) >= area] = -1
    alt = []
    for i in np.nonzero(ev)[0]:                    # same-direction steps with no opposite change between them are one change
        if not alt or ev[alt[-1]] != ev[i]: alt.append(i)
    tt = (np.array(alt, float) + 1) / 24; worst, fails = 0, []
    for s in np.arange(0, len(L) / 24, 1 / 24):
        c = int(((tt >= s) & (tt < s + 1)).sum()) // 2; worst = max(worst, c)
        if c > max_per_s and (not fails or s - fails[-1][0] >= 1): fails.append((round(float(s), 2), c))
    res = dict(seconds=round(len(L) / 24, 2), flashes=len(tt[::2]), worst_per_second=worst, limit=max_per_s, fails=fails, ok=not fails)
    print(json.dumps(res)); return res


def audit(P):
    fps = P.book.get("fps", 24); E = edl(P); used = {}
    for x in E:
        if not x["file"]: print(f"{x['show'][0]:8.2f}-{x['show'][1]:8.2f} {x['id']:6s} no take"); continue
        n = probe(x["file"])["frames"] or int(probe(x["file"])["duration"] * fps); c0, c1 = at(x["map"], x["show"][0]), at(x["map"], x["show"][1])
        rates = [(at(x["map"], t + 0.5) - at(x["map"], t)) / 0.5 for t in np.arange(x["show"][0], x["show"][1] - 0.5, 0.1)]   # over 0.5 s
        worst = max(rates, key=lambda r: abs(r - 1)) if rates else 1.0; used.setdefault(str(x["file"]), []).append(x["id"])
        pr = probe(x["file"]); W, H = size(P)
        flag = (f"  << {pr['width']}x{pr['height']}, not the film's shape: it fills the frame, edges cropped (or set crop)"
                if fills(P, x, W, H) else "") + \
               (f"  << holds {2 / fps - c0:.2f} s at the head" if c0 < 2 / fps - 0.02 else "") + \
               (f"  << holds {c1 - n / fps:.2f} s at the tail" if c1 > n / fps + 0.03 else "") + \
               (f"  << bent to {worst:.2f}x: set blend, or look at it" if abs(worst - 1) > 0.3 else "")
        print(f"{x['show'][0]:8.2f}-{x['show'][1]:8.2f} {x['id']:6s} take {x['take']}  clip {c0:5.2f}-{c1:5.2f} of {n / fps:5.2f}{flag}")
    for f, ids in used.items():
        if len(ids) > 1: print(f"  << one take in {len(ids)} shots: {', '.join(ids)}")
    song_end = probe(P.audio("song"))["duration"]
    if E and E[0]["show"][0] > 0.05: print(f"  << black for {E[0]['show'][0]:.2f} s before the first shot ({E[0]['id']})")
    if E and song_end - E[-1]["show"][1] > 0.05: print(f"  << black for the last {song_end - E[-1]['show'][1]:.2f} s of the song, after {E[-1]['id']}")
    prev = None
    for x in E:
        if prev and abs(x["show"][0] - prev["show"][1]) > 0.011:
            print(f"  << {'gap' if x['show'][0] > prev['show'][1] else 'overlap'} of {abs(x['show'][0] - prev['show'][1]):.2f} s between {prev['id']} and {x['id']}")
        prev = x


def main(argv=None):
    ap = argparse.ArgumentParser(prog="claudia_kit cut", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["edl", "render", "sections", "join", "sheets", "flash", "audit"]); ap.add_argument("args", nargs="+")
    ap.add_argument("--from", dest="t0", type=float); ap.add_argument("--to", dest="t1", type=float)
    ap.add_argument("--film-start", type=float, default=0.0, help="sheets: the song time the film file starts at")
    ap.add_argument("--draft", action="store_true"); ap.add_argument("--grain", action="store_true"); ap.add_argument("--no-fade", action="store_true")
    o = ap.parse_args(argv)
    if o.cmd == "flash": sys.exit(0 if flash(o.args[0])["ok"] else 1)
    P = Project(o.args[0]); end = probe(P.audio("song"))["duration"]
    if o.cmd == "edl":
        prev = 0.0
        for x in edl(P):
            gap = f"  (gap {x['show'][0] - prev:+.2f})" if abs(x["show"][0] - prev) > 0.011 else ""
            print(f"{x['show'][0]:8.2f}-{x['show'][1]:8.2f}  {x['id']:6s} {x['kind']:6s} " + (f"take {x['take']}" if x["file"] else "NO TAKE") + gap)
            prev = x["show"][1]
    elif o.cmd == "render": render(P, o.args[1], o.t0 or 0.0, o.t1 or end, o.draft, o.grain, fades=not o.no_fade)
    elif o.cmd == "sections":
        from pathlib import Path
        d = Path(o.args[1]); d.mkdir(parents=True, exist_ok=True); S = sections(P)
        for i in ([int(x) for x in o.args[2:]] or range(1, len(S) + 1)):
            render(P, d / f"s{i:02d}.mp4", *S[i - 1], draft=o.draft, grain=o.grain, picture_only=True)
    elif o.cmd == "join": join(P, o.args[1], o.args[2])
    elif o.cmd == "sheets": sheets(P, o.args[1], o.args[2], o.film_start)
    else: audit(P)


if __name__ == "__main__":
    main()
